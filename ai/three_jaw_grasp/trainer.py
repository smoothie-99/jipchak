from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

from .evaluator import GraspScoreMLP
from .feature_extractor import FeatureExtractor
from .dataset import load_attempts


class GraspDataset(Dataset):
    """
    JSONL 형식의 파지 로그 파일을 위한 PyTorch Dataset.

    mean/std 가 주어지면 (x - mean) / std 로 정규화한 feature 를 반환한다.
    feature scale 차이(width 20~100 vs ratio 0~1)로 학습이 깨지는 것 방지.
    """
    def __init__(
        self,
        samples: list[dict],
        mean: Optional[np.ndarray] = None,
        std: Optional[np.ndarray] = None,
    ):
        self.samples = samples
        self.mean = mean
        self.std = std

    @classmethod
    def from_jsonl(
        cls, data_path: str, feature_dim: int = FeatureExtractor.FEATURE_DIM
    ) -> "GraspDataset":
        samples: list[dict] = []
        for log in load_attempts(data_path, feature_dim):
            if log["dataset_role"] == "train":
                samples.append({"features": log["features"], "label": float(log["success"])})
        return cls(samples)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        row = self.samples[idx]
        x = row["features"]
        if self.mean is not None and self.std is not None:
            x = (x - self.mean) / self.std
        return (
            torch.from_numpy(x.astype(np.float32)),
            torch.tensor([row["label"]], dtype=torch.float32),
        )


def _split_samples(
    samples: list[dict], val_ratio: float, seed: int
) -> tuple[list[dict], list[dict]]:
    """성공/실패가 train과 validation 양쪽에 남도록 계층 분할한다."""
    rng = np.random.default_rng(seed)
    labels = np.asarray([int(sample["label"]) for sample in samples])
    train_idx: list[int] = []
    val_idx: list[int] = []
    for label in (0, 1):
        class_idx = np.flatnonzero(labels == label)
        class_idx = rng.permutation(class_idx)
        if len(class_idx) < 2:
            train_idx.extend(class_idx.tolist())
            continue
        n_val = min(
            len(class_idx) - 1,
            max(1, int(round(len(class_idx) * val_ratio))),
        )
        val_idx.extend(class_idx[:n_val].tolist())
        train_idx.extend(class_idx[n_val:].tolist())
    rng.shuffle(train_idx)
    rng.shuffle(val_idx)
    return [samples[i] for i in train_idx], [samples[i] for i in val_idx]


def _fit_isotonic(
    scores: np.ndarray, labels: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Pool Adjacent Violators (PAV) 로 단조 증가 calibration mapping 학습.
    추론 시 np.interp(raw_sigmoid, iso_x, iso_y) 로 보정 점수 얻음.

    sigmoid 출력은 ranking 신호일 뿐 실제 성공률과 어긋남.
    별도 calibration split의 (predicted, actual) 쌍으로 단조 보정.
    """
    if len(scores) == 0:
        # 빈 입력 — identity mapping
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])

    s, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    sums = np.bincount(inverse, weights=labels.astype(np.float64)).tolist()
    sizes = counts.tolist()
    block_lengths = [1] * len(s)
    i = 0
    while i < len(sums) - 1:
        if sums[i] / sizes[i] > sums[i + 1] / sizes[i + 1]:
            sums[i] += sums[i + 1]
            sizes[i] += sizes[i + 1]
            block_lengths[i] += block_lengths[i + 1]
            del sums[i + 1]
            del sizes[i + 1]
            del block_lengths[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1

    fitted = np.empty_like(s)
    pos = 0
    for s_sum, s_size, length in zip(sums, sizes, block_lengths):
        avg = s_sum / s_size
        fitted[pos:pos + length] = avg
        pos += length
    return s, fitted


def _fit_sigmoid(scores: np.ndarray, labels: np.ndarray) -> list[float]:
    logits = torch.tensor(np.log(np.clip(scores, 1e-7, 1-1e-7) /
                                  (1-np.clip(scores, 1e-7, 1-1e-7))), dtype=torch.float64)
    targets = torch.tensor(labels, dtype=torch.float64)
    parameters = torch.zeros(2, dtype=torch.float64, requires_grad=True)
    optimizer = optim.LBFGS([parameters], max_iter=50, line_search_fn="strong_wolfe")

    def closure():
        optimizer.zero_grad()
        a = parameters[0].clamp(-10, 10).exp()
        loss = nn.functional.binary_cross_entropy_with_logits(a * logits + parameters[1], targets)
        loss = loss + 1e-4 * parameters.square().sum()
        loss.backward()
        return loss

    optimizer.step(closure)
    return [float(parameters[0].detach().clamp(-10, 10).exp()), float(parameters[1].detach())]


def train_evaluator_model(
    data_path: str,
    save_path: str,
    epochs: int = 200,
    lr: float = 1e-3,
    batch_size: int = 32,
    patience: int = 15,
    val_ratio: float = 0.2,
    seed: int = 0,
    feature_dim: int = FeatureExtractor.FEATURE_DIM,
    metadata: Optional[dict] = None,
    min_calibration_samples: int = 100,
    isotonic_min_samples: int = 1000,
):
    """
    데이터셋으로 GraspScoreMLP 모델을 학습하고 저장한다.

    저장 포맷 (.pth):
        {
            "state_dict":   모델 가중치,
            "feature_dim":  학습 시 차원 (호환성 체크용),
            "norm_mean":    feature 평균 (정규화용, list[float]),
            "norm_std":     feature 표준편차 (정규화용, list[float]),
            "best_epoch":   best val_loss epoch,
            "best_val_loss":최저 val_loss,
            "best_val_acc": 그때의 val_acc,
        }

    추론 시 evaluator 가 norm_mean/norm_std 로 feature 정규화한 뒤 모델에 통과시킨다.
    """
    torch.manual_seed(seed)

    full = GraspDataset.from_jsonl(data_path, feature_dim=feature_dim)
    if len(full) < 4:
        raise ValueError(
            f"학습에는 최소 4개의 유효한 샘플이 필요합니다: {data_path} ({len(full)}개)"
        )

    labels = [int(sample["label"]) for sample in full.samples]
    if len(set(labels)) < 2:
        raise ValueError("성공과 실패 데이터가 모두 있어야 학습할 수 있습니다.")

    train_samples, val_samples = _split_samples(full.samples, val_ratio, seed)
    if not val_samples:
        raise ValueError("validation requires sufficient samples in both classes")
    # Calibration must not fit on the same labels used to choose the best epoch.
    calibration_samples = []
    if (len(val_samples) >= 2 * min_calibration_samples
            and min(sum(s["label"] == label for s in val_samples) for label in (0, 1)) >= 4):
        val_samples, calibration_samples = _split_samples(val_samples, 0.5, seed + 1)

    # 정규화 통계는 train split 만 사용 (data leakage 방지)
    train_features = np.stack([s["features"] for s in train_samples])
    mean = train_features.mean(axis=0)
    std = train_features.std(axis=0)
    std[std < 1e-6] = 1.0  # 분산 0 feature 보호

    train_ds = GraspDataset(train_samples, mean=mean, std=std)
    val_ds = GraspDataset(val_samples, mean=mean, std=std)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    model = GraspScoreMLP(input_dim=feature_dim)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    print(
        f"총 {len(full)}개 샘플 (train {len(train_samples)} / val {len(val_samples)}). "
        f"early-stop patience={patience} epochs"
    )

    best_val_loss = float("inf")
    best_val_acc = 0.0
    best_epoch = -1
    best_state = None
    epochs_since_improve = 0

    for epoch in range(epochs):
        model.train()
        train_loss_sum = 0.0
        for features, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            train_loss_sum += loss.item()

        model.eval()
        val_loss_sum, correct, total = 0.0, 0, 0
        with torch.no_grad():
            for features, labels in val_loader:
                outputs = model(features)
                val_loss_sum += criterion(outputs, labels).item()
                predicted = (outputs > 0.5).float()
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        val_loss = val_loss_sum / max(len(val_loader), 1)
        val_acc = 100.0 * correct / total if total > 0 else 0.0

        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            best_val_acc = val_acc
            best_epoch = epoch + 1
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            epochs_since_improve = 0
            mark = " *"
        else:
            epochs_since_improve += 1
            mark = ""

        if epoch == 0 or (epoch + 1) % 5 == 0 or mark:
            print(
                f"Epoch {epoch+1:>3}/{epochs} | "
                f"Train Loss: {train_loss_sum/max(len(train_loader),1):.4f} | "
                f"Val Loss: {val_loss:.4f} | "
                f"Val Acc: {val_acc:.2f}%{mark}"
            )

        if epochs_since_improve >= patience:
            print(f"early stop (no val_loss improvement for {patience} epochs)")
            break

    if best_state is None:
        raise RuntimeError("학습 실패: best state 없음")

    # Fit an independent calibrator only when enough samples are available.
    best_model = GraspScoreMLP(input_dim=feature_dim)
    best_model.load_state_dict(best_state)
    best_model.eval()
    val_scores: list[float] = []
    val_targets: list[float] = []
    with torch.no_grad():
        calibration_loader = DataLoader(GraspDataset(calibration_samples, mean=mean, std=std),
                                        batch_size=batch_size)
        for x, y in calibration_loader:
            out = best_model(x).squeeze(-1).numpy()
            val_scores.extend(np.atleast_1d(out).tolist())
            val_targets.extend(y.squeeze(-1).numpy().tolist())
    calibration = {}
    method = "none"
    if (len(val_scores) >= min_calibration_samples
            and min(val_targets.count(label) for label in (0.0, 1.0)) >= 5):
        scores = np.asarray(val_scores, dtype=np.float64)
        targets = np.asarray(val_targets, dtype=np.float64)
        if len(val_scores) >= isotonic_min_samples:
            iso_x, iso_y = _fit_isotonic(scores, targets)
            calibration = {"iso_x": iso_x.tolist(), "iso_y": iso_y.tolist()}
            method = "isotonic"
        else:
            calibration = {"sigmoid": _fit_sigmoid(scores, targets)}
            method = "sigmoid"

    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
            "state_dict": best_state,
            "feature_dim": feature_dim,
            "norm_mean": mean.tolist(),
            "norm_std": std.tolist(),
            "best_epoch": best_epoch,
            "best_val_loss": float(best_val_loss),
            "best_val_acc": float(best_val_acc),
            **calibration,
            "metadata": {**(metadata or {}), "calibration_method": method,
                         "calibration_samples": len(calibration_samples)},
        }
    torch.save(checkpoint, output_path)
    print(
        f"\n학습 완료. best epoch={best_epoch} "
        f"val_loss={best_val_loss:.4f} val_acc={best_val_acc:.2f}% "
        f"→ '{save_path}'"
    )
    return {
        "sample_count": len(full),
        "best_epoch": best_epoch,
        "best_val_loss": float(best_val_loss),
        "best_val_acc": float(best_val_acc),
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Grasp Evaluator MLP 모델 학습")
    parser.add_argument("--data", type=str, default="grasp_log.jsonl", help="학습 데이터 파일 경로 (.jsonl)")
    parser.add_argument("--out", type=str, default="evaluator_model.pth", help="학습된 모델을 저장할 경로 (.pth)")
    args = parser.parse_args()
    train_evaluator_model(data_path=args.data, save_path=args.out)
