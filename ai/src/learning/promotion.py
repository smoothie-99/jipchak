"""Compare complete serving predictions on a reserved, versioned hold-out."""
import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class PromotionPolicy:
    min_samples: int = 30
    min_class_samples: int = 5
    min_session_groups: int = 5
    min_brier_improvement: float = 0.005
    max_log_loss_regression: float = 0.02
    min_slice_samples: int = 10
    max_slice_brier_regression: float = 0.02
    bootstrap_rounds: int = 500

    def __post_init__(self):
        if self.min_samples < 2 or self.min_class_samples < 1 or self.min_session_groups < 2:
            raise ValueError("promotion sample limits must be positive")
        if self.min_slice_samples < 1 or self.bootstrap_rounds < 100:
            raise ValueError("invalid slice or bootstrap limits")
        for value in (self.min_brier_improvement, self.max_log_loss_regression,
                      self.max_slice_brier_regression):
            if not np.isfinite(value) or value < 0:
                raise ValueError("promotion thresholds must be finite and nonnegative")


def probability_metrics(labels, probabilities) -> dict:
    y = np.asarray(labels, dtype=np.float64)
    p = np.asarray(probabilities, dtype=np.float64)
    if p.shape != y.shape or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("invalid probability predictions")
    clipped = np.clip(p, 1e-7, 1 - 1e-7)
    bins = []
    ece = 0.0
    bin_ids = np.minimum((p * 10).astype(int), 9)
    for i in range(10):
        mask = bin_ids == i
        if mask.any():
            predicted, actual = float(p[mask].mean()), float(y[mask].mean())
            ece += mask.mean() * abs(predicted - actual)
            bins.append({"bin": i, "count": int(mask.sum()),
                         "predicted": predicted, "actual": actual})
    return {"brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(clipped) + (1-y) * np.log(1-clipped))),
            "ece": float(ece), "calibration_bins": bins}


def compare_models(rows, candidate_predict, baseline_predict, policy: PromotionPolicy) -> dict:
    encoded = [{"attempt_id": r.get("attempt_id"), "session_id": r.get("session_id"),
                "features": r["features"].tolist(), "success": r["success"],
                "metadata": r["metadata"]} for r in rows]
    dataset_version = hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest()
    y = np.asarray([r["success"] for r in rows], dtype=np.float64)
    report = {"dataset_version": dataset_version, "sample_count": len(rows),
              "success": int(y.sum()), "failure": int(len(y)-y.sum()),
              "thresholds": asdict(policy), "promoted": False, "reasons": []}
    if len(rows) < policy.min_samples or min(report["success"], report["failure"]) < policy.min_class_samples:
        report["reasons"] = ["insufficient_holdout"]
        return report
    x = np.stack([r["features"] for r in rows])
    candidate = np.asarray(candidate_predict(x), dtype=np.float64)
    baseline = np.asarray(baseline_predict(x), dtype=np.float64)
    report["candidate"] = probability_metrics(y, candidate)
    report["baseline"] = probability_metrics(y, baseline)
    improvement = report["baseline"]["brier"] - report["candidate"]["brier"]
    report["brier_improvement"] = improvement
    # Session-level bootstrap avoids pretending rounds from the same session are independent.
    group_ids = [r.get("session_id") or r.get("attempt_id") or str(i) for i, r in enumerate(rows)]
    groups = list(dict.fromkeys(group_ids))
    errors = (baseline-y)**2 - (candidate-y)**2
    group_sums = np.asarray([errors[np.asarray(group_ids) == g].sum() for g in groups])
    group_counts = np.asarray([group_ids.count(g) for g in groups])
    rng = np.random.default_rng(0)
    draws = rng.integers(len(groups), size=(policy.bootstrap_rounds, len(groups)))
    changes = group_sums[draws].sum(axis=1) / group_counts[draws].sum(axis=1)
    ci = np.quantile(changes, [0.025, 0.975]).tolist()
    report["brier_improvement_ci95"] = ci
    if improvement < policy.min_brier_improvement:
        report["reasons"].append("brier_not_improved")
    report["session_groups"] = len(groups)
    if len(groups) < policy.min_session_groups or ci[0] <= 0:
        report["reasons"].append("improvement_uncertain")
    if report["candidate"]["log_loss"] > report["baseline"]["log_loss"] + policy.max_log_loss_regression:
        report["reasons"].append("log_loss_regressed")
    report["slices"] = {}
    for name in sorted({str(r["metadata"].get("doll_type", "unknown")) for r in rows}):
        if name == "unknown":
            continue
        mask = np.asarray([str(r["metadata"].get("doll_type", "unknown")) == name for r in rows])
        if mask.sum() < policy.min_slice_samples:
            continue
        delta = float(np.mean((candidate[mask]-y[mask])**2 - (baseline[mask]-y[mask])**2))
        report["slices"][name] = {"count": int(mask.sum()), "brier_regression": delta}
        if delta > policy.max_slice_brier_regression:
            report["reasons"].append(f"slice_regressed:{name}")
    report["promoted"] = not report["reasons"]
    return report
