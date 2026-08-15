import asyncio
import signal
import sys
import time

from src.camera.astra import AstraCamera
from src.camera.webcam import WebcamCamera
from src.network.ws_client import WebSocketClient
from src.utils.packer import FramePacker

async def stream_loop(cam_3d: AstraCamera, cam_2d: WebcamCamera, ws_client: WebSocketClient):
    """카메라 프레임을 지속적으로 읽고 압축하여 전송하는 루프"""
    print("[Main] Starting stream loop...")
    frames_sent = 0
    start_time = time.time()

    while True:
        try:
            # 1. 프레임 캡처 (3D + 2D)
            color_3d, depth_3d = cam_3d.get_frames()
            color_2d, _ = cam_2d.get_frames()

            if color_2d is None and color_3d is None and depth_3d is None:
                await asyncio.sleep(0.01)
                continue

            # 2. 데이터 압축 및 직렬화
            payload_bytes = FramePacker.pack(color_2d, color_3d, depth_3d)

            if payload_bytes:
                # 3. 서버 전송
                sent = await ws_client.send_binary(payload_bytes)
                if sent:
                    frames_sent += 1

            # FPS 계산 및 출력 (100프레임마다)
            if frames_sent % 100 == 0 and frames_sent > 0:
                elapsed = time.time() - start_time
                fps = frames_sent / elapsed
                print(f"[Main] Streaming... FPS: {fps:.2f}")
                frames_sent = 0
                start_time = time.time()

            # 비동기 양보 (다른 태스크가 실행될 수 있도록)
            await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Main] Error in stream loop: {e}")
            await asyncio.sleep(1)

async def main():
    print("[Main] Initializing RPi Streaming Module...")

    # 카메라 변경시 변경
    cam_3d = AstraCamera()
    cam_2d = WebcamCamera()
    ws_client = WebSocketClient()

    # 종료 시그널 처리를 위한 이벤트
    stop_event = asyncio.Event()

    def signal_handler():
        print("\n[Main] Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, signal_handler)

    try:
        # 카메라 시작
        cam_3d.start()
        cam_2d.start()

        # WebSocket 연결 태스크와 스트리밍 태스크를 병렬 실행
        ws_task = asyncio.create_task(ws_client.connect())
        stream_task = asyncio.create_task(stream_loop(cam_3d, cam_2d, ws_client))

        # 종료 이벤트 대기
        await stop_event.wait()

    finally:
        print("[Main] Shutting down...")
        # 태스크 취소
        if 'stream_task' in locals() and not stream_task.done():
            stream_task.cancel()
        if 'ws_task' in locals() and not ws_task.done():
            ws_task.cancel()

        # 리소스 해제
        await ws_client.stop()
        cam_3d.stop()
        cam_2d.stop()
        print("[Main] Exited gracefully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
