"""
웹캠 + Intel RealSense D435 통합 스트리밍

최적화 포인트:
    - 웹캠 / D435 캡처를 각각 별도 스레드에서 실행 (블로킹 I/O 분리)
    - 메인 루프는 최신 프레임 가져와서 인코딩 + 전송만 담당
    - D435 wait_for_frames (블로킹) → 전용 스레드에서 처리
    - Depth는 2프레임에 1번만 전송 (용량 절감)

채널 매핑:
    color_2d ← 웹캠 RGB  (EC2 녹화 대상)
    color_3d ← D435 RGB  (브라우저 오버레이)
    depth_3d ← D435 Depth (집게 판정용, LZ4 압축)

사용:
    python3 main.py \
        --url wss://k14d108.p.ssafy.io/ws/camera \
        --webcam 0 \
        --send-fps 15
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
import websockets
from websockets.exceptions import ConnectionClosed


# ─────────────────────────────────────────
# D435 캡처 스레드
# ─────────────────────────────────────────

class RealSenseReader:
    """
    별도 스레드에서 D435 프레임을 지속적으로 캡처.
    메인 루프는 get_frames() 로 최신 프레임만 읽음.
    """

    def __init__(self, width: int, height: int, fps: int) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.latest_color: Optional[np.ndarray] = None
        self.latest_depth: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pipeline: Optional[rs.pipeline] = None
        self._align: Optional[rs.align] = None

    def start(self) -> None:
        self._pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
        self._pipeline.start(config)
        self._align = rs.align(rs.stream.color)
        print(f"[D435] started: {self.width}x{self.height} @ {self.fps}fps")

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        """D435 전용 캡처 루프 (블로킹 wait_for_frames 사용)."""
        while not self._stop.is_set():
            try:
                frames = self._pipeline.wait_for_frames(timeout_ms=1000)
                aligned = self._align.process(frames)
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
                    print(f"[D435] capture error: {e}")
                    time.sleep(0.1)

    def get_frames(self) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        with self._lock:
            return self.latest_color, self.latest_depth

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._pipeline:
            try:
                self._pipeline.stop()
            except Exception:
                pass
        print("[D435] stopped")


# ─────────────────────────────────────────
# 웹캠 캡처 스레드
# ─────────────────────────────────────────

class WebcamReader:
    """
    별도 스레드에서 웹캠 프레임을 지속적으로 캡처.
    메인 루프는 get_frame() 으로 최신 프레임만 읽음.
    """

    def __init__(self, device, width: int, height: int, fps: int) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.latest_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            raise RuntimeError(f"[Webcam] 열기 실패 (device={self.device})")

        # MJPEG 포맷: 고FPS + USB 대역폭 절감
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_w   = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h   = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
        print(f"[Webcam] started: {actual_w}x{actual_h} @ {actual_fps:.1f}fps (device={self.device})")

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            if self._cap is None:
                break
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            with self._lock:
                self.latest_frame = frame

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self.latest_frame

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
        print("[Webcam] stopped")


# ─────────────────────────────────────────
# WebSocket 클라이언트
# ─────────────────────────────────────────

class WebSocketClient:
    def __init__(self, url: str, retry_interval: float = 3.0) -> None:
        self.url = url
        self.retry_interval = retry_interval
        self.session_id = f"rpi-{uuid.uuid4().hex[:8]}"
        self._ws = None
        self._connected = False
        self._stop = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        while not self._stop:
            try:
                print(f"[WS] connecting to {self.url} ...")
                async with websockets.connect(self.url, max_size=None) as ws:
                    self._ws = ws
                    self._connected = True
                    print(f"[WS] connected | session={self.session_id}")
                    await ws.send(json.dumps({
                        "event": "START",
                        "session_id": self.session_id,
                    }))
                    await ws.wait_closed()
            except Exception as e:
                print(f"[WS] disconnected: {e}")
            finally:
                self._ws = None
                self._connected = False

            if not self._stop:
                print(f"[WS] retrying in {self.retry_interval}s ...")
                await asyncio.sleep(self.retry_interval)

    async def send(self, data: bytes) -> bool:
        if not self._connected or self._ws is None:
            return False
        try:
            await self._ws.send(data)
            return True
        except ConnectionClosed:
            self._connected = False
            return False
        except Exception as e:
            print(f"[WS] send error: {e}")
            return False

    async def stop(self) -> None:
        self._stop = True
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "event": "STOP",
                    "session_id": self.session_id,
                }))
                await self._ws.close()
            except Exception:
                pass
        print("[WS] stopped")


# ─────────────────────────────────────────
# 페이로드 패킹
# ─────────────────────────────────────────

def _encode_jpeg(frame: Optional[np.ndarray], quality: int) -> bytes:
    if frame is None:
        return b""
    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpg.tobytes() if ok else b""


def _pack(
    webcam_color: Optional[np.ndarray],
    d435_color: Optional[np.ndarray],
    d435_depth: Optional[np.ndarray],
    jpeg_quality: int,
    send_depth: bool = True,
) -> Optional[bytes]:
    color_2d = _encode_jpeg(webcam_color, jpeg_quality)
    color_3d = _encode_jpeg(d435_color, jpeg_quality)

    depth_3d = b""
    depth_3d_shape: tuple = ()
    if send_depth and d435_depth is not None:
        depth_3d = lz4.frame.compress(d435_depth.tobytes())
        depth_3d_shape = d435_depth.shape

    if not color_2d and not color_3d and not depth_3d:
        return None

    return msgpack.packb({
        "timestamp":      time.time_ns(),
        "color_2d":       color_2d,
        "color_3d":       color_3d,
        "depth_3d":       depth_3d,
        "depth_3d_shape": depth_3d_shape,
    })


# ─────────────────────────────────────────
# 메인 스트리밍 루프
# ─────────────────────────────────────────

async def stream_loop(
    d435: RealSenseReader,
    webcam: Optional[WebcamReader],
    ws: WebSocketClient,
    send_fps: int,
    jpeg_quality: int,
    depth_every: int,
) -> None:
    print("[Main] stream loop started")
    interval = 1.0 / max(send_fps, 1)
    frame_idx = 0
    sent = 0
    dropped = 0
    t_start = time.time()

    while True:
        try:
            loop_start = time.monotonic()

            # 연결 안 됐으면 대기
            if not ws.is_connected:
                await asyncio.sleep(0.05)
                continue

            # 스레드에서 캡처된 최신 프레임 가져오기
            d435_color, d435_depth = d435.get_frames()
            webcam_color = webcam.get_frame() if webcam else None

            # Depth는 depth_every 프레임마다 1번만 전송
            send_depth = (frame_idx % max(depth_every, 1) == 0)

            payload = _pack(webcam_color, d435_color, d435_depth, jpeg_quality, send_depth)
            if payload:
                ok = await ws.send(payload)
                sent += 1 if ok else 0
                dropped += 0 if ok else 1
            else:
                dropped += 1

            frame_idx += 1

            # FPS 로그 (100프레임마다)
            if sent > 0 and sent % 100 == 0:
                elapsed = time.time() - t_start
                print(f"[Main] sent={sent} dropped={dropped} fps={sent / elapsed:.1f}")
                sent = 0
                dropped = 0
                t_start = time.time()

            # FPS 유지
            elapsed_loop = time.monotonic() - loop_start
            await asyncio.sleep(max(interval - elapsed_loop, 0))

        except asyncio.CancelledError:
            print("[Main] stream loop cancelled")
            break
        except Exception as e:
            print(f"[Main] loop error: {e}")
            await asyncio.sleep(1)


# ─────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    print("[Main] starting...")

    d435 = RealSenseReader(args.d435_width, args.d435_height, args.d435_fps)
    d435.start()

    webcam = None
    if not args.no_webcam:
        try:
            device = int(args.webcam) if args.webcam.isdigit() else args.webcam
            webcam = WebcamReader(device, args.webcam_width, args.webcam_height, args.webcam_fps)
            webcam.start()
        except RuntimeError as e:
            print(f"[Main] webcam disabled: {e}")

    ws = WebSocketClient(url=args.url)

    stop_event = asyncio.Event()
    def _on_signal():
        print("\n[Main] shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            pass

    try:
        ws_task     = asyncio.create_task(ws.connect())
        stream_task = asyncio.create_task(
            stream_loop(d435, webcam, ws, args.send_fps, args.jpeg_quality, args.depth_every)
        )
        await stop_event.wait()

    finally:
        print("[Main] shutting down...")
        for task in (locals().get("stream_task"), locals().get("ws_task")):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await ws.stop()
        if webcam:
            webcam.stop()
        d435.stop()
        print("[Main] exited gracefully")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="웹캠 + D435 통합 스트리밍")
    p.add_argument("--url",           default="wss://k14d108.p.ssafy.io/ws/camera", help="EC2 WebSocket 주소 (기본: k14d108)")
    p.add_argument("--webcam",        default="0",         help="웹캠 장치 번호 (기본 0)")
    p.add_argument("--webcam-width",  type=int, default=640,  help="웹캠 너비 (기본 640)")
    p.add_argument("--webcam-height", type=int, default=480,  help="웹캠 높이 (기본 480)")
    p.add_argument("--webcam-fps",    type=int, default=30,   help="웹캠 FPS (기본 30)")
    p.add_argument("--d435-width",    type=int, default=640,  help="D435 너비 (기본 640)")
    p.add_argument("--d435-height",   type=int, default=480,  help="D435 높이 (기본 480)")
    p.add_argument("--d435-fps",      type=int, default=15,   help="D435 FPS (기본 15)")
    p.add_argument("--send-fps",      type=int, default=15,   help="전송 FPS (기본 15)")
    p.add_argument("--jpeg-quality",  type=int, default=60,   help="JPEG 품질 0~100 (기본 60)")
    p.add_argument("--depth-every",   type=int, default=2,    help="Depth 전송 주기 N프레임마다 1회 (기본 2)")
    p.add_argument("--no-webcam",     action="store_true",    help="웹캠 없이 D435만 전송")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass