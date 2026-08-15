import numpy as np
from typing import Optional

from .candidate import GraspCandidate
from .feature_extractor import FeatureExtractor


class SuccessFeatureExtractor(FeatureExtractor):
    """실제 게임 결과 학습에 사용하는 3발 집게 전용 16차원 특징."""

    FEATURE_DIM = FeatureExtractor.FEATURE_DIM + 5

    def extract(
        self,
        grasp: GraspCandidate,
        depth: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        base = super().extract(grasp, depth)
        learned_context = np.asarray(
            [
                float(grasp.raw.get("gripper_distance_ratio", 0.0)),
                float(grasp.raw.get("top_bias", 0.0)),
                float(grasp.raw.get("neck_capture", 0.0)),
                float(grasp.raw.get("support", 0.0)),
                float(grasp.raw.get("clearance", 0.0)),
            ],
            dtype=np.float32,
        )
        return np.concatenate((base, learned_context))
