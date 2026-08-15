import numpy as np

from src.inference.judge import CatchJudge


def test_fallback_dummy_when_no_depth():
    judge = CatchJudge()
    result = judge.judge()
    assert result.is_caught is False
    assert result.method == "dummy"


def test_fallback_dummy_when_only_last_depth():
    judge = CatchJudge()
    result = judge.judge(
        depth_frame=np.ones((480, 640), dtype=np.uint16) * 500,
    )
    assert result.is_caught is False
    assert result.method == "dummy"


def test_caught_when_depth_increases():
    """인형이 빠져나가면 depth가 커짐 → 성공"""
    judge = CatchJudge(threshold_mm=20, min_changed_pixels=100)

    first = np.ones((480, 640), dtype=np.uint16) * 300
    last = np.ones((480, 640), dtype=np.uint16) * 300

    # 중앙 영역에서 depth 증가 (인형 없어짐)
    last[150:350, 200:450] = 400

    result = judge.judge(
        depth_frame=last,
        first_depth_frame=first,
    )
    assert result.is_caught is True
    assert result.method == "depth_diff"
    assert result.confidence > 0.0


def test_not_caught_when_depth_same():
    """depth 변화 없음 → 실패"""
    judge = CatchJudge(threshold_mm=20, min_changed_pixels=100)

    frame = np.ones((480, 640), dtype=np.uint16) * 300

    result = judge.judge(
        depth_frame=frame,
        first_depth_frame=frame.copy(),
    )
    assert result.is_caught is False
    assert result.method == "depth_diff"


def test_not_caught_when_change_too_small():
    """변화 영역이 min_changed_pixels 미만 → 실패"""
    judge = CatchJudge(threshold_mm=20, min_changed_pixels=5000)

    first = np.ones((480, 640), dtype=np.uint16) * 300
    last = first.copy()
    # 아주 작은 영역만 변화
    last[240:245, 320:325] = 400

    result = judge.judge(
        depth_frame=last,
        first_depth_frame=first,
    )
    assert result.is_caught is False
