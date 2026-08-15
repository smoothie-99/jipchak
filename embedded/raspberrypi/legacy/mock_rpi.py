"""
RPi 없이 ai 서버를 단독 검증하기 위한 모의 송신기.

흐름:
  1. ws://<host>/ws/camera 로 연결
  2. {"event":"START","session_id":"..."} 텍스트 전송
  3. N 프레임 동안 더미 RGB+Depth 를 FramePacker 형식으로 보냄
  4. {"event":"STOP","session_id":"..."} 전송 후 종료

사용 예:
  python -m ai.scripts.mock_rpi --url ws://localhost:8000/ws/camera --frames 60
또는 ai/ 안에서:
  python scripts/mock_rpi.py --url ws://localhost:8000/ws/camera --frames 60
"""
import argparse
import asyncio
import time
import uuid

import cv2
import lz4.frame
import msgpack
import numpy as np
import websockets


def make_payload(idx: int, h: int = 240, w: int = 320) -> bytes:
    """RPi의 FramePacker가 만드는 페이로드와 동일한 포맷."""
    # 시간에 따라 색이 변하는 더미 영상
    color = np.zeros((h, w, 3), dtype=np.uint8)
    color[:, :] = [(idx * 5) % 255, (idx * 7) % 255, (idx * 11) % 255]
    cv2.putText(color, f"frame {idx}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    ok2d, jpeg2d = cv2.imencode(".jpg", color, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    ok3d, jpeg3d = cv2.imencode(".jpg", color, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

    depth = (np.random.rand(h, w) * 1000).astype(np.uint16)
    depth_lz4 = lz4.frame.compress(depth.tobytes())

    payload = {
        "timestamp": time.time_ns(),
        "color_2d": jpeg2d.tobytes() if ok2d else b"",
        "color_3d": jpeg3d.tobytes() if ok3d else b"",
        "depth_3d": depth_lz4,
        "depth_3d_shape": depth.shape,
    }
    return msgpack.packb(payload)


async def run(url: str, frames: int, fps: int) -> None:
    session_id = f"mock-{uuid.uuid4().hex[:8]}"
    interval = 1.0 / fps
    print(f"[mock_rpi] connecting to {url} ...")

    async with websockets.connect(url, max_size=None) as ws:
        print(f"[mock_rpi] connected, session_id={session_id}")

        await ws.send(f'{{"event":"START","session_id":"{session_id}"}}')
        print(f"[mock_rpi] sent START")

        start = time.time()
        for i in range(frames):
            await ws.send(make_payload(i))
            await asyncio.sleep(interval)
        elapsed = time.time() - start
        print(f"[mock_rpi] sent {frames} frames in {elapsed:.2f}s "
              f"({frames / elapsed:.1f} fps)")

        await ws.send(f'{{"event":"STOP","session_id":"{session_id}"}}')
        print(f"[mock_rpi] sent STOP, closing")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://localhost:8000/ws/camera")
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--fps", type=int, default=30)
    args = p.parse_args()
    asyncio.run(run(args.url, args.frames, args.fps))


if __name__ == "__main__":
    main()
