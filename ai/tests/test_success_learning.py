import json

import numpy as np
import pytest

from src.learning import AutoSuccessLearner
from three_jaw_grasp.candidate import GraspCandidate
from three_jaw_grasp.evaluator_chick import ChickEvaluator
from three_jaw_grasp.success_feature_extractor import SuccessFeatureExtractor


def _candidate(distance_ratio: float = 0.4) -> GraspCandidate:
    mask = np.zeros((80, 100), dtype=np.uint8)
    mask[10:70, 20:80] = 1
    return GraspCandidate(
        center_x=50.0,
        center_y=35.0,
        center_z=0.3,
        width=50.0,
        angle=0.2,
        original_score=0.85,
        mask=mask,
        raw={"gripper_distance_ratio": distance_ratio},
    )


def test_feature_extractor_contains_center_distance():
    features = SuccessFeatureExtractor().extract(
        _candidate(distance_ratio=0.73),
        np.ones((80, 100), dtype=np.float32) * 0.4,
    )

    assert features.shape == (SuccessFeatureExtractor.FEATURE_DIM,)
    assert features[-5] == np.float32(0.73)


def test_outcome_is_appended_with_last_prediction(tmp_path):
    evaluator = ChickEvaluator(jaw_count=3, extractor=SuccessFeatureExtractor())
    learner = AutoSuccessLearner(
        data_path=str(tmp_path / "attempts.jsonl"),
        model_path=str(tmp_path / "model.pth"),
        evaluator=evaluator,
        min_samples=100,
    )
    depth = np.ones((80, 100), dtype=np.float32) * 0.4

    learner.remember_attempt("session-1", _candidate(), depth, 0.67)
    started = learner.complete_attempt("session-1", success=True)

    assert started is False
    rows = [
        json.loads(line)
        for line in (tmp_path / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["success"] == 1
    assert rows[0]["predicted_probability"] == 0.67
    assert len(rows[0]["features"]) == SuccessFeatureExtractor.FEATURE_DIM
    assert learner.dataset_stats().total == 1


def test_only_latest_attempt_per_session_is_labeled(tmp_path):
    evaluator = ChickEvaluator(jaw_count=3, extractor=SuccessFeatureExtractor())
    learner = AutoSuccessLearner(
        data_path=str(tmp_path / "attempts.jsonl"),
        model_path=str(tmp_path / "model.pth"),
        evaluator=evaluator,
        min_samples=100,
    )

    learner.remember_attempt("session-2", _candidate(0.2), None, 0.4)
    learner.remember_attempt("session-2", _candidate(0.9), None, 0.8)
    learner.complete_attempt("session-2", success=False)

    row = json.loads((tmp_path / "attempts.jsonl").read_text(encoding="utf-8"))
    assert row["features"][-5] == pytest.approx(0.9)
    assert row["predicted_probability"] == 0.8
    assert row["success"] == 0
