import cv2
import lz4.frame
import msgpack
import time
import numpy as np
from typing import Tuple, Optional

from ..config import JPEG_QUALITY

class FramePacker:
    """프레임을 압축하고 전송용 바이트로 패킹하는 클래스"""

    @staticmethod
    def pack(color_2d: Optional[np.ndarray], color_3d: Optional[np.ndarray], depth_3d: Optional[np.ndarray]) -> Optional[bytes]:
        """세 채널 영상 압축(JPEG/LZ4) 후 msgpack 직렬화 반환"""
        try:
            payload = {"timestamp": time.time_ns()}

            # 2D camera RGB 압축 (JPEG)
            if color_2d is not None:
                success, encoded_2d = cv2.imencode('.jpg', color_2d, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                if success:
                    payload["color_2d"] = encoded_2d.tobytes()

            # 3D camera RGB 압축 (JPEG)
            if color_3d is not None:
                success, encoded_3d = cv2.imencode('.jpg', color_3d, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                if success:
                    payload["color_3d"] = encoded_3d.tobytes()

            # 3D camera Depth 압축 (LZ4)
            if depth_3d is not None:
                payload["depth_3d"] = lz4.frame.compress(depth_3d.tobytes())
                payload["depth_3d_shape"] = depth_3d.shape
            else:
                payload["depth_3d"] = b""
                payload["depth_3d_shape"] = ()

            # 최소한 1개의 이미지
            if "color_2d" not in payload and "color_3d" not in payload and payload["depth_3d"] == b"":
                return None

            return msgpack.packb(payload)

        except Exception as e:
            print(f"[FramePacker] Error during packing: {e}")
            return None
