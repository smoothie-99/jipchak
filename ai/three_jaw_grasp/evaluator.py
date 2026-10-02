import math
import threading
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import torch
import torch.nn as nn
import yaml

from .candidate import GraspCandidate
from .factory import EvaluatorFactory
from .feature_extractor import FeatureExtractor


class GraspScoreMLP(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


@dataclass(frozen=True)
class PreparedModel:
    model: nn.Module
    norm_mean: Optional[np.ndarray]
    norm_std: Optional[np.ndarray]
    iso_x: Optional[np.ndarray]
    iso_y: Optional[np.ndarray]
    metadata: dict
    sigmoid: Optional[tuple[float, float]] = None


@EvaluatorFactory.register("default")
class ThreeJawEvaluator:
    def __init__(
        self,
        config_path: Optional[str] = None,
        model_path: Optional[str] = None,
        extractor: Optional[FeatureExtractor] = None,
        jaw_count: int = 3,
    ):
        self.extractor = extractor or FeatureExtractor()
        self.config = self._load_config(config_path)
        self.model = None
        self.jaw_count = max(2, int(jaw_count))
        # 학습 시 사용한 feature 정규화 통계 (없으면 정규화 안 함)
        self._norm_mean: Optional[np.ndarray] = None
        self._norm_std: Optional[np.ndarray] = None
        # Isotonic regression calibration mapping (sigmoid 출력 -> 진짜 확률)
        # 독립 calibration split으로 fit해 .pth에 저장. 없으면 raw sigmoid 사용.
        self._iso_x: Optional[np.ndarray] = None  # 정렬된 score boundary
        self._iso_y: Optional[np.ndarray] = None  # 각 boundary 의 평균 라벨 (단조)
        self._model_metadata: dict = {}
        self._sigmoid = None
        self._model_lock = threading.RLock()

        if model_path:
            self.load_model(model_path)

    @property
    def prediction_source(self) -> str:
        return "ml" if self.model is not None else "rule"

    @property
    def model_metadata(self) -> dict:
        with self._model_lock:
            return dict(self._model_metadata)

    def snapshot_model(self) -> Optional[PreparedModel]:
        with self._model_lock:
            if self.model is None:
                return None
            return PreparedModel(self.model, self._norm_mean, self._norm_std,
                                 self._iso_x, self._iso_y, dict(self._model_metadata),
                                 self._sigmoid)

    def prepare_model(self, model_path: str) -> PreparedModel:
        """Validate a candidate without changing serving state."""
        ckpt = torch.load(model_path, map_location="cpu", weights_only=True)
        model = GraspScoreMLP(self.extractor.FEATURE_DIM)
        mean = std = iso_x = iso_y = sigmoid = None
        metadata = {}
        if isinstance(ckpt, dict) and "state_dict" in ckpt:
            if int(ckpt.get("feature_dim", self.extractor.FEATURE_DIM)) != self.extractor.FEATURE_DIM:
                raise ValueError("feature_dim mismatch")
            model.load_state_dict(ckpt["state_dict"])
            if ("norm_mean" in ckpt) != ("norm_std" in ckpt):
                raise ValueError("incomplete normalization")
            if "norm_mean" in ckpt:
                mean = np.asarray(ckpt["norm_mean"], dtype=np.float32)
                std = np.asarray(ckpt["norm_std"], dtype=np.float32)
                if (mean.shape != (self.extractor.FEATURE_DIM,) or std.shape != mean.shape
                        or not np.isfinite(mean).all() or not np.isfinite(std).all()
                        or (std <= 0).any()):
                    raise ValueError("invalid normalization")
            if ("iso_x" in ckpt) != ("iso_y" in ckpt):
                raise ValueError("incomplete isotonic calibration")
            if "iso_x" in ckpt:
                iso_x = np.asarray(ckpt["iso_x"], dtype=np.float64)
                iso_y = np.asarray(ckpt["iso_y"], dtype=np.float64)
                if (iso_x.ndim != 1 or iso_x.size == 0 or iso_x.shape != iso_y.shape
                        or not np.isfinite(iso_x).all() or not np.isfinite(iso_y).all()
                        or (np.diff(iso_x) < 0).any() or (np.diff(iso_y) < 0).any()
                        or ((iso_x < 0) | (iso_x > 1)).any()
                        or ((iso_y < 0) | (iso_y > 1)).any()):
                    raise ValueError("invalid isotonic calibration")
            if "sigmoid" in ckpt:
                sigmoid = tuple(float(v) for v in ckpt["sigmoid"])
                if len(sigmoid) != 2 or not np.isfinite(sigmoid).all() or sigmoid[0] <= 0 or iso_x is not None:
                    raise ValueError("invalid sigmoid calibration")
            metadata = dict(ckpt.get("metadata", {}))
        else:
            model.load_state_dict(ckpt)
        if not all(torch.isfinite(v).all() for v in model.state_dict().values()):
            raise ValueError("nonfinite model weights")
        model.eval()
        prepared = PreparedModel(model, mean, std, iso_x, iso_y, metadata, sigmoid)
        self.predict_features(np.zeros((2, self.extractor.FEATURE_DIM)), prepared)
        return prepared

    def activate_model(self, prepared: Optional[PreparedModel]) -> None:
        """Switch all serving weights and preprocessing in one critical section."""
        with self._model_lock:
            self.model = prepared.model if prepared else None
            self._norm_mean = prepared.norm_mean if prepared else None
            self._norm_std = prepared.norm_std if prepared else None
            self._iso_x = prepared.iso_x if prepared else None
            self._iso_y = prepared.iso_y if prepared else None
            self._model_metadata = dict(prepared.metadata) if prepared else {}
            self._sigmoid = prepared.sigmoid if prepared else None

    def load_model(self, model_path: str) -> bool:
        """새 체크포인트를 완전히 검증한 뒤 추론 모델을 원자적으로 교체한다."""
        try:
            prepared = self.prepare_model(model_path)
            self.activate_model(prepared)
            print(
                f"[ThreeJawEvaluator] ML model loaded "
                f"(dim={self.extractor.FEATURE_DIM}, samples={prepared.metadata.get('sample_count', '?')})"
            )
            return True
        except Exception as exc:
            print(f"[ThreeJawEvaluator] model load skipped: {exc}")
            return False

    def select_best(
        self, candidates: List[GraspCandidate], depth: Optional[np.ndarray] = None
    ) -> GraspCandidate:
        if not candidates:
            raise ValueError("No grasp candidates to evaluate.")

        if self.model:
            scores = self._mlp_scores(candidates, depth)
        else:
            scores = [self._calculate_rule_score(c, depth) for c in candidates]

        best_idx = int(np.argmax(scores))
        return candidates[best_idx]

    def score_all(
        self, candidates: List[GraspCandidate], depth: Optional[np.ndarray] = None
    ) -> List[float]:
        if self.model:
            return list(self._mlp_scores(candidates, depth))
        return [self._calculate_rule_score(c, depth) for c in candidates]

    def success_probability(
        self, candidate: GraspCandidate, depth: Optional[np.ndarray] = None
    ) -> float:
        """학습 모델이 있으면 보정된 확률, 없으면 규칙 기반 초기 점수를 반환한다."""
        return self.predict_with_source(candidate, depth)[0]

    def predict_with_source(self, candidate: GraspCandidate, depth: Optional[np.ndarray] = None) -> tuple[float, str, str]:
        """Keep the probability, source and version consistent across a hot-reload."""
        prepared = self.snapshot_model()
        if prepared is None:
            return float(self._calculate_rule_score(candidate, depth)), "rule", "rule"
        features = self.extractor.extract(candidate, depth).reshape(1, -1)
        probability = float(self.predict_features(features, prepared)[0])
        return probability, "ml", str(prepared.metadata.get("model_version", "legacy"))

    def _width_fitness(self, g: GraspCandidate) -> float:
        spec = self.config["gripper"]
        if g.width < spec["min_width"] or g.width > spec["max_width"]:
            return 0.0
        sigma = (spec["max_width"] - spec["min_width"]) / 2.0
        return float(np.exp(-0.5 * ((g.width - spec["ideal_width"]) / sigma) ** 2))

    def _height_fitness(self, g: GraspCandidate) -> float:
        threshold = self.config["gripper"]["collision_threshold_z"]
        if g.center_z >= threshold:
            return 1.0
        if g.center_z <= 0:
            return 0.0
        return float(g.center_z / threshold)

    def _stability(self, g: GraspCandidate) -> float:
        period = (2.0 * math.pi) / float(self.jaw_count)
        residual = abs(g.angle % period)
        deviation = min(residual, period - residual)
        max_dev = period / 2.0
        return float(1.0 - deviation / max_dev)

    def _symmetry(self, g: GraspCandidate) -> float:
        return float(math.cos(float(self.jaw_count) * g.angle) ** 2)

    def _original_score(self, g: GraspCandidate) -> float:
        return float(min(1.0, max(0.0, g.original_score)))

    def _mask_fitness(self, g: GraspCandidate) -> float:
        if getattr(g, "mask", None) is None:
            return 1.0

        cx, cy = g.center_x, g.center_y
        r = g.width / 2.0
        angle = g.angle

        collisions = 0
        h, w = g.mask.shape
        for i in range(self.jaw_count):
            theta = angle + i * (2 * math.pi / float(self.jaw_count))
            jx = int(round(cx + r * math.cos(theta)))
            jy = int(round(cy + r * math.sin(theta)))

            if 0 <= jx < w and 0 <= jy < h and g.mask[jy, jx] > 0:
                collisions += 1

        ratio = collisions / float(self.jaw_count)
        return float(max(0.1, 1.0 - 0.9 * ratio))

    def _calculate_rule_score(
        self, g: GraspCandidate, depth: Optional[np.ndarray]
    ) -> float:
        w = self.config["evaluation"]["rule_weights"]
        score = (
            w["width"] * self._width_fitness(g)
            + w["score"] * self._original_score(g)
            + w["height"] * self._height_fitness(g)
            + w["stability"] * self._stability(g)
            + w["symmetry"] * self._symmetry(g)
        )
        score *= self._mask_fitness(g)
        return float(min(0.90, score))

    def score_detail(self, g: GraspCandidate, depth: Optional[np.ndarray] = None) -> dict:
        w = self.config["evaluation"]["rule_weights"]
        rw = self._width_fitness(g)
        rs = self._original_score(g)
        rh = self._height_fitness(g)
        rb = self._stability(g)
        ry = self._symmetry(g)
        rm = self._mask_fitness(g)

        base_total = (
            w["width"] * rw
            + w["score"] * rs
            + w["height"] * rh
            + w["stability"] * rb
            + w["symmetry"] * ry
        )
        total = min(0.90, base_total * rm)

        return {
            "width": {"raw": rw, "weighted": w["width"] * rw},
            "score": {"raw": rs, "weighted": w["score"] * rs},
            "height": {"raw": rh, "weighted": w["height"] * rh},
            "stability": {"raw": rb, "weighted": w["stability"] * rb},
            "symmetry": {"raw": ry, "weighted": w["symmetry"] * ry},
            "mask": {"raw": rm, "weighted": rm},
            "total": float(total),
        }

    def _mlp_scores(
        self, candidates: List[GraspCandidate], depth: Optional[np.ndarray]
    ) -> np.ndarray:
        features = self.extractor.extract_batch(candidates, depth)
        prepared = self.snapshot_model()
        if prepared is None:
            return np.asarray(
                [self._calculate_rule_score(c, depth) for c in candidates],
                dtype=np.float32,
            )
        return self.predict_features(features, prepared)

    def predict_features(self, features: np.ndarray, prepared: Optional[PreparedModel] = None) -> np.ndarray:
        """Replay stored features with this model's own normalization and calibration."""
        prepared = prepared or self.snapshot_model()
        if prepared is None:
            raise ValueError("no ML model available")
        features = np.asarray(features, dtype=np.float32)
        if features.ndim != 2 or features.shape[1] != self.extractor.FEATURE_DIM or not np.isfinite(features).all():
            raise ValueError("invalid feature matrix")
        if prepared.norm_mean is not None:
            features = (features - prepared.norm_mean) / prepared.norm_std
        if not np.isfinite(features).all():
            raise ValueError("normalization produced nonfinite features")
        with torch.no_grad():
            tensor = torch.from_numpy(features.astype(np.float32))
            scores = prepared.model(tensor).reshape(-1).numpy()

        scores = np.atleast_1d(scores)

        # Isotonic calibration: sigmoid 출력 -> 진짜 확률
        # mapping 이 있으면 raw sigmoid 점수를 학습 시 fit 된 보정 곡선으로 변환.
        if prepared.iso_x is not None:
            scores = np.interp(scores, prepared.iso_x, prepared.iso_y)
        elif prepared.sigmoid is not None:
            p = np.clip(scores.astype(np.float64), 1e-7, 1-1e-7)
            logits = prepared.sigmoid[0] * np.log(p/(1-p)) + prepared.sigmoid[1]
            scores = 1 / (1 + np.exp(-np.clip(logits, -60, 60)))

        # 보정된 ML 출력은 실제 성공률을 직접 나타낸다. 여기서 규칙 기반
        # multiplier를 다시 곱하면 calibration이 깨지므로 후처리 가중치는 적용하지 않는다.
        if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
            raise ValueError("invalid model predictions")
        return scores

    def _load_config(self, path: Optional[str]) -> dict:
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {
            "gripper": {
                "min_width": 0.01,
                "max_width": 0.10,
                "ideal_width": 0.05,
                "collision_threshold_z": 0.02,
            },
            "evaluation": {
                "rule_weights": {
                    "width": 0.35,
                    "score": 0.30,
                    "height": 0.25,
                    "stability": 0.10,
                    "symmetry": 0.00,
                }
            },
        }
