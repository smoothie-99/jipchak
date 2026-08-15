import cv2
import lz4.frame
import msgpack
import numpy as np

from src.stream.unpacker import FrameUnpacker


def _pack(payload: dict) -> bytes:
    """RPi의 FramePacker가 만드는 페이로드를 그대로 흉내낸다."""
    return msgpack.packb(payload)


def _make_jpeg(h: int, w: int) -> bytes:
    img = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _make_depth_lz4(h: int, w: int) -> tuple[bytes, tuple]:
    depth = (np.random.rand(h, w) * 1000).astype(np.uint16)
    return lz4.frame.compress(depth.tobytes()), depth.shape


def test_unpack_full_payload_returns_all_three_frames():
    h, w = 60, 80
    depth_buf, depth_shape = _make_depth_lz4(h, w)
    payload = _pack({
        "timestamp": 12345,
        "color_2d": _make_jpeg(h, w),
        "color_3d": _make_jpeg(h, w),
        "depth_3d": depth_buf,
        "depth_3d_shape": depth_shape,
    })

    frame = FrameUnpacker.unpack(payload)

    assert frame is not None
    assert frame.timestamp_ns == 12345
    assert frame.color_2d.shape == (h, w, 3)
    assert frame.color_3d.shape == (h, w, 3)
    assert frame.depth_3d.shape == (h, w)
    assert frame.depth_3d.dtype == np.uint16


def test_unpack_color_only_payload():
    h, w = 30, 40
    payload = _pack({
        "timestamp": 1,
        "color_2d": _make_jpeg(h, w),
        "depth_3d": b"",
        "depth_3d_shape": (),
    })

    frame = FrameUnpacker.unpack(payload)

    assert frame is not None
    assert frame.color_2d is not None
    assert frame.color_3d is None
    assert frame.depth_3d is None


def test_unpack_empty_payload_returns_none():
    payload = _pack({
        "timestamp": 0,
        "depth_3d": b"",
        "depth_3d_shape": (),
    })

    assert FrameUnpacker.unpack(payload) is None


def test_unpack_garbage_returns_none():
    assert FrameUnpacker.unpack(b"\x00\x01\x02not-msgpack") is None
