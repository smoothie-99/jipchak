import os
from pathlib import Path

import cv2
import numpy as np
import pytest


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    """RECORDING_DIR을 tmp_path로 가로채서 격리된 테스트 환경 구성."""
    monkeypatch.setenv("RECORDING_DIR", str(tmp_path))
    # 모듈 캐시 무력화: src.config 가 이미 import 됐을 수 있으므로 강제 재로딩
    import importlib

    import src.config
    import src.recorder.video_recorder as vr_mod

    importlib.reload(src.config)
    importlib.reload(vr_mod)
    return vr_mod.VideoRecorder()


def _frame(h=60, w=80) -> np.ndarray:
    return (np.random.rand(h, w, 3) * 255).astype(np.uint8)


def test_start_write_stop_creates_mp4(recorder, tmp_path):
    sid = "session-abc"
    frame = _frame()
    recorder.start_session(sid, frame.shape)
    for _ in range(10):
        recorder.write(sid, frame)
    path = recorder.stop_session(sid)

    assert path is not None
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0
    assert path.endswith(".mp4")


def test_write_before_start_is_silently_ignored(recorder):
    # 세션 시작 안 한 상태에서 write가 들어와도 예외 없이 무시되어야 함
    recorder.write("ghost", _frame())
    assert not recorder.is_recording("ghost")


def test_stop_unknown_session_returns_none(recorder):
    assert recorder.stop_session("not-exist") is None


def test_duplicate_start_session_restarts_cleanly(recorder):
    sid = "dup"
    f = _frame()
    recorder.start_session(sid, f.shape)
    recorder.write(sid, f)
    # 두 번째 start: 기존 writer 닫고 새로 시작해야 함
    recorder.start_session(sid, f.shape)
    recorder.write(sid, f)
    path = recorder.stop_session(sid)
    assert path is not None
    assert Path(path).exists()
