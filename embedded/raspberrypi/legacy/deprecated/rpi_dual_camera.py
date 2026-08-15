"""
라즈베리파이에 USB 웹캠 + Intel RealSense D435 가 동시에 연결되어 있을 때,
두 카메라의 RGB 영상을 동시에 캡처하여 AI 서버(/ws/camera) 로 송신.

- 일반 웹캠   → payload["color_2d"]  (브라우저 Cam1)
- D435 RGB    → payload["color_3d"]  (브라우저 Cam2)

embedded/raspberrypi 의 정식 코드와는 별개의 빠른 검증용 단일 파일.
librealsense2(SDK) 없이 D435 를 일반 UVC 디바이스(cv2)로 다룬다.
즉 depth 는 못 받지만 RGB 는 즉시 됨.

의존성 (RPi):
    pip install opencv-python-headless msgpack websockets numpy

사용 예 (RPi 에서):
    python3 rpi_dual_camera.py \
        --url ws://192.168.100.94:8000/ws/camera \
        --webcam 0 \
        --d435 4 \
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
import msgpack
import numpy as np
import websockets


_stop = asyncio.Event()


def _install_signal_handlers() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop.set)
        except NotImplementedError:
            pass


def _open_camera(device, width: int, height: int, fps: int, label: str) -> Optional[cv2.VideoCapture]:
    # device 는 int (예: 8) 또는 str path (예: /dev/v4l/by-id/usb-Intel...) 둘 다 지원.
    # V4L2 backend 명시: 자동 선택은 RPi 환경에서 FFMPEG 로 fallback 후 실패할 수 있음.
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"[{label}] 카메라를 열 수 없습니다 (device={device}).")
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[{label}] opened: {actual_w}x{actual_h} @ {actual_fps:.1f} fps (device={device})")
    return cap


def _encode_jpeg(frame: Optional[np.ndarray], quality: int) -> bytes:
    if frame is None:
        return b""
    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpg.tobytes() if ok else b""


def _pack(frame_2d: Optional[np.ndarray], frame_3d: Optional[np.ndarray], q: int) -> Optional[bytes]:
    payload = {
        "timestamp": time.time_ns(),
        "color_2d": _encode_jpeg(frame_2d, q),
        "color_3d": _encode_jpeg(frame_3d, q),
        # depth 는 SDK 없이는 못 받으므로 빈 값
        "depth_3d": b"",
        "depth_3d_shape": (),
    }
    if not payload["color_2d"] and not payload["color_3d"]:
        return None
    return msgpack.packb(payload)


async def run(
    url: str,
    webcam_idx,
    d435_idx,
    width: int,
    height: int,
    fps: int,
    jpeg_q: int,
) -> None:
    cap_2d = _open_camera(webcam_idx, width, height, fps, "webcam")
    cap_3d = _open_camera(d435_idx, width, height, fps, "d435")

    if cap_2d is None and cap_3d is None:
        print("[rpi_dual] 두 카메라 모두 열기 실패. 종료.")
        return

    interval = 1.0 / max(fps, 1)
    session_id = f"rpi-{uuid.uuid4().hex[:8]}"

    print(f"[rpi_dual] connecting to {url} ...")
    try:
        async with websockets.connect(url, max_size=None) as ws:
            print(f"[rpi_dual] connected, session_id={session_id}")
            await ws.send(json.dumps({"event": "START", "session_id": session_id}))

            sent = 0
            t_start = time.time()

            while not _stop.is_set():
                frame_2d = None
                frame_3d = None

                if cap_2d is not None:
                    ok, f = cap_2d.read()
                    frame_2d = f if ok else None
                if cap_3d is not None:
                    ok, f = cap_3d.read()
                    frame_3d = f if ok else None

                payload = _pack(frame_2d, frame_3d, jpeg_q)
                if payload is not None:
                    try:
                        await ws.send(payload)
                        sent += 1
                    except websockets.ConnectionClosed:
                        print("[rpi_dual] ws closed by server")
                        break

                if sent and sent % 100 == 0:
                    elapsed = time.time() - t_start
                    print(f"[rpi_dual] sent {sent} frames ({sent / elapsed:.1f} fps)")

                await asyncio.sleep(interval)

            try:
                await ws.send(json.dumps({"event": "STOP", "session_id": session_id}))
                print(f"[rpi_dual] sent STOP, total={sent}")
            except Exception:
                pass

    finally:
        if cap_2d is not None:
            cap_2d.release()
        if cap_3d is not None:
            cap_3d.release()
        print("[rpi_dual] cameras released, bye")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="ws://<AI 서버>:8000/ws/camera")
    # 정수 인덱스(예: 0) 또는 path (예: /dev/v4l/by-id/usb-...) 둘 다 허용.
    # path 형태는 인덱스 변동에 영향 안 받아 안정적.
    p.add_argument("--webcam", default="0", help="웹캠 인덱스 또는 /dev/v4l/by-id/... path")
    p.add_argument("--d435", default="4", help="D435 RGB 인덱스 또는 /dev/v4l/by-id/... path")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--jpeg-quality", type=int, default=80)
    args = p.parse_args()

    # 숫자 문자열이면 int 로, 아니면 path 그대로 사용
    def _to_device(v):
        try:
            return int(v)
        except ValueError:
            return v

    webcam_dev = _to_device(args.webcam)
    d435_dev = _to_device(args.d435)

    async def _main() -> None:
        _install_signal_handlers()
        await run(
            args.url, webcam_dev, d435_dev,
            args.width, args.height, args.fps, args.jpeg_quality,
        )

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
