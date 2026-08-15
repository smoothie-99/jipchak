"""
rpi_full.py — RPi 통합 송신 스크립트 (게임 플로우 + 카메라 라이프사이클)

동작 흐름:
    1) Arduino 시리얼에서 state 읽기 (sendStatus 의 st 필드)
    2) state 전이 감지:
         IDLE     (1) ↔ READY (2)         : 카메라 ON/OFF 토글 (발열 보호)
         READY    (2) → PLAYING (3)       : SESSION_START 송신 (한 판 시작)
         RETURN_UP(10) → POST_GAME (11)   : GAME_RESULT 송신 (한 판 종료)
         POST_GAME (11) → PLAYING (3)     : SESSION_START 송신 (다음 판)
         POST_GAME (11) → IDLE (1)        : 카메라 OFF (세션 전체 종료)
    3) 카메라 ON 동안만 D435 + 웹캠 영상을 AI 서버로 송신

Arduino StateMachine.h::SystemState 와 일치 (게임 플로우 재설계 후):
    IDLE        = 1   캠 OFF
    READY       = 2   캠 ON, 게임 시작 대기
    PLAYING     = 3   게임 중 (조이스틱 + 15초 타이머)
    GRAB_DOWN   = 4
    GRAB_CLOSE  = 5
    GRAB_UP     = 6
    RETURN_MOVE = 7
    RETURN_DOWN = 8
    RETURN_OPEN = 9
    RETURN_UP   = 10
    POST_GAME   = 11  한 판 종료, 다음판/종료 대기

의존성 (RPi):
    pip install opencv-python-headless msgpack websockets numpy lz4 pyserial
    + librealsense2 빌드 후 venv 에 pyrealsense2 복사

사용 예:
    python3 rpi_full.py \
        --url wss://k14d108.p.ssafy.io/ws/camera \
        --serial /dev/ttyACM0 \
        --webcam '/dev/v4l/by-id/usb-Web_Camera_Web_Camera_240729163401-video-index0' \
        --fps 30
"""
import argparse
import asyncio
import json
import signal
import threading
import time
import uuid
from typing import Optional

import cv2
import lz4.frame
import msgpack
import numpy as np
import pyrealsense2 as rs
import serial
import websockets


# Arduino StateMachine.h::SystemState 와 일치
ARDUINO_STATE_IDLE        = 1
ARDUINO_STATE_READY       = 2
ARDUINO_STATE_PLAYING     = 3
ARDUINO_STATE_GRAB_DOWN   = 4
ARDUINO_STATE_GRAB_CLOSE  = 5
ARDUINO_STATE_GRAB_UP     = 6
ARDUINO_STATE_RETURN_MOVE = 7
ARDUINO_STATE_RETURN_DOWN = 8
ARDUINO_STATE_RETURN_OPEN = 9
ARDUINO_STATE_RETURN_UP   = 10
ARDUINO_STATE_POST_GAME   = 11

_stop = asyncio.Event()


def _install_signal_handlers() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop.set)
        except NotImplementedError:
            pass


# ---------- D435 (pyrealsense2) ----------

class RealSensePipeline:
    """D435 RGB + Depth 동시 캡처 + align. start/stop 반복 가능 (멀티스레드 비동기)."""

    def __init__(self, width: int, height: int, fps: int) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.pipeline: Optional[rs.pipeline] = None
        self.align: Optional[rs.align] = None
        self.depth_scale: float = 0.0

        self.latest_color: Optional[np.ndarray] = None
        self.latest_depth: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.pipeline is not None:
            return
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        profile = self.pipeline.start(config)
        self.align = rs.align(rs.stream.color)
        depth_sensor = profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        print(f"[d435] started: {self.width}x{self.height} @ {self.fps} fps")

        self._stop.clear()
        self.latest_color = None
        self.latest_depth = None
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            if self.pipeline is None:
                break
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                aligned = self.align.process(frames)
                color_frame = aligned.get_color_frame()
                depth_frame = aligned.get_depth_frame()
                if not color_frame or not depth_frame:
                    continue
                color = np.asanyarray(color_frame.get_data())
                depth = np.asanyarray(depth_frame.get_data())
                with self._lock:
                    self.latest_color = color
                    self.latest_depth = depth
            except Exception as e:
                if not self._stop.is_set():
                    print(f"[d435] capture error: {e}")
                    time.sleep(0.05)

    def get_frames(self):
        with self._lock:
            return self.latest_color, self.latest_depth

    def stop(self) -> None:
        if self.pipeline is None:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        try:
            self.pipeline.stop()
        except Exception:
            pass
        self.pipeline = None
        self.align = None
        print("[d435] stopped")


# ---------- 일반 USB 웹캠 (cv2) ----------

class WebcamCapture:
    """USB 웹캠. start/stop 반복 가능 (멀티스레드 비동기)."""

    def __init__(self, device, width: int, height: int, fps: int) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None

        self.latest_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.cap is not None:
            return
        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.cap = None
            raise RuntimeError(f"webcam open failed (device={self.device})")
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        print(f"[webcam] opened: {actual_w}x{actual_h} @ {actual_fps:.1f} fps (device={self.device})")

        self._stop.clear()
        self.latest_frame = None
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            if self.cap is None:
                break
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            with self._lock:
                self.latest_frame = frame

    def read(self):
        with self._lock:
            return self.latest_frame

    def release(self) -> None:
        if self.cap is None:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        try:
            self.cap.release()
        except Exception:
            pass
        self.cap = None
        print("[webcam] released")


# ---------- 카메라 라이프사이클 ----------

class CameraLifecycle:
    """D435 + 웹캠을 묶어서 ON/OFF 토글. Arduino state 전이 시점에 호출된다.

    동시성 가정:
        - turn_on / turn_off 는 serial_reader_task 하나에서만 호출 (직렬).
        - get_frames 는 frame_loop_task 에서만 호출.
        - 토글 중 get_frames 가 호출되면 instance 가 None 으로 보이면서
          그 프레임만 건너뛴다. 명시적 lock 은 두지 않음 (atomic 참조 갱신만).
    """

    def __init__(self, width: int, height: int, fps: int, webcam_dev) -> None:
        self.d435 = RealSensePipeline(width, height, fps)
        self.webcam = WebcamCapture(webcam_dev, width, height, fps) if webcam_dev is not None else None
        self._on = False

    def is_on(self) -> bool:
        return self._on

    def turn_on(self) -> None:
        if self._on:
            return
        try:
            self.d435.start()
        except Exception as e:
            print(f"[cam] d435 start failed: {e}")
        if self.webcam is not None:
            try:
                self.webcam.start()
            except Exception as e:
                print(f"[cam] webcam start failed: {e}")
        self._on = True
        print("[cam] ON")

    def turn_off(self) -> None:
        if not self._on:
            return
        self.d435.stop()
        if self.webcam is not None:
            self.webcam.release()
        self._on = False
        print("[cam] OFF")

    def get_frames(self):
        if not self._on:
            return None, None, None
        d435_color, d435_depth = self.d435.get_frames()
        webcam_color = self.webcam.read() if self.webcam is not None else None
        return webcam_color, d435_color, d435_depth


# ---------- Frame packing ----------

def _encode_jpeg(frame, quality: int) -> bytes:
    if frame is None:
        return b""
    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpg.tobytes() if ok else b""


def _pack_frame(webcam_color, d435_color, d435_depth, jpeg_q: int) -> Optional[bytes]:
    payload = {
        "timestamp": time.time_ns(),
        # 고정 매핑: 웹캠 → Cam1 (color_2d, 녹화 대상), D435 → Cam2 (color_3d)
        "color_2d": _encode_jpeg(webcam_color, jpeg_q),
        "color_3d": _encode_jpeg(d435_color, jpeg_q),
        "depth_3d": b"",
        "depth_3d_shape": (),
    }
    if d435_depth is not None:
        payload["depth_3d"] = lz4.frame.compress(d435_depth.tobytes())
        payload["depth_3d_shape"] = d435_depth.shape
    if not payload["color_2d"] and not payload["color_3d"] and not payload["depth_3d"]:
        return None
    return msgpack.packb(payload)


# ---------- 게임 세션 ----------

class GameSession:
    """현재 진행 중인 한 판의 ID. PLAYING 진입마다 새 ID 발급."""

    def __init__(self) -> None:
        self.id: Optional[str] = None

    def is_active(self) -> bool:
        return self.id is not None

    def start(self) -> str:
        self.id = f"rpi-{uuid.uuid4()}"
        return self.id

    def stop(self) -> Optional[str]:
        prev, self.id = self.id, None
        return prev


# ---------- 시리얼 reader 태스크 ----------

async def serial_reader_task(
    port: str,
    baud: int,
    ws,
    session: GameSession,
    cam: CameraLifecycle,
    send_lock: asyncio.Lock,
) -> None:
    """Arduino 시리얼에서 state 변화 감지 →
       1) 카메라 ON/OFF 토글
       2) SESSION_START / GAME_RESULT 송신
    """
    try:
        ser = serial.Serial(port, baud, timeout=0.1)
    except Exception as e:
        print(f"[serial] open failed ({port}): {e}")
        return

    print(f"[serial] opened {port} @ {baud}")
    loop = asyncio.get_running_loop()
    last_state = ARDUINO_STATE_IDLE

    def _read_line() -> Optional[str]:
        try:
            raw = ser.readline()
            return raw.decode("utf-8", errors="ignore").strip() if raw else None
        except Exception as e:
            print(f"[serial] read error: {e}")
            return None

    try:
        while not _stop.is_set():
            line = await loop.run_in_executor(None, _read_line)
            if not line:
                await asyncio.sleep(0.02)
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 일회성 이벤트 (예: IDLE 빨강 → GUIDE 모달 호출)
            if data.get("t") == "e":
                name = data.get("e")
                if isinstance(name, str) and name:
                    async with send_lock:
                        await ws.send(json.dumps({"event": name}))
                    print(f"[serial] event forwarded: {name}")
                continue

            if data.get("t") != "s":
                continue
            state = data.get("st")
            if not isinstance(state, int):
                continue
            if state == last_state:
                continue

            # ───── 카메라 lifecycle + 세션 생성 ─────
            # 세션 = 한 사용자가 다회 플레이하는 단위 (Frontend 가 선택한 1/3/5 판).
            # IDLE → 비IDLE (READY 진입) 시 session.start() 로 새 uuid 발급, 그 후 모든 판이 같은 id 공유.
            # 비IDLE → IDLE (세션 종료) 시 session.stop() + SESSION_END 송신.
            was_idle = last_state == ARDUINO_STATE_IDLE
            now_idle = state == ARDUINO_STATE_IDLE
            if was_idle and not now_idle:
                # 파란 버튼 누름 (IDLE -> READY) → 홈 화면에서 게임 화면으로 자동 전환하기 위한 이벤트
                async with send_lock:
                    await ws.send(json.dumps({"event": "BLUE_BUTTON_PRESS"}))
                print(f"[serial] event forwarded: BLUE_BUTTON_PRESS")

                if not session.is_active():
                    session.start()
                sid = session.id
                if sid:
                    async with send_lock:
                        await ws.send(json.dumps({"event": "START", "session_id": sid}))
                    print(f"[serial] session START: {sid} (state {last_state} -> {state})")
            elif not was_idle and now_idle:
                session.stop()
                # (POST_GAME timeout / PLAYING idle timeout / READY 빨강 뒤로 등 모든 경로).
                async with send_lock:
                    await ws.send(json.dumps({"event": "SESSION_END"}))
                print(f"[serial] SESSION_END (state {last_state} → {state})")

            # ───── 판(round) 이벤트 ─────
            #   PLAYING 진입(=한 판 시작) : START (기존 session_id 재사용)
            #   POST_GAME 진입(=한 판 끝) : STOP
            if state == ARDUINO_STATE_PLAYING and last_state == ARDUINO_STATE_POST_GAME:
                sid = session.id
                if sid:
                    async with send_lock:
                        await ws.send(json.dumps({"event": "START", "session_id": sid}))
                    print(f"[serial] game START: {sid} (state {last_state} → {state})")
            elif state == ARDUINO_STATE_POST_GAME and last_state != ARDUINO_STATE_POST_GAME:
                sid = session.id
                if sid:
                    async with send_lock:
                        await ws.send(json.dumps({"event": "STOP", "session_id": sid}))
                    print(f"[serial] game STOP:  {sid} (state {last_state} → {state})")

            # SESSION_END 는 위 "비IDLE → IDLE" 통합 분기에서 이미 송신됨.

            last_state = state
    finally:
        try:
            ser.close()
        except Exception:
            pass
        print("[serial] closed")


# ---------- 카메라 frame 송신 태스크 ----------

async def frame_loop_task(
    cam: CameraLifecycle,
    ws,
    fps: int,
    jpeg_q: int,
    send_lock: asyncio.Lock,
) -> None:
    """카메라 ON 동안만 frame 송신. OFF 면 그냥 polling sleep."""
    interval = 1.0 / max(fps, 1)
    sent = 0
    t_start = time.time()

    while not _stop.is_set():
        if not cam.is_on():
            await asyncio.sleep(interval)
            continue

        webcam_color, d435_color, d435_depth = cam.get_frames()
        # 2프레임에 1번만 depth 전송 (대역폭 절감)
        send_depth = (sent % 2 == 0)
        payload = _pack_frame(webcam_color, d435_color, d435_depth if send_depth else None, jpeg_q)
        if payload is not None:
            try:
                async with send_lock:
                    await ws.send(payload)
                sent += 1
            except websockets.ConnectionClosed:
                print("[frame] ws closed by server")
                break

        if sent and sent % 100 == 0:
            elapsed = time.time() - t_start
            print(f"[frame] sent {sent} ({sent / elapsed:.1f} fps)")

        await asyncio.sleep(interval)


# ---------- 메인 ----------

async def run(
    url: str,
    serial_port: str,
    baud: int,
    webcam_dev,
    width: int,
    height: int,
    fps: int,
    jpeg_q: int,
) -> None:
    """WS 끊김 시 지수 백오프로 자동 재연결.

    발표장 핫스팟 환경에서 신호가 깜빡여도 사용자 개입 없이 복구되도록
    한 번 끊겨도 프로세스가 죽지 않고 다시 붙는다. 카메라/세션 상태는
    재연결 시점에 새로 시작 (이전 진행 중 세션은 STOP 으로 정리).
    """
    cam = CameraLifecycle(width, height, fps, webcam_dev)
    session = GameSession()
    send_lock = asyncio.Lock()

    backoff = 1.0
    try:
        while not _stop.is_set():
            try:
                print(f"[main] connecting to {url} ...")
                async with websockets.connect(url, max_size=None, ping_interval=20, ping_timeout=20) as ws:
                    print("[main] connected")
                    # [수정] 웹 UI에서 언제든 게임을 시작할 수 있도록, 연결 시점에 카메라를 켭니다.
                    # 이로 인해 홈 화면에서도 카메라가 켜져 있게 됩니다.
                    cam.turn_on()
                    backoff = 1.0  # 성공 시 백오프 리셋

                    tasks = [
                        asyncio.create_task(frame_loop_task(cam, ws, fps, jpeg_q, send_lock)),
                        asyncio.create_task(serial_reader_task(serial_port, baud, ws, session, cam, send_lock)),
                    ]

                    # _stop 또는 어느 한 task 라도 종료되면 빠져나옴 (WS 끊김 등).
                    stop_task = asyncio.create_task(_stop.wait())
                    done, pending = await asyncio.wait(
                        tasks + [stop_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # 진행 중 세션 있으면 STOP 송신 (가능하면)
                    if session.is_active():
                        sid = session.stop()
                        try:
                            async with send_lock:
                                await ws.send(json.dumps({"event": "STOP", "session_id": sid}))
                            print(f"[main] sent final STOP: {sid}")
                        except Exception:
                            pass

                    for t in tasks + [stop_task]:
                        t.cancel()
                    await asyncio.gather(*tasks, stop_task, return_exceptions=True)

                    if _stop.is_set():
                        break

                    # WS 끊김 외 사유로 task 종료 → 재연결 시도
                    print("[main] connection lost, reconnecting ...")
            except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                # [수정] 연결 실패 시에도 카메라를 끕니다.
                cam.turn_off()
                print(f"[main] connect failed: {e}; retry in {backoff:.1f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
    finally:
        cam.turn_off()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="ws[s]://<AI 서버>:<port>/ws/camera")
    p.add_argument("--serial", required=True, help="Arduino 시리얼 디바이스 (예: /dev/ttyACM0)")
    p.add_argument("--baud", type=int, default=115200, help="Arduino BAUD (기본 115200)")
    p.add_argument("--webcam", default="0", help="웹캠 인덱스 또는 /dev/v4l/by-id/... path")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--jpeg-quality", type=int, default=40)
    args = p.parse_args()

    def _to_device(v):
        try:
            return int(v)
        except ValueError:
            return v

    webcam_dev = _to_device(args.webcam)

    async def _main() -> None:
        _install_signal_handlers()
        await run(
            args.url, args.serial, args.baud, webcam_dev,
            args.width, args.height, args.fps, args.jpeg_quality,
        )

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
