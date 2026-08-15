"""
Object Detection 서비스.
SSDLiteDetector 를 래핑하여 RGB 프레임에서 물체별 bounding box 를 반환한다.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class DetectedObject:
    bbox: Tuple[int, int, int, int]  # (xmin, ymin, xmax, ymax)
    score: float
    label: int


class DetectionService:

    def __init__(
        self,
        score_threshold: float = 0.35,
        target_labels: Optional[List[int]] = None,
        device: str = "cpu",
    ):
        self._threshold = score_threshold
        self._target_labels = target_labels
        self._device = device
        self._detector = None

    def load(self) -> None:
        from three_jaw_grasp.detector import SSDLiteDetector

        self._detector = SSDLiteDetector(
            score_threshold=self._threshold,
            target_labels=self._target_labels,
            device=self._device,
        )
        print("[DetectionService] loaded")

    @property
    def is_ready(self) -> bool:
        return self._detector is not None

    def detect(self, rgb: np.ndarray) -> List[DetectedObject]:
        if self._detector is None:
            return []

        results = self._detector.detect_all(rgb)
        return [
            DetectedObject(bbox=d.bbox, score=d.score, label=d.label)
            for d in results
        ]
