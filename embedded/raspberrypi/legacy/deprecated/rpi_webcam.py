"""
라즈베리파이 USB 웹캠으로 실제 영상을 캡처하여 AI 서버(/ws/camera)로 송신.

embedded/raspberrypi 폴더의 정식 코드(Astra/D435 + main.py)와는 별개로,
"WebSocket 영상 흐름이 실기에서 작동하는지" 만 빠르게 검증하기 위한 단일 파일 스크립트.

의존성 (RPi):
    pip install opencv-python-headless msgpack websockets numpy

사용 예 (RPi 에서):
    python3 rpi_webcam.py --url ws://<호스트IP>:8000/ws/camera
    python3 rpi_webcam.py --url ws://192.168.100.94:8000/ws/camera --device 0 --fps 30
"""
import argparse
import asyncio
import json
import signal
import time
import uuid

import cv2
import msgpack
import numpy as np
import websockets


_stop = asyncio.Event()


def _install_signal_handlers() -> None:
    """Ctrl+C 또는 SIGTERM 시 깔끔하게 종료."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop.set)
        except NotImplementedError:
            # Windows 등에서 add_signal_handler 미지원 → KeyboardInterrupt 로 처리
            pass


def _open_camera(device: int, width: int, height: int, fps: int) -> cv2.VideoCapture:
    # V4L2 backend 명시: 자동 선택은 RPi 환경에서 FFMPEG 로 fallback 후 실패할 수 있음
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"웹캠을 열 수 없습니다 (device={device}).")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[rpi_webcam] camera opened: {actual_w}x{actual_h} @ {actual_fps:.1f} fps")
    return cap


def _pack(frame_bgr: np.ndarray, jpeg_quality: int) -> bytes | None:
    """FramePacker 와 동일 포맷으로 color_2d 만 채워서 송신."""
    ok, jpg = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        return None
    payload = {
        "timestamp": time.time_ns(),
        "color_2d": jpg.tobytes(),
        # color_3d / depth_3d 는 비움 (D435 미사용)
        "depth_3d": b"",
        "depth_3d_shape": (),
    }
    return msgpack.packb(payload)


async def run(url: str, device: int, width: int, height: int, fps: int, jpeg_q: int) -> None:
    cap = _open_camera(device, width, height, fps)
    interval = 1.0 / max(fps, 1)
    session_id = f"rpi-{uuid.uuid4().hex[:8]}"

    print(f"[rpi_webcam] connecting to {url} ...")
    try:
        async with websockets.connect(url, max_size=None) as ws:
            print(f"[rpi_webcam] connected, session_id={session_id}")
            await ws.send(json.dumps({"event": "START", "session_id": session_id}))

            sent = 0
            t_start = time.time()

            while not _stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    print("[rpi_webcam] frame read failed, retrying ...")
                    await asyncio.sleep(0.1)
                    continue

                payload = _pack(frame, jpeg_q)
                if payload is not None:
                    try:
                        await ws.send(payload)
                        sent += 1
                    except websockets.ConnectionClosed:
                        print("[rpi_webcam] ws closed by server")
                        break

                # FPS 로그 (100 프레임마다)
                if sent and sent % 100 == 0:
                    elapsed = time.time() - t_start
                    print(f"[rpi_webcam] sent {sent} frames ({sent / elapsed:.1f} fps)")

                await asyncio.sleep(interval)

            # 종료 시 STOP 신호
            try:
                await ws.send(json.dumps({"event": "STOP", "session_id": session_id}))
                print(f"[rpi_webcam] sent STOP, total={sent}")
            except Exception:
                pass

    finally:
        cap.release()
        print("[rpi_webcam] camera released, bye")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="ws://<AI 서버 호스트>:8000/ws/camera")
    p.add_argument("--device", type=int, default=0, help="웹캠 인덱스 (기본 0)")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--jpeg-quality", type=int, default=80)
    args = p.parse_args()

    async def _main() -> None:
        _install_signal_handlers()
        await run(args.url, args.device, args.width, args.height, args.fps, args.jpeg_quality)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
