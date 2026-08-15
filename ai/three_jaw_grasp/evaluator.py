import math
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
        # 학습 시 train split 으로 fit, .pth 에 함께 저장됨. 없으면 calibration 없이 raw sigmoid 사용.
        self._iso_x: Optional[np.ndarray] = None  # 정렬된 score boundary
        self._iso_y: Optional[np.ndarray] = None  # 각 boundary 의 평균 라벨 (단조)

        if model_path:
            ckpt = torch.load(model_path, map_location="cpu")
            # 새 포맷(dict with state_dict + norm stats) vs 구포맷(state_dict only) 모두 지원
            if isinstance(ckpt, dict) and "state_dict" in ckpt:
                self.model = GraspScoreMLP(self.extractor.FEATURE_DIM)
                self.model.load_state_dict(ckpt["state_dict"])
                if "norm_mean" in ckpt and "norm_std" in ckpt:
                    self._norm_mean = np.asarray(ckpt["norm_mean"], dtype=np.float32)
                    self._norm_std = np.asarray(ckpt["norm_std"], dtype=np.float32)
                    print(
                        f"[ThreeJawEvaluator] loaded model + normalization stats "
                        f"(dim={self.extractor.FEATURE_DIM})"
                    )
                else:
                    print(
                        "[ThreeJawEvaluator] WARNING: model loaded without normalization stats — "
                        "추론 점수가 학습 시와 일치하지 않을 수 있음"
                    )
                if "iso_x" in ckpt and "iso_y" in ckpt:
                    self._iso_x = np.asarray(ckpt["iso_x"], dtype=np.float64)
                    self._iso_y = np.asarray(ckpt["iso_y"], dtype=np.float64)
                    print(
                        f"[ThreeJawEvaluator] isotonic calibration loaded "
                        f"({len(self._iso_x)} points) — sigmoid → 진짜 확률 변환 활성"
                    )
            else:
                # 구포맷: raw state_dict
                self.model = GraspScoreMLP(self.extractor.FEATURE_DIM)
                self.model.load_state_dict(ckpt)
                print(
                    "[ThreeJawEvaluator] loaded legacy model (no norm stats) — "
                    "trainer.py 로 재학습 권장"
                )
            self.model.eval()

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
        # 학습 시 적용한 정규화를 동일하게 적용 (없으면 raw 사용 — 단 학습/추론 불일치 위험)
        if self._norm_mean is not None and self._norm_std is not None:
            features = (features - self._norm_mean) / self._norm_std
        with torch.no_grad():
            tensor = torch.from_numpy(features.astype(np.float32))
            scores = self.model(tensor).squeeze().numpy()

        scores = np.atleast_1d(scores)

        # Isotonic calibration: sigmoid 출력 -> 진짜 확률
        # mapping 이 있으면 raw sigmoid 점수를 학습 시 fit 된 보정 곡선으로 변환.
        if self._iso_x is not None and self._iso_y is not None:
            scores = np.interp(scores, self._iso_x, self._iso_y)

        mask_multipliers = np.array([self._mask_fitness(c) for c in candidates])
        scores = scores * mask_multipliers
        scores = np.clip(scores, 0.0, 0.90)
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
