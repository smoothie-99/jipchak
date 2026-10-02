import hashlib
import json
import os
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import numpy as np

from three_jaw_grasp.candidate import GraspCandidate
from three_jaw_grasp.dataset import load_attempts
from three_jaw_grasp.evaluator import ThreeJawEvaluator
from three_jaw_grasp.trainer import train_evaluator_model
from .model_store import ModelStore
from .promotion import PromotionPolicy, compare_models


@dataclass(frozen=True)
class DatasetStats:
    total: int = 0
    success: int = 0
    failure: int = 0


@dataclass
class _PendingAttempt:
    features: list[float]
    predicted_probability: float
    metadata: dict[str, Any]
    observed_at: float


@dataclass
class _AttemptContext:
    attempt_id: str
    frozen: bool = False


class AutoSuccessLearner:
    """Collect pre-grab observations; evaluate candidates before installing them."""

    def __init__(
        self, data_path: str, model_path: str, evaluator: ThreeJawEvaluator,
        enabled: bool = True, min_samples: int = 30, retrain_every: int = 10,
        min_class_samples: int = 5, epochs: int = 120, batch_size: int = 32,
        holdout_ratio: float = 0.2, max_observation_age: float = 2.0,
        promotion_policy: Optional[PromotionPolicy] = None,
    ) -> None:
        self.data_path, self.model_path = Path(data_path), Path(model_path)
        self.evaluator = evaluator
        self.extractor = evaluator.extractor
        self.enabled = enabled
        self.min_samples = max(4, int(min_samples))
        self.retrain_every = max(1, int(retrain_every))
        self.min_class_samples = max(1, int(min_class_samples))
        self.epochs, self.batch_size = max(1, int(epochs)), max(1, int(batch_size))
        if not 0 < holdout_ratio < 1 or not np.isfinite(max_observation_age) or max_observation_age <= 0:
            raise ValueError("invalid holdout ratio or observation age")
        self.holdout_ratio, self.max_observation_age = holdout_ratio, max_observation_age
        self.promotion_policy = promotion_policy or PromotionPolicy()
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.store = ModelStore(self.model_path)
        self.recovery_source = self.store.recover(evaluator)
        self.audit_path = self.model_path.with_name(self.model_path.name + ".promotions.jsonl")
        self._pending: dict[str, _PendingAttempt] = {}
        self._contexts: dict[str, _AttemptContext] = {}
        self._session_roles = {r["session_id"]: r["dataset_role"]
                               for r in load_attempts(self.data_path, self.extractor.FEATURE_DIM)
                               if r.get("session_id")}
        self._data_lock = threading.RLock()
        self._training_lock = threading.Lock()
        self._training = False
        self._training_thread: Optional[threading.Thread] = None
        self._last_evaluated_count = int(evaluator.model_metadata.get(
            "observed_count", evaluator.model_metadata.get("sample_count", 0)))
        self.last_promotion: dict = {}
        if self.audit_path.exists():
            for line in self.audit_path.read_text(encoding="utf-8").splitlines():
                try:
                    report = json.loads(line)
                    self._last_evaluated_count = max(self._last_evaluated_count, int(report["observed_count"]))
                    self.last_promotion = report
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    continue

    @property
    def training(self) -> bool:
        with self._training_lock:
            return self._training

    def begin_attempt(self, session_id: str, attempt_id: Optional[str] = None) -> str:
        attempt_id = attempt_id or uuid4().hex
        with self._data_lock:
            self._pending.pop(session_id, None)
            self._contexts[session_id] = _AttemptContext(attempt_id)
        return attempt_id

    def remember_attempt(
        self, session_id: str, candidate: GraspCandidate, depth: Optional[np.ndarray],
        predicted_probability: float, metadata: Optional[dict[str, Any]] = None,
        observed_at: Optional[float] = None, attempt_id: Optional[str] = None,
    ) -> None:
        if not self.enabled or not session_id:
            return
        features = self.extractor.extract(candidate, depth)
        timestamp = time.monotonic() if observed_at is None else float(observed_at)
        if (features.shape != (self.extractor.FEATURE_DIM,) or not np.isfinite(features).all()
                or not np.isfinite(predicted_probability) or not 0 <= predicted_probability <= 1
                or not np.isfinite(timestamp)):
            return
        with self._data_lock:
            context = self._contexts.get(session_id)
            if context is None or context.frozen or (attempt_id is not None and context.attempt_id != attempt_id):
                return
            previous = self._pending.get(session_id)
            if previous is not None and timestamp < previous.observed_at:
                return
            self._pending[session_id] = _PendingAttempt(
                features.astype(float).tolist(), float(predicted_probability),
                dict(metadata or {}), timestamp)

    def freeze_attempt(self, session_id: str) -> Optional[float]:
        """GRAB_START freezes the last completed, recent observation."""
        with self._data_lock:
            context = self._contexts.get(session_id)
            if context is None:
                return None
            if not context.frozen:
                context.frozen = True
                pending = self._pending.get(session_id)
                if pending is not None and not 0 <= time.monotonic()-pending.observed_at <= self.max_observation_age:
                    self._pending.pop(session_id, None)
            pending = self._pending.get(session_id)
            return pending.predicted_probability if pending else None

    def discard_attempt(self, session_id: str) -> None:
        with self._data_lock:
            self._pending.pop(session_id, None)
            self._contexts.pop(session_id, None)

    def complete_attempt(
        self, session_id: str, success: bool, *, outcome_valid: bool = True,
        outcome_metadata: Optional[dict] = None,
    ) -> bool:
        if not self.enabled:
            self.discard_attempt(session_id)
            return False
        with self._data_lock:
            context = self._contexts.pop(session_id, None)
            attempt = self._pending.pop(session_id, None)
            if not outcome_valid or context is None or not context.frozen or attempt is None:
                return False
            # Whole sessions stay on one side; legacy rows without a role remain training-only.
            fraction = int(hashlib.sha256(session_id.encode()).hexdigest()[:16], 16) / 2**64
            role = self._session_roles.setdefault(
                session_id, "promotion" if fraction < self.holdout_ratio else "train")
            entry = {
                "schema_version": 2, "attempt_id": context.attempt_id, "session_id": session_id,
                "dataset_role": role, "features": attempt.features, "success": int(bool(success)),
                "outcome_valid": True, "predicted_probability": attempt.predicted_probability,
                "feature_dim": self.extractor.FEATURE_DIM,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {**attempt.metadata, **(outcome_metadata or {})},
            }
            with self.data_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        return self.start_retraining_if_needed()

    def dataset_stats(self, role: Optional[str] = None) -> DatasetStats:
        with self._data_lock:
            rows = load_attempts(self.data_path, self.extractor.FEATURE_DIM)
        return self._stats(rows, role)

    @staticmethod
    def _stats(rows, role=None):
        selected = [r for r in rows if role is None or r["dataset_role"] == role]
        success = sum(r["success"] for r in selected)
        return DatasetStats(len(selected), success, len(selected)-success)

    def start_retraining_if_needed(self) -> bool:
        stats = self.dataset_stats()
        with self._training_lock:
            if self._training or not self._is_trainable(stats):
                return False
            self._training = True
            self._training_thread = threading.Thread(
                target=self._train_worker, name="jipchak-success-trainer", daemon=True)
            self._training_thread.start()
        return True

    def _is_trainable(self, stats: DatasetStats) -> bool:
        return (self.enabled and stats.total >= self.min_samples
                and min(stats.success, stats.failure) >= self.min_class_samples
                and (self._last_evaluated_count == 0
                     or stats.total-self._last_evaluated_count >= self.retrain_every))

    def _train_worker(self) -> None:
        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
        candidate_path = self.store.versions_dir / (version + ".pth")
        snapshot_path = self.data_path.with_name(f".{self.data_path.name}.{uuid4().hex}.snapshot")
        observed_count = self._last_evaluated_count
        report = {"model_version": version, "promoted": False, "reasons": []}
        try:
            with self._data_lock:
                shutil.copyfile(self.data_path, snapshot_path)
            rows = load_attempts(snapshot_path, self.extractor.FEATURE_DIM)
            stats = self._stats(rows, "train")
            observed_count = len(rows)
            if stats.total < self.min_samples or min(stats.success, stats.failure) < self.min_class_samples:
                report["reasons"] = ["insufficient_training_data"]
                return
            baseline = self.evaluator.snapshot_model()
            train_evaluator_model(
                data_path=str(snapshot_path), save_path=str(candidate_path),
                epochs=self.epochs, batch_size=self.batch_size,
                feature_dim=self.extractor.FEATURE_DIM,
                metadata={**asdict(stats), "sample_count": stats.total, "observed_count": observed_count,
                          "model_version": version, "feature_dim": self.extractor.FEATURE_DIM,
                          "trained_at": datetime.now(timezone.utc).isoformat()})
            candidate = self.evaluator.prepare_model(str(candidate_path))
            holdout = [r for r in rows if r["dataset_role"] == "promotion"]
            if baseline is None:
                if any(r["metadata"].get("prediction_source") != "rule" for r in holdout):
                    report["reasons"] = ["rule_baseline_unavailable"]
                    return
                rule_scores = np.asarray([r.get("predicted_probability", np.nan) for r in holdout])
                baseline_predict = lambda x: rule_scores
                baseline_version = "rule_observed"
            else:
                baseline_predict = lambda x: self.evaluator.predict_features(x, baseline)
                baseline_version = baseline.metadata.get("model_version", "legacy")
            report.update(compare_models(
                holdout, lambda x: self.evaluator.predict_features(x, candidate),
                baseline_predict, self.promotion_policy))
            report["baseline_version"] = baseline_version
            if report["promoted"]:
                # All candidate checks run before any serving disk or memory mutation.
                report["promoted"] = False
                self._append_report({**report, "phase": "approved_for_install",
                                     "observed_count": observed_count,
                                     "evaluated_at": datetime.now(timezone.utc).isoformat()})
                self.store.install(candidate_path, self.evaluator, candidate)
                report["promoted"] = True
        except Exception as exc:
            report["promoted"] = False
            report["reasons"] = ["training_or_install_failed"]
            report["error"] = str(exc)
        finally:
            snapshot_path.unlink(missing_ok=True)
            report.update({"observed_count": observed_count, "phase": "finished",
                           "evaluated_at": datetime.now(timezone.utc).isoformat()})
            try:
                self._append_report(report)
            except OSError as exc:
                report["audit_error"] = str(exc)
            finally:
                with self._training_lock:
                    # Failed/rejected candidates also advance the cursor, preventing retry storms.
                    self._last_evaluated_count = observed_count
                    self.last_promotion = report
                    self._training = False
            print(f"[AutoSuccessLearner] promotion: {version} accepted={report['promoted']} reasons={report['reasons']}")

    def _append_report(self, report: dict) -> None:
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(report, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def wait_for_training(self, timeout: Optional[float] = None) -> None:
        thread = self._training_thread
        if thread is not None:
            thread.join(timeout=timeout)
