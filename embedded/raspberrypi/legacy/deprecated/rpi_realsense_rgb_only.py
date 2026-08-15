"""
rpi_realsense.py — WS 영상 흐름 빠른 검증용 RGB-only 송신 스크립트

목적: D435 + 웹캠 → AI 서버 까지의 WebSocket 흐름이 동작하는지 단순 검증.
운영 환경 (Arduino 게임 트리거 + Depth 분석 포함) 은 rpi_full.py 사용.

검증 전용 최적화:
    - D435 의 Depth stream 비활성화 (RGB color stream 만 enable)
    - rs.align 미사용 (Depth 없으니 정렬 불필요)
    - payload["depth_3d"] 항상 빈값 (LZ4 압축 비용 0)
    - 결과: CPU/USB 대역폭/네트워크 페이로드 크기 모두 절감

채널 매핑 (rpi_full.py 와 동일):
    - payload["color_2d"]  ← 일반 USB 웹캠   → 브라우저 Cam1 (★ 녹화 대상)
    - payload["color_3d"]  ← D435 RGB        → 브라우저 Cam2

세션 모델:
    - 단일 세션 (WS 연결 = 한 게임). 연결 시 자동 START, Ctrl+C 시 자동 STOP.
    - 다중 게임 / Arduino 트리거가 필요하면 rpi_full.py 사용.

의존성 (RPi):
    pip install opencv-python-headless msgpack websockets numpy
    (lz4 / pyserial 불필요 — 운영용 rpi_full.py 에만 필요)
    pyrealsense2 는 librealsense2 빌드 후 venv 에 직접 복사된 상태 가정.

사용 예:
    python3 rpi_realsense.py \
        --url ws://192.168.100.94:8000/ws/camera \
        --webcam '/dev/v4l/by-id/usb-Web_Camera_Web_Camera_240729163401-video-index0' \
        --width 640 --height 480 --fps 30
"""
import argparse
import asyncio
import json
import signal
import time
import uuid
from typing import Optional

import cv2
import msgpack
import numpy as np
import pyrealsense2 as rs
import websockets


_stop = asyncio.Event()


def _install_signal_handlers() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop.set)
        except NotImplementedError:
            pass


# ---------- D435 (RGB only) ----------

class RealSensePipeline:
    """D435 의 color stream 만 enable. Depth stream / align 없음 (검증 전용 단순화)."""

    def __init__(self, width: int, height: int, fps: int) -> None:
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        # ★ Depth stream 비활성화 — 검증엔 RGB 만 있으면 충분, 자원 절감
        self.pipeline.start(config)
        print(f"[d435] started (RGB-only): {width}x{height} @ {fps} fps")

    def get_color(self) -> Optional[np.ndarray]:
        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
            color = frames.get_color_frame()
            if not color:
                return None
            return np.asanyarray(color.get_data())
        except Exception as e:
            print(f"[d435] frame read error: {e}")
            return None

    def stop(self) -> None:
        try:
            self.pipeline.stop()
        except Exception:
            pass
        print("[d435] stopped")


# ---------- 일반 USB 웹캠 (cv2) ----------

class WebcamCapture:
    """V4L2 backend 명시 + by-id path 지원."""

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


# ---------- 페이로드 패킹 (RGB only) ----------

def _encode_jpeg(frame: Optional[np.ndarray], quality: int) -> bytes:
    if frame is None:
        return b""
    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpg.tobytes() if ok else b""


def _pack(d435_color: Optional[np.ndarray],
          webcam_color: Optional[np.ndarray],
          jpeg_q: int) -> Optional[bytes]:
    payload = {
        "timestamp": time.time_ns(),
        # 고정 매핑: 웹캠 → Cam1 (color_2d, 녹화 대상), D435 → Cam2 (color_3d)
        "color_2d": _encode_jpeg(webcam_color, jpeg_q),
        "color_3d": _encode_jpeg(d435_color, jpeg_q),
        # 검증 전용: depth 송신 안 함. 운영용 rpi_full.py 만 LZ4 depth 채움.
        "depth_3d": b"",
        "depth_3d_shape": (),
    }
    if not payload["color_2d"] and not payload["color_3d"]:
        return None
    return msgpack.packb(payload)


# ---------- 메인 루프 ----------

async def run(url: str, webcam_dev, width: int, height: int, fps: int, jpeg_q: int) -> None:
    d435 = RealSensePipeline(width, height, fps)
    try:
        webcam = WebcamCapture(webcam_dev, width, height, fps)
    except RuntimeError as e:
        print(f"[main] webcam disabled: {e}")
        webcam = None

    interval = 1.0 / max(fps, 1)
    session_id = f"rpi-{uuid.uuid4().hex[:8]}"

    print(f"[main] connecting to {url} ...")
    try:
        async with websockets.connect(url, max_size=None) as ws:
            print(f"[main] connected, session_id={session_id}")
            await ws.send(json.dumps({"event": "START", "session_id": session_id}))

            sent = 0
            t_start = time.time()

            while not _stop.is_set():
                d435_color = d435.get_color()
                webcam_color = webcam.read() if webcam else None

                payload = _pack(d435_color, webcam_color, jpeg_q)
                if payload is not None:
                    try:
                        await ws.send(payload)
                        sent += 1
                    except websockets.ConnectionClosed:
                        print("[main] ws closed by server")
                        break

                if sent and sent % 100 == 0:
                    elapsed = time.time() - t_start
                    print(f"[main] sent {sent} frames ({sent / elapsed:.1f} fps)")

                await asyncio.sleep(interval)

            try:
                await ws.send(json.dumps({"event": "STOP", "session_id": session_id}))
                print(f"[main] sent STOP, total={sent}")
            except Exception:
                pass

    finally:
        if webcam is not None:
            webcam.release()
        d435.stop()


def main() -> None:
    p = argparse.ArgumentParser(description="WS 영상 흐름 검증용 RGB-only 송신 스크립트")
    p.add_argument("--url", required=True, help="ws://<AI 서버>:8000/ws/camera")
    p.add_argument("--webcam", default="0",
                   help="일반 웹캠 인덱스 또는 /dev/v4l/by-id/... path (없으면 D435 만 송신)")
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
        await run(args.url, webcam_dev, args.width, args.height, args.fps, args.jpeg_quality)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
