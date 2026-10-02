"""Shared validation for training, dataset counts and promotion evaluation."""
import json
from pathlib import Path

import numpy as np


def load_attempts(path: str | Path, feature_dim: int) -> list[dict]:
    rows = []
    seen = set()
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            features = np.asarray(row["features"], dtype=np.float32)
            label = row["success"]
            if features.shape != (feature_dim,) or not np.isfinite(features).all():
                continue
            if label not in (0, 1) or row.get("outcome_valid", True) is not True:
                continue
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("judge_method") == "dummy":
                continue
            if any(value is not None and not isinstance(value, str)
                   for value in (row.get("session_id"), row.get("attempt_id"))):
                continue
            role = row.get("dataset_role", "train")
            if role not in ("train", "promotion"):
                continue
            # Only records reserved prospectively by the new collector are hold-out.
            if role == "promotion" and row.get("schema_version") != 2:
                continue
            attempt_id = row.get("attempt_id")
            if attempt_id and attempt_id in seen:
                continue
            if attempt_id:
                seen.add(attempt_id)
            rows.append({**row, "features": features, "success": int(label),
                         "dataset_role": role, "metadata": metadata})
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
            continue
    training_sessions = {r.get("session_id") for r in rows if r["dataset_role"] == "train"}
    return [r for r in rows if r["dataset_role"] == "train"
            or not r.get("session_id") or r["session_id"] not in training_sessions]
