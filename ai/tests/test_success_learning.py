import json
import time

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

    learner.begin_attempt("session-1")
    learner.remember_attempt("session-1", _candidate(), depth, 0.67)
    learner.freeze_attempt("session-1")
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

    learner.begin_attempt("session-2")
    learner.remember_attempt("session-2", _candidate(0.2), None, 0.4)
    learner.remember_attempt("session-2", _candidate(0.9), None, 0.8)
    learner.freeze_attempt("session-2")
    learner.complete_attempt("session-2", success=False)

    row = json.loads((tmp_path / "attempts.jsonl").read_text(encoding="utf-8"))
    assert row["features"][-5] == pytest.approx(0.9)
    assert row["predicted_probability"] == 0.8
    assert row["success"] == 0


def _learner(tmp_path):
    return AutoSuccessLearner(str(tmp_path/"attempts.jsonl"), str(tmp_path/"model.pth"),
                              ChickEvaluator(jaw_count=3, extractor=SuccessFeatureExtractor()),
                              min_samples=100)


def test_grab_start_freezes_features_against_late_inference(tmp_path):
    learner = _learner(tmp_path)
    token = learner.begin_attempt("s")
    learner.remember_attempt("s", _candidate(0.2), None, 0.4, attempt_id=token)
    assert learner.freeze_attempt("s") == 0.4
    learner.remember_attempt("s", _candidate(0.9), None, 0.8, attempt_id=token)
    learner.complete_attempt("s", True)
    row = json.loads(learner.data_path.read_text())
    assert row["features"][-5] == pytest.approx(0.2)
    assert row["predicted_probability"] == 0.4
    learner.remember_attempt("s", _candidate(0.9), None, 0.8, attempt_id=token)
    assert "s" not in learner._pending


@pytest.mark.parametrize("case", ["unknown", "not_frozen", "stale", "no_observation"])
def test_ineligible_attempts_are_never_added_to_training(tmp_path, case):
    learner = _learner(tmp_path)
    learner.begin_attempt("s")
    if case != "no_observation":
        learner.remember_attempt("s", _candidate(), None, 0.6,
                                 observed_at=time.monotonic()-3 if case == "stale" else None)
    if case != "not_frozen":
        learner.freeze_attempt("s")
    assert not learner.complete_attempt("s", False, outcome_valid=case != "unknown")
    assert learner.dataset_stats().total == 0
    assert "s" not in learner._contexts


def test_previous_round_inference_cannot_contaminate_reused_session(tmp_path):
    learner = _learner(tmp_path)
    old = learner.begin_attempt("s")
    new = learner.begin_attempt("s")
    learner.remember_attempt("s", _candidate(0.9), None, 0.9, attempt_id=old)
    learner.remember_attempt("s", _candidate(0.2), None, 0.4, attempt_id=new)
    learner.freeze_attempt("s")
    learner.complete_attempt("s", True)
    row = json.loads(learner.data_path.read_text())
    assert row["attempt_id"] == new
    assert row["features"][-5] == pytest.approx(0.2)


def test_session_partition_is_preserved_after_restart_and_configuration_change(tmp_path):
    learner = _learner(tmp_path)
    learner.begin_attempt("same-session")
    learner.remember_attempt("same-session", _candidate(), None, 0.5)
    learner.freeze_attempt("same-session")
    learner.complete_attempt("same-session", True)
    original = json.loads(learner.data_path.read_text())["dataset_role"]
    second = AutoSuccessLearner(str(learner.data_path), str(learner.model_path), learner.evaluator,
                               min_samples=100, holdout_ratio=0.99 if original == "train" else 0.001)
    second.begin_attempt("same-session")
    second.remember_attempt("same-session", _candidate(), None, 0.5)
    second.freeze_attempt("same-session")
    second.complete_attempt("same-session", False)
    rows = [json.loads(line) for line in learner.data_path.read_text().splitlines()]
    assert {r["dataset_role"] for r in rows} == {original}
