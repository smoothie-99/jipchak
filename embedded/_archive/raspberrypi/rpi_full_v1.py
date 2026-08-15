"""
rpi_full.py — RPi 통합 송신 스크립트 (게임 트리거 기반)

동작 흐름:
    1) 카메라 (D435 + 웹캠) 영상은 **항상** 송신 → 브라우저 라이브 미리보기
    2) Arduino 시리얼에서 state 읽기 → IDLE↔게임 전환을 감지
    3) 게임 시작 (IDLE → !IDLE) 시 WS 텍스트 START 송신 → AI 가 녹화 시작
    4) 게임 종료 (!IDLE → IDLE) 시 WS 텍스트 STOP 송신 → AI 가 mp4 finalize + Spring 업로드

Arduino 프로토콜 (embedded/arduino/.../Comm.cpp 와 일치):
    - 매 100ms : {"t":"s","x":<float>,"y":<float>,"st":<int>}
    - st 값: 1=IDLE, 2~9=게임 진행 중 (StateMachine.h::SystemState 참조)

vs. rpi_realsense.py 와 차이점:
    - 단일 세션(연결=세션) → 다중 세션 (게임마다 별도 mp4)
    - Arduino 시리얼 통합 (pyserial)
    - 영상은 항상 송신, 녹화만 게임 동안

의존성 (RPi):
    pip install opencv-python-headless msgpack websockets numpy lz4 pyserial
    + librealsense2 빌드 후 venv 에 pyrealsense2 복사 (rpi_realsense.py 와 동일)

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
ARDUINO_STATE_IDLE = 1

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
    """D435 RGB + Depth 동시 캡처 + align."""

    def __init__(self, width: int, height: int, fps: int) -> None:
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        profile = self.pipeline.start(config)
        self.align = rs.align(rs.stream.color)
        depth_sensor = profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        print(f"[d435] started: {width}x{height} @ {fps} fps, depth_scale={self.depth_scale}")

    def get_frames(self) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
            aligned = self.align.process(frames)
            color = aligned.get_color_frame()
            depth = aligned.get_depth_frame()
            if not color or not depth:
                return None, None
            return np.asanyarray(color.get_data()), np.asanyarray(depth.get_data())
        except Exception as e:
            print(f"[d435] frame error: {e}")
            return None, None

    def stop(self) -> None:
        try:
            self.pipeline.stop()
        except Exception:
            pass
        print("[d435] stopped")


# ---------- 일반 USB 웹캠 (cv2) ----------

class WebcamCapture:
    def __init__(self, device, width: int, height: int, fps: int) -> None:
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"webcam open failed (device={device})")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        print(f"[webcam] opened: {actual_w}x{actual_h} @ {actual_fps:.1f} fps (device={device})")

    def read(self) -> Optional[np.ndarray]:
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self) -> None:
        self.cap.release()
        print("[webcam] released")


# ---------- Frame packing ----------

def _encode_jpeg(frame: Optional[np.ndarray], quality: int) -> bytes:
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


# ---------- 게임 세션 추적 ----------

class GameSession:
    """현재 진행 중인 게임 세션 ID. 동시 한 게임만 가정."""

    def __init__(self) -> None:
        self.id: Optional[str] = None

    def is_active(self) -> bool:
        return self.id is not None

    def start(self) -> str:
        self.id = f"rpi-{uuid.uuid4().hex[:8]}"
        return self.id

    def stop(self) -> Optional[str]:
        prev, self.id = self.id, None
        return prev


# ---------- WS 송신 직렬화용 락 ----------
# frame 송신 (binary) 과 control 송신 (text) 가 동시에 일어나면 race 가능 →
# asyncio.Lock 으로 직렬화. websockets 의 send 자체는 atomic 이지만
# 명시적 직렬화로 디버깅 단순화.


# ---------- 시리얼 reader 태스크 ----------

async def serial_reader_task(
    port: str,
    baud: int,
    ws,
    session: GameSession,
    send_lock: asyncio.Lock,
) -> None:
    """Arduino 시리얼에서 state 변화 감지 → WS START/STOP 텍스트 송신."""
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
            if data.get("t") != "s":
                continue
            state = data.get("st")
            if not isinstance(state, int):
                continue

            # state 변화 감지
            was_idle = last_state == ARDUINO_STATE_IDLE
            now_idle = state == ARDUINO_STATE_IDLE

            if was_idle and not now_idle:
                # 게임 시작
                sid = session.start()
                async with send_lock:
                    await ws.send(json.dumps({"event": "START", "session_id": sid}))
                print(f"[serial] game START: {sid} (state {last_state} → {state})")
            elif not was_idle and now_idle:
                # 게임 종료
                sid = session.stop()
                if sid:
                    async with send_lock:
                        await ws.send(json.dumps({"event": "STOP", "session_id": sid}))
                    print(f"[serial] game STOP: {sid} (state {last_state} → {state})")

            last_state = state
    finally:
        try:
            ser.close()
        except Exception:
            pass
        print("[serial] closed")


# ---------- 카메라 frame 송신 태스크 ----------

async def frame_loop_task(
    d435: RealSensePipeline,
    webcam: Optional[WebcamCapture],
    ws,
    fps: int,
    jpeg_q: int,
    send_lock: asyncio.Lock,
) -> None:
    """영상 프레임을 항상 송신 (게임 진행 여부 무관)."""
    interval = 1.0 / max(fps, 1)
    sent = 0
    t_start = time.time()

    while not _stop.is_set():
        d435_color, d435_depth = d435.get_frames()
        webcam_color = webcam.read() if webcam else None

        payload = _pack_frame(webcam_color, d435_color, d435_depth, jpeg_q)
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
    d435 = RealSensePipeline(width, height, fps)
    try:
        webcam = WebcamCapture(webcam_dev, width, height, fps) if webcam_dev else None
    except RuntimeError as e:
        print(f"[main] webcam disabled: {e}")
        webcam = None

    session = GameSession()
    send_lock = asyncio.Lock()

    print(f"[main] connecting to {url} ...")
    try:
        async with websockets.connect(url, max_size=None) as ws:
            print("[main] connected")

            tasks = [
                asyncio.create_task(frame_loop_task(d435, webcam, ws, fps, jpeg_q, send_lock)),
                asyncio.create_task(serial_reader_task(serial_port, baud, ws, session, send_lock)),
            ]
            await _stop.wait()

            # 종료 시 진행 중 게임 있으면 STOP 송신
            if session.is_active():
                sid = session.stop()
                try:
                    async with send_lock:
                        await ws.send(json.dumps({"event": "STOP", "session_id": sid}))
                    print(f"[main] sent final STOP: {sid}")
                except Exception:
                    pass

            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        if webcam is not None:
            webcam.release()
        d435.stop()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="ws[s]://<AI 서버>:<port>/ws/camera")
    p.add_argument("--serial", required=True, help="Arduino 시리얼 디바이스 (예: /dev/ttyACM0)")
    p.add_argument("--baud", type=int, default=115200, help="Arduino BAUD (기본 115200)")
    p.add_argument("--webcam", default="0", help="웹캠 인덱스 또는 /dev/v4l/by-id/... path")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--jpeg-quality", type=int, default=80)
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
