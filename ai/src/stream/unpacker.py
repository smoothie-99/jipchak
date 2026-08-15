from dataclasses import dataclass
from typing import Optional

import cv2
import lz4.frame
import msgpack
import numpy as np


@dataclass
class UnpackedFrame:
    """RPi가 보낸 한 프레임을 디코딩한 결과"""
    timestamp_ns: int
    color_2d: Optional[np.ndarray]   # (H, W, 3) uint8 BGR (웹캠)
    color_3d: Optional[np.ndarray]   # (H, W, 3) uint8 BGR (D435 RGB)
    depth_3d: Optional[np.ndarray]   # (H, W)    uint16   (D435 Depth, mm 단위)


class FrameUnpacker:
    """
    embedded/raspberrypi/.../utils/packer.py::FramePacker 의 역방향.
    msgpack 바이너리를 받아 numpy ndarray 묶음으로 복원한다.
    """

    @staticmethod
    def unpack(payload_bytes: bytes) -> Optional[UnpackedFrame]:
        try:
            payload = msgpack.unpackb(payload_bytes, raw=True)
        except Exception as e:
            print(f"[FrameUnpacker] msgpack decode failed: {e}")
            return None

        timestamp_ns = int(payload.get(b"timestamp", 0))

        color_2d = FrameUnpacker._decode_jpeg(payload.get(b"color_2d"))
        color_3d = FrameUnpacker._decode_jpeg(payload.get(b"color_3d"))
        depth_3d = FrameUnpacker._decode_depth(
            payload.get(b"depth_3d", b""),
            tuple(payload.get(b"depth_3d_shape", ())),
        )

        if color_2d is None and color_3d is None and depth_3d is None:
            return None

        return UnpackedFrame(
            timestamp_ns=timestamp_ns,
            color_2d=color_2d,
            color_3d=color_3d,
            depth_3d=depth_3d,
        )

    @staticmethod
    def _decode_jpeg(buf: Optional[bytes]) -> Optional[np.ndarray]:
        if not buf:
            return None
        arr = np.frombuffer(buf, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    @staticmethod
    def _decode_depth(buf: bytes, shape: tuple) -> Optional[np.ndarray]:
        if not buf or not shape:
            return None
        try:
            raw = lz4.frame.decompress(buf)
            return np.frombuffer(raw, dtype=np.uint16).reshape(shape)
        except Exception as e:
            print(f"[FrameUnpacker] depth decompress failed: {e}")
            return None
