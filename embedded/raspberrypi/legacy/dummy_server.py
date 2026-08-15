import asyncio
import websockets
import msgpack
import lz4.frame
import cv2
import numpy as np
import time

async def stream_handler(websocket, path="/ws/camera"):
    print(f"[Client Connected] {websocket.remote_address}")

    try:
        async for message in websocket:
            start_time = time.time()

            # 1. MessagePack 언패킹
            payload = msgpack.unpackb(message)
            process_time = (time.time() - start_time) * 1000
            print(f"Frame received! Timestamp: {payload[b'timestamp']}, Processing Time: {process_time:.2f}ms")

            # 2. 2D RGB 복원
            if b'color_2d' in payload:
                bytes_2d = payload[b'color_2d']
                frame_2d = cv2.imdecode(np.frombuffer(bytes_2d, dtype=np.uint8), cv2.IMREAD_COLOR)
                cv2.imshow("Dummy Server: 2D Color", frame_2d)

            # 3. 3D RGB 복원
            if b'color_3d' in payload:
                bytes_3d = payload[b'color_3d']
                frame_3d = cv2.imdecode(np.frombuffer(bytes_3d, dtype=np.uint8), cv2.IMREAD_COLOR)
                cv2.imshow("Dummy Server: 3D Color", frame_3d)

            # 4. 3D Depth 복원
            depth_compressed = payload.get(b'depth_3d', b'')
            depth_shape = tuple(payload.get(b'depth_3d_shape', ()))

            if depth_compressed and depth_shape:
                depth_decompressed = lz4.frame.decompress(depth_compressed)
                depth_frame = np.frombuffer(depth_decompressed, dtype=np.uint16).reshape(depth_shape)

                depth_colormap = cv2.normalize(depth_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                depth_colormap = cv2.applyColorMap(depth_colormap, cv2.COLORMAP_JET)
                cv2.imshow("Dummy Server: 3D Depth", depth_colormap)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except websockets.exceptions.ConnectionClosed:
        print(f"[Client Disconnected]")
    finally:
        cv2.destroyAllWindows()

async def main():
    print("Starting Dummy WebSocket Server on ws://0.0.0.0:8000 ...")
    # max_size=None으로 설정하여 대용량 프레임 수신 시 문제 없도록 함
    server = await websockets.serve(stream_handler, "0.0.0.0", 8000, max_size=None)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
