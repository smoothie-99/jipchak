from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class JudgeResult:
    is_caught: bool
    confidence: float       # 0.0 ~ 1.0
    method: str             # 'depth_diff' | 'dummy'


class CatchJudge:
    """
    인형이 잡혔는지 depth 변화로 판정한다.

    원리:
      세션 시작 시 첫 depth (인형 있는 상태) 와
      세션 종료 시 마지막 depth 를 비교.
      인형이 빠져나간 영역은 depth 값이 커짐 (카메라 → 바닥까지 거리 증가).
      일정 픽셀 이상에서 depth가 threshold_mm 이상 증가하면 성공 판정.
    """

    def __init__(
        self,
        threshold_mm: float = 30.0,
        min_changed_pixels: int = 500,
        roi_margin: float = 0.15,
    ) -> None:
        self.threshold_mm = threshold_mm
        self.min_changed_pixels = min_changed_pixels
        self.roi_margin = roi_margin

    def judge(
        self,
        color_frame: Optional[np.ndarray] = None,
        depth_frame: Optional[np.ndarray] = None,
        first_depth_frame: Optional[np.ndarray] = None,
    ) -> JudgeResult:
        if first_depth_frame is None or depth_frame is None:
            return JudgeResult(is_caught=False, confidence=0.0, method="dummy")

        first = first_depth_frame.astype(np.float32)
        last = depth_frame.astype(np.float32)

        if first.shape != last.shape:
            return JudgeResult(is_caught=False, confidence=0.0, method="dummy")

        h, w = first.shape[:2]
        m = self.roi_margin
        y0, y1 = int(h * m), int(h * (1 - m))
        x0, x1 = int(w * m), int(w * (1 - m))

        roi_first = first[y0:y1, x0:x1]
        roi_last = last[y0:y1, x0:x1]

        valid = (roi_first > 0) & (roi_last > 0)
        if valid.sum() < 100:
            return JudgeResult(is_caught=False, confidence=0.0, method="depth_diff")

        diff = roi_last[valid] - roi_first[valid]

        changed = (diff > self.threshold_mm).sum()
        total_valid = valid.sum()
        ratio = float(changed) / float(total_valid)

        is_caught = int(changed) >= self.min_changed_pixels
        confidence = min(ratio * 5.0, 1.0)

        return JudgeResult(
            is_caught=is_caught,
            confidence=round(confidence, 3),
            method="depth_diff",
        )
