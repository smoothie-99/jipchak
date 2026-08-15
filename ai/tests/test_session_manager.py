from typing import Optional

import numpy as np
import pytest

from src.inference.judge import CatchJudge, JudgeResult
from src.session_manager import SessionManager


class FakeRecorder:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.frames_written: dict[str, int] = {}
        self.fail_start = False

    def start_session(self, session_id: str, shape) -> str:
        if self.fail_start:
            raise RuntimeError("disk full")
        self.started.append(session_id)
        self.frames_written[session_id] = 0
        return f"/tmp/{session_id}.mp4"

    def write(self, session_id: str, frame) -> None:
        if session_id in self.frames_written:
            self.frames_written[session_id] += 1

    def stop_session(self, session_id: str) -> Optional[str]:
        if session_id in self.started:
            self.stopped.append(session_id)
            return f"/tmp/{session_id}.mp4"
        return None


class FakeSpring:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bool, str | None]] = []
        self.response = {"id": 42}

    async def upload_game_log(self, video_path: str, is_success: bool, session_id: str | None = None):
        self.uploads.append((video_path, is_success, session_id))
        return self.response

    async def close(self):
        pass


class FixedJudge(CatchJudge):
    def __init__(self, is_caught: bool) -> None:
        super().__init__()
        self._fixed = is_caught

    def judge(self, color_frame=None, depth_frame=None, first_depth_frame=None) -> JudgeResult:
        return JudgeResult(is_caught=self._fixed, confidence=1.0, method="fixed")


def _color() -> np.ndarray:
    return (np.random.rand(60, 80, 3) * 255).astype(np.uint8)


def _depth() -> np.ndarray:
    return (np.random.rand(60, 80) * 1000).astype(np.uint16)


@pytest.fixture
def parts():
    rec = FakeRecorder()
    spring = FakeSpring()
    judge = FixedJudge(is_caught=True)
    sm = SessionManager(recorder=rec, judge=judge, spring=spring)
    return sm, rec, spring


async def test_full_lifecycle_records_judges_and_uploads(parts):
    sm, rec, spring = parts
    await sm.start("s1")
    await sm.on_frame("s1", _color(), _depth())
    await sm.on_frame("s1", _color(), _depth())
    resp = await sm.stop("s1")

    assert resp == {"id": 42}
    assert rec.started == ["s1"]
    assert rec.frames_written["s1"] == 2
    assert rec.stopped == ["s1"]
    assert spring.uploads == [("/tmp/s1.mp4", True, "s1")]


async def test_on_frame_without_session_is_noop(parts):
    sm, rec, _ = parts
    await sm.on_frame("never-started", _color(), _depth())
    assert rec.started == []


async def test_on_frame_with_empty_session_id_is_noop(parts):
    sm, rec, _ = parts
    await sm.on_frame(None, _color(), _depth())
    await sm.on_frame("", _color(), _depth())
    assert rec.started == []


async def test_stop_unknown_session_returns_none(parts):
    sm, _, spring = parts
    result = await sm.stop("ghost")
    assert result is None
    assert spring.uploads == []


async def test_duplicate_start_closes_previous(parts):
    sm, rec, _ = parts
    await sm.start("dup")
    await sm.on_frame("dup", _color(), None)
    await sm.start("dup")  # 재시작
    await sm.on_frame("dup", _color(), None)
    await sm.stop("dup")

    # 첫 세션의 stop_session이 한번 호출되었어야 함 (중복 START 시점)
    assert rec.stopped.count("dup") == 2  # 첫 START 정리 + 마지막 STOP


async def test_recorder_failure_skips_subsequent_writes(parts):
    sm, rec, spring = parts
    rec.fail_start = True
    await sm.start("bad")
    await sm.on_frame("bad", _color(), _depth())
    await sm.on_frame("bad", _color(), _depth())

    assert rec.started == []
    assert rec.frames_written == {}


async def test_judge_lose_uploads_with_false_flag(parts):
    sm, _, spring = parts
    sm._judge = FixedJudge(is_caught=False)

    await sm.start("loser")
    await sm.on_frame("loser", _color(), _depth())
    await sm.stop("loser")

    assert spring.uploads == [("/tmp/loser.mp4", False, "loser")]
