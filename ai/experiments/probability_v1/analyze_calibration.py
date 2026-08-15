"""
Probability calibration 분석.

가설: ChickEvaluator의 룰 점수는 (0~0.98 범위) ranking 신호일 뿐
      실제 성공 확률이 아니다. 분석에서 묻는 것:
        - "룰 점수 = 0.7 인 후보들의 실제 성공률은 70%인가?"
        - 아니라면 sigmoid / Platt / isotonic 으로 보정 가능한가?

실제 데이터 수집 전 합성 데이터로 분석 파이프라인 검증.
실제 데이터가 들어오면 동일 스크립트 그대로 사용 가능.

산출물:
    - ECE (Expected Calibration Error) 출력
    - Reliability diagram 데이터 (bin별 평균 예측, 실제 성공률) 콘솔 출력
    - Platt-scaling 된 점수와 원점수의 ECE 비교
"""

import argparse
import json
from pathlib import Path

import numpy as np


def _load_jsonl(path: Path) -> tuple[np.ndarray, np.ndarray]:
    features_list, labels = [], []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            log = json.loads(line)
            features_list.append(log["features"])
            labels.append(log["success"])
    return np.array(features_list, dtype=np.float32), np.array(labels, dtype=np.int64)


def _rule_proxy_score(features: np.ndarray) -> np.ndarray:
    """
    실제 ChickEvaluator를 호출하려면 GraspCandidate 객체가 필요 (mask 등).
    이 스크립트는 features 만 다루므로, ChickEvaluator 가중치 흐름을 흉내내는
    proxy score 를 features 에서 직접 계산한다.

    feature index 매핑 (generate_synthetic.py 기준, FEATURE_DIM=11):
        [0] width, [7] sensor_invalid_ratio, [10] relative_grasp_y
    """
    width = features[:, 0]
    invalid_ratio = features[:, 7]
    rel_y = features[:, 10]

    width_term = np.exp(-((width - 55.0) ** 2) / (2 * 15.0 ** 2))
    invalid_term = 1.0 - invalid_ratio
    top_term = np.exp(-((rel_y - 0.30) ** 2) / (2 * 0.15 ** 2))
    score = 0.45 * width_term + 0.30 * invalid_term + 0.25 * top_term
    return np.clip(score, 0.0, 0.98)


def expected_calibration_error(
    probs: np.ndarray, labels: np.ndarray, n_bins: int = 10
) -> tuple[float, list[dict]]:
    """
    ECE 계산.

    각 확률 구간(bin)에서 평균 예측확률과 실제 성공률의 차이를 가중합한다.
    0 에 가까울수록 잘 보정된 것.
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    rows = []
    n = len(labels)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        in_bin = (probs >= lo) & (probs < hi if i < n_bins - 1 else probs <= hi)
        count = int(in_bin.sum())
        if count == 0:
            rows.append({"bin": f"[{lo:.1f},{hi:.1f}]", "n": 0, "pred": 0.0, "actual": 0.0, "gap": 0.0})
            continue
        mean_pred = float(probs[in_bin].mean())
        actual = float(labels[in_bin].mean())
        gap = abs(mean_pred - actual)
        ece += (count / n) * gap
        rows.append({"bin": f"[{lo:.1f},{hi:.1f}]", "n": count, "pred": mean_pred, "actual": actual, "gap": gap})
    return float(ece), rows


def platt_scaling_fit(
    scores: np.ndarray, labels: np.ndarray, max_iter: int = 500, lr: float = 0.1
) -> tuple[float, float]:
    """
    Platt scaling: 1-D logistic regression. P = sigmoid(a*score + b)
    BCE loss 를 수동 gradient descent 로 최소화.
    """
    a, b = 1.0, 0.0
    n = len(scores)
    for _ in range(max_iter):
        z = a * scores + b
        p = 1.0 / (1.0 + np.exp(-z))
        # gradient (BCE)
        err = p - labels
        grad_a = float((err * scores).mean())
        grad_b = float(err.mean())
        a -= lr * grad_a
        b -= lr * grad_b
        if abs(grad_a) < 1e-6 and abs(grad_b) < 1e-6:
            break
    return float(a), float(b)


def platt_scaling_apply(scores: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(a * scores + b)))


def isotonic_regression_fit(
    scores: np.ndarray, labels: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Isotonic regression: Pool Adjacent Violators (PAV) 알고리즘.

    score 로 정렬한 뒤 단조 증가 step function 을 학습한다.
    Platt 와 달리 파라메트릭 가정 없음 → cliff/계단형 분포에도 대응.

    Returns
    -------
    sorted_scores : np.ndarray
        정렬된 unique score 값 (boundary)
    fitted_probs : np.ndarray
        각 score 구간의 평균 라벨 (단조 증가 보장)
    """
    order = np.argsort(scores)
    s = scores[order]
    y = labels[order].astype(np.float64)

    # PAV: 인접 위반 발견 시 평균으로 풀(pool)
    blocks = [[v] for v in y]
    sums = [float(v) for v in y]
    sizes = [1 for _ in y]

    i = 0
    while i < len(sums) - 1:
        if sums[i] / sizes[i] > sums[i + 1] / sizes[i + 1]:
            # 위반 → 풀
            sums[i] += sums[i + 1]
            sizes[i] += sizes[i + 1]
            del sums[i + 1]
            del sizes[i + 1]
            del blocks[i + 1]
            blocks[i].extend(blocks[i + 1] if i + 1 < len(blocks) else [])
            # 이전 블록과 다시 비교 (위반 전파)
            if i > 0:
                i -= 1
        else:
            i += 1

    # 각 블록 평균을 원본 위치에 펼침
    fitted = np.empty_like(y)
    pos = 0
    for s_sum, s_size in zip(sums, sizes):
        avg = s_sum / s_size
        fitted[pos:pos + s_size] = avg
        pos += s_size

    return s, fitted


def isotonic_apply(
    new_scores: np.ndarray, sorted_scores: np.ndarray, fitted_probs: np.ndarray
) -> np.ndarray:
    """학습된 isotonic 매핑을 새 score 에 적용 (가장 가까운 학습 포인트 보간)."""
    return np.interp(new_scores, sorted_scores, fitted_probs)


def _print_reliability(rows: list[dict], header: str) -> None:
    print(f"\n--- {header} (reliability diagram) ---")
    print(f"  {'bin':<14} {'n':>5} {'pred':>8} {'actual':>8} {'gap':>8}")
    for r in rows:
        print(
            f"  {r['bin']:<14} {r['n']:>5} {r['pred']:>8.3f} "
            f"{r['actual']:>8.3f} {r['gap']:>8.3f}"
        )


def main(args: argparse.Namespace) -> None:
    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"데이터 없음: {data_path}\nfirst run generate_synthetic.py")

    features, labels = _load_jsonl(data_path)
    print(f"[analyze] loaded {len(labels)} samples ({labels.sum()} success, {len(labels) - labels.sum()} fail)")

    # 1) 룰 점수 proxy (현재 production 시스템과 동일한 흐름의 점수)
    raw_scores = _rule_proxy_score(features)
    print(f"[analyze] raw score min={raw_scores.min():.3f} max={raw_scores.max():.3f} mean={raw_scores.mean():.3f}")

    ece_raw, rows_raw = expected_calibration_error(raw_scores, labels, args.bins)
    _print_reliability(rows_raw, "raw rule score")
    print(f"  ECE (raw rule score) = {ece_raw:.4f}")

    # 정직한 평가를 위해 calibration fit / ECE eval 분리 (70/30 split)
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(labels))
    n_fit = int(0.7 * len(labels))
    fit_idx, eval_idx = perm[:n_fit], perm[n_fit:]
    fit_scores, fit_labels = raw_scores[fit_idx], labels[fit_idx]
    eval_scores, eval_labels = raw_scores[eval_idx], labels[eval_idx]
    print(f"\n[analyze] calibration fit={n_fit} / eval={len(eval_idx)} (no leak)")

    # 0-1) raw 도 동일 eval set 에서 다시 계산 (Platt/Isotonic 과 공정 비교)
    ece_raw_eval, _ = expected_calibration_error(eval_scores, eval_labels, args.bins)

    # 2) Platt scaling: fit 으로 학습, eval 에서 평가
    a, b = platt_scaling_fit(fit_scores, fit_labels.astype(np.float32))
    print(f"[analyze] Platt scaling fit: a={a:.4f}, b={b:.4f}")
    platt_eval = platt_scaling_apply(eval_scores, a, b)
    ece_platt, rows_platt = expected_calibration_error(platt_eval, eval_labels, args.bins)
    _print_reliability(rows_platt, "Platt-scaled (eval split)")
    print(f"  ECE (Platt-scaled, eval) = {ece_platt:.4f}")

    # 3) Isotonic regression: fit 으로 학습, eval 에서 평가
    sorted_s, fitted_p = isotonic_regression_fit(fit_scores, fit_labels.astype(np.float64))
    iso_eval = isotonic_apply(eval_scores, sorted_s, fitted_p)
    ece_iso, rows_iso = expected_calibration_error(iso_eval, eval_labels, args.bins)
    _print_reliability(rows_iso, "Isotonic-mapped (eval split)")
    print(f"  ECE (Isotonic, eval) = {ece_iso:.4f}")

    # 4) 요약
    print("\n=== summary (모두 동일 eval split 600개에서 측정) ===")
    print(f"  ECE raw       = {ece_raw_eval:.4f}")
    print(f"  ECE Platt     = {ece_platt:.4f}  (Δ vs raw: {ece_raw_eval - ece_platt:+.4f})")
    print(f"  ECE Isotonic  = {ece_iso:.4f}  (Δ vs raw: {ece_raw_eval - ece_iso:+.4f})")
    best = min(
        [("raw", ece_raw_eval), ("Platt", ece_platt), ("Isotonic", ece_iso)],
        key=lambda kv: kv[1],
    )
    print(f"  → 최저 ECE: {best[0]} ({best[1]:.4f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probability calibration 분석")
    parser.add_argument(
        "--data", type=str,
        default="ai/experiments/probability_v1/data/synthetic_log.jsonl",
    )
    parser.add_argument("--bins", type=int, default=10, help="reliability bin 개수")
    main(parser.parse_args())
