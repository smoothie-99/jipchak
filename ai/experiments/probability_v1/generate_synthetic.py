"""
합성 파지 데이터 생성기.

trainer.py 에 들어가는 jsonl 포맷:
    {"features": [19개 float], "success": 0|1, "candidate": {...}, "metadata": {...}}

FEATURE_DIM=11 구성 (FeatureExtractor 기준, 중복/약신호 6개 드롭 후):
    [0]  width
    [1]  original_score
    [2]  center_z
    [3]  sin(angle)
    [4]  cos(angle)
    [5]  depth_median
    [6]  depth_roughness
    [7]  sensor_invalid_ratio
    [8]  aspect_ratio
    [9]  width_variance
    [10] relative_grasp_y
"""

import argparse
import json
from pathlib import Path

import numpy as np


N_FEATURES = 11  # FeatureExtractor.FEATURE_DIM 과 일치


def _sample_one(rng: np.random.Generator) -> tuple[list[float], int]:
    """
    feature 19개 + success 라벨 1쌍 샘플링.

    성공 라벨은 width / neck-capture / support 조합으로 결정.
    """
    width = rng.uniform(20.0, 100.0)
    original_score = rng.uniform(0.05, 0.95)
    center_z = rng.uniform(0.3, 0.8)  # meter
    angle = rng.uniform(-np.pi, np.pi)
    sin_a, cos_a = float(np.sin(angle)), float(np.cos(angle))

    depth_median = rng.uniform(0.3, 0.8)
    depth_roughness = rng.gamma(2.0, 0.005)        # 표면 굴곡
    sensor_invalid_ratio = rng.beta(2, 18)        # 보통 작은 값

    aspect_ratio = rng.lognormal(0.0, 0.3)         # 약 1 근처
    width_variance = rng.uniform(0.05, 0.6)
    relative_grasp_y = rng.uniform(0.1, 0.6)

    features = [
        width, original_score, center_z, sin_a, cos_a,
        depth_median, depth_roughness, sensor_invalid_ratio,
        aspect_ratio, width_variance, relative_grasp_y,
    ]

    # 성공 라벨: 이상 width(55) 가까울수록, sensor_invalid 적을수록, 위쪽 파지일수록 +
    width_term = float(np.exp(-((width - 55.0) ** 2) / (2 * 15.0 ** 2)))
    invalid_term = float(1.0 - sensor_invalid_ratio)
    top_term = float(np.exp(-((relative_grasp_y - 0.30) ** 2) / (2 * 0.15 ** 2)))
    raw_p = 0.45 * width_term + 0.30 * invalid_term + 0.25 * top_term
    raw_p = float(np.clip(raw_p, 0.0, 1.0))
    # 결정적 라벨 + 5% 라벨 플립 노이즈 (학습 가능성 검증용 강한 신호)
    label = 1 if raw_p > 0.5 else 0
    if rng.random() < 0.05:
        label = 1 - label
    success = label

    return features, success


def main(args: argparse.Namespace) -> None:
    rng = np.random.default_rng(args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    successes = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i in range(args.n):
            features, success = _sample_one(rng)
            entry = {
                "features": features,
                "success": success,
                "candidate": {"synthetic": True, "index": i},
                "metadata": {"source": "generate_synthetic.py", "seed": args.seed},
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            successes += success

    print(f"[generate_synthetic] {args.n}건 생성 완료 → {out_path}")
    print(f"  success: {successes} ({successes / args.n * 100:.1f}%)")
    print(f"  fail:    {args.n - successes} ({(args.n - successes) / args.n * 100:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="합성 파지 데이터 생성")
    parser.add_argument("--n", type=int, default=200, help="샘플 개수 (기본 200)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument(
        "--out", type=str,
        default="ai/experiments/probability_v1/data/synthetic_log.jsonl",
        help="출력 jsonl 경로",
    )
    main(parser.parse_args())
