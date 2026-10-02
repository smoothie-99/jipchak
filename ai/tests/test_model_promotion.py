import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest
import torch

from src.learning import AutoSuccessLearner
from src.learning.model_store import ModelStore
from src.learning.promotion import PromotionPolicy, compare_models
from three_jaw_grasp.dataset import load_attempts
from three_jaw_grasp.evaluator import GraspScoreMLP, ThreeJawEvaluator
from three_jaw_grasp.success_feature_extractor import SuccessFeatureExtractor
from three_jaw_grasp.trainer import GraspDataset, train_evaluator_model, _fit_isotonic


def checkpoint(path, kind="good", version="test", **extra):
    model = GraspScoreMLP(16)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        if kind != "constant":
            model.net[0].weight[0, 0] = 1
            model.net[3].weight[0, 0] = 1
            model.net[5].weight[0, 0] = 6 if kind == "good" else -6
            model.net[5].bias[0] = -3 if kind == "good" else 3
    data = {"state_dict": model.state_dict(), "feature_dim": 16,
            "norm_mean": [0.0]*16, "norm_std": [1.0]*16,
            "metadata": {"model_version": version}, **extra}
    torch.save(data, path)
    return Path(path)


def records(role, n=40):
    return [{"features": [float(i % 2)] + [0.0]*15, "success": i % 2,
             "session_id": f"{role}-{i}", "attempt_id": f"{role}-{i}",
             "schema_version": 2, "dataset_role": role, "outcome_valid": True,
             "metadata": {"prediction_source": "rule", "doll_type": "chick"},
             "predicted_probability": 0.5} for i in range(n)]


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def learner_fixture(tmp_path, baseline=False):
    data, active = tmp_path/"attempts.jsonl", tmp_path/"active.pth"
    write_rows(data, records("train") + records("promotion"))
    if baseline:
        checkpoint(active, "constant", "baseline")
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    learner = AutoSuccessLearner(str(data), str(active), evaluator, epochs=1)
    return learner, evaluator, data, active


def test_shared_parser_excludes_bad_labels_nonfinite_features_and_holdout_from_training(tmp_path):
    path = tmp_path/"data.jsonl"
    valid = records("train", 4)
    corrupt = [{**valid[0], "attempt_id": "invalid-label", "success": 2},
               {**valid[0], "attempt_id": "invalid-float", "features": [float("nan")]*16},
               {**valid[0], "attempt_id": "dummy", "metadata": {"judge_method": "dummy"}},
               {**valid[0], "attempt_id": "unknown", "outcome_valid": False}]
    write_rows(path, valid + corrupt + records("promotion", 4) + [valid[0]])
    with path.open("a") as stream:
        stream.write("not JSON\n")
    assert len(load_attempts(path, 16)) == 8
    assert len(GraspDataset.from_jsonl(str(path), 16)) == 4


def test_legacy_records_never_become_holdout_and_sessions_cannot_leak(tmp_path):
    path = tmp_path/"data.jsonl"
    old = {"session_id": "legacy", "features": [0.0]*16, "success": 0}
    holdout = {**records("promotion", 1)[0], "session_id": "legacy"}
    forged = {**records("promotion", 2)[1], "schema_version": 1}
    write_rows(path, [old, holdout, forged])
    assert [r["dataset_role"] for r in load_attempts(path, 16)] == ["train"]


def test_models_replay_their_own_normalization_without_changing_serving(tmp_path):
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    old_path = checkpoint(tmp_path/"old.pth", "constant", "old")
    candidate_path = checkpoint(tmp_path/"candidate.pth", norm_mean=[1.0] + [0.0]*15)
    assert evaluator.load_model(str(old_path))
    candidate = evaluator.prepare_model(str(candidate_path))
    assert evaluator.model_metadata["model_version"] == "old"
    values = np.zeros((2, 16), dtype=np.float32)
    values[1, 0] = 2
    assert evaluator.predict_features(values, candidate)[0] < 0.1
    assert evaluator.predict_features(values, candidate)[1] > 0.9
    assert np.allclose(evaluator.predict_features(values), 0.5)


def test_prediction_source_does_not_change_mid_prediction_during_first_promotion(tmp_path, monkeypatch):
    from tests.test_success_learning import _candidate
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    prepared = evaluator.prepare_model(str(checkpoint(tmp_path/"candidate.pth")))
    def rule(candidate, depth):
        evaluator.activate_model(prepared)
        return 0.4
    monkeypatch.setattr(evaluator, "_calculate_rule_score", rule)
    assert evaluator.predict_with_source(_candidate()) == (0.4, "rule", "rule")
    assert evaluator.prediction_source == "ml"


def test_prediction_version_is_consistent_when_new_model_activates_during_inference(tmp_path, monkeypatch):
    from tests.test_success_learning import _candidate
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    evaluator.load_model(str(checkpoint(tmp_path/"old.pth", "constant", "old")))
    prepared = evaluator.prepare_model(str(checkpoint(tmp_path/"candidate.pth", version="new")))
    original = evaluator.predict_features
    def predict(features, state):
        evaluator.activate_model(prepared)
        return original(features, state)
    monkeypatch.setattr(evaluator, "predict_features", predict)
    probability, source, version = evaluator.predict_with_source(_candidate())
    assert probability == pytest.approx(0.5)
    assert (source, version) == ("ml", "old")
    assert evaluator.model_metadata["model_version"] == "new"


@pytest.mark.parametrize("extra", [
    {"norm_std": [0.0]*16}, {"norm_mean": [float("nan")]*16},
    {"norm_mean": [0.0]}, {"feature_dim": 11},
    {"iso_x": [0.8, 0.2], "iso_y": [0.0, 1.0]},
    {"iso_x": [-0.1, 1.1], "iso_y": [0.0, 1.0]},
    {"iso_x": [0.0, 1.0], "iso_y": [0.8, 0.2]},
    {"sigmoid": [float("nan"), 0.0]},
])
def test_invalid_candidate_never_replaces_serving(tmp_path, extra):
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    old = checkpoint(tmp_path/"old.pth", "constant", "old")
    bad = checkpoint(tmp_path/"bad.pth", **extra)
    assert evaluator.load_model(str(old))
    assert not evaluator.load_model(str(bad))
    assert evaluator.model_metadata["model_version"] == "old"


def test_better_candidate_is_promoted_and_previous_model_survives_restart(tmp_path, monkeypatch):
    learner, evaluator, _, active = learner_fixture(tmp_path, baseline=True)
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model",
                        lambda **kw: checkpoint(kw["save_path"], version=kw["metadata"]["model_version"]))
    assert learner.start_retraining_if_needed()
    learner.wait_for_training(5)
    assert not learner.training
    assert learner.last_promotion["promoted"]
    assert learner.last_promotion["sample_count"] == 40
    assert learner.last_promotion["baseline_version"] == "baseline"
    assert evaluator.model_metadata["model_version"] != "baseline"
    restarted = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    assert restarted.load_model(str(active))
    assert restarted.model_metadata == evaluator.model_metadata
    assert learner.store.previous_path.exists()


def test_first_model_compares_against_collected_rule_predictions(tmp_path, monkeypatch):
    learner, evaluator, _, _ = learner_fixture(tmp_path)
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model",
                        lambda **kw: checkpoint(kw["save_path"]))
    learner.start_retraining_if_needed()
    learner.wait_for_training(5)
    assert learner.last_promotion["promoted"]
    assert learner.last_promotion["baseline_version"] == "rule_observed"
    assert evaluator.prediction_source == "ml"


def test_worse_candidate_is_rejected_and_not_retried_on_same_data_after_restart(tmp_path, monkeypatch):
    learner, evaluator, data, active = learner_fixture(tmp_path, baseline=True)
    before = active.read_bytes()
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model",
                        lambda **kw: checkpoint(kw["save_path"], "bad"))
    learner.start_retraining_if_needed()
    learner.wait_for_training(5)
    assert not learner.last_promotion["promoted"]
    assert "brier_not_improved" in learner.last_promotion["reasons"]
    assert active.read_bytes() == before
    assert evaluator.model_metadata["model_version"] == "baseline"
    assert not learner.start_retraining_if_needed()
    restarted = AutoSuccessLearner(str(data), str(active), evaluator)
    assert not restarted.start_retraining_if_needed()


def test_training_failure_keeps_existing_disk_and_memory(tmp_path, monkeypatch):
    learner, evaluator, _, active = learner_fixture(tmp_path, baseline=True)
    before = active.read_bytes()
    def fail(**kwargs):
        raise RuntimeError("training crashed")
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model", fail)
    learner.start_retraining_if_needed()
    learner.wait_for_training(5)
    assert learner.last_promotion["reasons"] == ["training_or_install_failed"]
    assert active.read_bytes() == before
    assert evaluator.model_metadata["model_version"] == "baseline"
    assert not learner.training


def test_failed_memory_switch_restores_previous_disk_and_memory(tmp_path, monkeypatch):
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    active = checkpoint(tmp_path/"active.pth", "constant", "old")
    candidate = checkpoint(tmp_path/"candidate.pth", version="new")
    store = ModelStore(active)
    store.recover(evaluator)
    original = evaluator.activate_model
    def fail_new(state):
        if state and state.metadata.get("model_version") == "new":
            raise RuntimeError("activation failed")
        original(state)
    monkeypatch.setattr(evaluator, "activate_model", fail_new)
    before = active.read_bytes()
    with pytest.raises(RuntimeError):
        store.install(candidate, evaluator)
    assert active.read_bytes() == before
    assert evaluator.model_metadata["model_version"] == "old"
    restarted = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    assert ModelStore(active).recover(restarted) == "active"
    assert restarted.model_metadata["model_version"] == "old"


def test_restart_recovers_corrupt_active_from_previous_and_supports_rollback(tmp_path):
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    active = checkpoint(tmp_path/"active.pth", "constant", "old")
    new = checkpoint(tmp_path/"new.pth", version="new")
    store = ModelStore(active)
    store.recover(evaluator)
    store.install(new, evaluator)
    store.rollback(evaluator)
    assert evaluator.model_metadata["model_version"] == "old"
    active.write_bytes(b"broken checkpoint")
    restarted = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    assert ModelStore(active).recover(restarted) == "previous"
    assert restarted.model_metadata["model_version"] == "new"
    assert restarted.prepare_model(str(active)).metadata["model_version"] == "new"


def test_concurrent_triggers_start_only_one_training_job(tmp_path, monkeypatch):
    learner, _, _, _ = learner_fixture(tmp_path)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def train(**kwargs):
        calls.append(kwargs)
        entered.set()
        assert release.wait(5)
        checkpoint(kwargs["save_path"])
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model", train)
    assert learner.start_retraining_if_needed()
    assert entered.wait(3)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert not any(pool.map(lambda _: learner.start_retraining_if_needed(), range(20)))
        assert len(calls) == 1
    finally:
        release.set()
        learner.wait_for_training(5)


def test_training_snapshot_excludes_new_records_while_training(tmp_path, monkeypatch):
    learner, _, data, _ = learner_fixture(tmp_path)
    captured = []
    def train(**kwargs):
        snapshot = Path(kwargs["data_path"])
        with data.open("a") as stream:
            stream.write(json.dumps(records("train-new", 1)[0] | {"dataset_role": "train"}) + "\n")
        captured.append(len(load_attempts(snapshot, 16)))
        checkpoint(kwargs["save_path"])
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model", train)
    learner.start_retraining_if_needed()
    learner.wait_for_training(5)
    assert captured == [80]
    assert learner.last_promotion["observed_count"] == 80
    assert learner.dataset_stats().total == 81


def test_insufficient_or_correlated_holdout_blocks_promotion(tmp_path):
    path = tmp_path/"holdout.jsonl"
    write_rows(path, records("promotion", 20))
    rows = load_attempts(path, 16)
    perfect = lambda x: x[:, 0]
    constant = lambda x: np.full(len(x), 0.5)
    assert compare_models(rows, perfect, constant, PromotionPolicy())["reasons"] == ["insufficient_holdout"]
    write_rows(path, [{**r, "session_id": "one-session"} for r in records("promotion")])
    report = compare_models(load_attempts(path, 16), perfect, constant, PromotionPolicy())
    assert not report["promoted"]
    assert "improvement_uncertain" in report["reasons"]


def test_overconfident_errors_block_promotion_even_when_brier_improves(tmp_path):
    path = tmp_path/"holdout.jsonl"
    write_rows(path, records("promotion", 100))
    rows = load_attempts(path, 16)
    y = np.asarray([r["success"] for r in rows])
    candidate = np.where(y, 0.7, 0.3)
    candidate[np.flatnonzero(y == 0)[:5]] = 1.0
    report = compare_models(rows, lambda x: candidate, lambda x: np.full(len(x), 0.5), PromotionPolicy())
    assert report["brier_improvement"] > 0
    assert "log_loss_regressed" in report["reasons"]
    assert not report["promoted"]


def test_regressed_doll_group_blocks_overall_better_candidate(tmp_path):
    path = tmp_path/"holdout.jsonl"
    source = records("promotion", 200)
    for row in source[:16]:
        row["metadata"]["doll_type"] = "rare"
    write_rows(path, source)
    rows = load_attempts(path, 16)
    y = np.asarray([r["success"] for r in rows])
    baseline = np.full(len(y), 0.5)
    baseline[:16] = np.where(y[:16], 0.9, 0.1)
    candidate = np.where(y, 0.95, 0.05)
    candidate[:16] = np.where(y[:16], 0.8, 0.2)
    report = compare_models(rows, lambda x: candidate, lambda x: baseline, PromotionPolicy())
    assert report["brier_improvement"] > 0
    assert "slice_regressed:rare" in report["reasons"]
    assert not report["promoted"]


def test_audit_failure_blocks_install_without_stalling_training(tmp_path, monkeypatch):
    learner, evaluator, _, active = learner_fixture(tmp_path, baseline=True)
    before = active.read_bytes()
    monkeypatch.setattr("src.learning.success_learning.train_evaluator_model",
                        lambda **kw: checkpoint(kw["save_path"]))
    def fail(report):
        raise OSError("audit disk full")
    monkeypatch.setattr(learner, "_append_report", fail)
    learner.start_retraining_if_needed()
    learner.wait_for_training(5)
    assert not learner.training
    assert learner.last_promotion["reasons"] == ["training_or_install_failed"]
    assert active.read_bytes() == before
    assert evaluator.model_metadata["model_version"] == "baseline"


def test_real_training_reserves_holdout_and_skips_small_sample_calibration(tmp_path):
    data, out = tmp_path/"data.jsonl", tmp_path/"model.pth"
    # Deliberate extreme hold-out values must not enter training normalization.
    holdout = [{**r, "features": [99999.0]*16} for r in records("promotion")]
    write_rows(data, records("train") + holdout)
    result = train_evaluator_model(str(data), str(out), epochs=2, feature_dim=16)
    saved = torch.load(out, weights_only=True)
    assert result["sample_count"] == 40
    assert max(saved["norm_mean"]) <= 1
    assert saved["metadata"]["calibration_method"] == "none"
    assert "iso_x" not in saved and "sigmoid" not in saved
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    assert evaluator.load_model(str(out))


def test_calibrator_uses_a_separate_split_and_selects_sigmoid(tmp_path):
    data, out = tmp_path/"data.jsonl", tmp_path/"model.pth"
    write_rows(data, records("train", 200))
    train_evaluator_model(str(data), str(out), epochs=1, feature_dim=16, min_calibration_samples=10)
    saved = torch.load(out, weights_only=True)
    assert saved["metadata"]["calibration_method"] == "sigmoid"
    assert saved["metadata"]["calibration_samples"] == 20
    assert "sigmoid" in saved and "iso_x" not in saved
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    assert evaluator.load_model(str(out))
    assert np.isfinite(evaluator.predict_features(np.zeros((2, 16)))).all()


def test_isotonic_duplicate_scores_have_one_consistent_probability():
    x, y = _fit_isotonic(np.array([0.5, 0.5, 0.8]), np.array([0, 1, 1]))
    assert x.tolist() == [0.5, 0.8]
    assert y.tolist() == [0.5, 1.0]
