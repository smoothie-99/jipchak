"""
Feature normalization 추가한 학습 검증.

train_test.py 가 50 epoch 동안 val acc 57.5% 에 박힌 이유:
    feature scale 차이 (width 20~100 vs depth 0.3~0.8 vs ratio 0~1).
    MLP 가 큰 값 feature gradient 에만 끌려가서 학습 못함.

이 스크립트는:
    1. jsonl 데이터 로드
    2. feature 평균/표준편차 계산 (train split 만 기준)
    3. (x - mean) / std 로 표준화
    4. MLP 학습
    5. 모델 + 정규화 통계를 dict 로 .pth 저장

추론 시에는 동일한 mean/std 로 표준화해야 일관됨.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split

# ai/three_jaw_grasp 패키지 import
_AI_ROOT = Path(__file__).resolve().parents[2]
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from three_jaw_grasp.evaluator import GraspScoreMLP
from three_jaw_grasp.feature_extractor import FeatureExtractor


class NormalizedGraspDataset(Dataset):
    """jsonl 로 부터 features, success 로드 + 외부에서 주입된 mean/std 로 표준화."""

    def __init__(self, samples: list[dict], mean: np.ndarray, std: np.ndarray) -> None:
        self.samples = samples
        self.mean = mean
        self.std = std

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.samples[idx]
        x = (np.asarray(row["features"], dtype=np.float32) - self.mean) / self.std
        return (
            torch.from_numpy(x.astype(np.float32)),
            torch.tensor([float(row["success"])], dtype=torch.float32),
        )


def _load_jsonl(path: Path) -> list[dict]:
    samples: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            log = json.loads(line)
            if len(log.get("features", [])) == FeatureExtractor.FEATURE_DIM:
                samples.append(log)
    return samples


def train_normalized(
    data_path: Path,
    save_path: Path,
    epochs: int = 80,
    lr: float = 1e-3,
    batch_size: int = 32,
    val_split: float = 0.2,
    seed: int = 0,
    patience: int = 15,
) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)

    samples = _load_jsonl(data_path)
    if not samples:
        raise SystemExit(f"데이터 없음: {data_path}")

    n_total = len(samples)
    n_val = max(1, int(n_total * val_split))
    n_train = n_total - n_val

    # train/val 인덱스 셔플
    perm = np.random.permutation(n_total)
    train_idx, val_idx = perm[:n_train], perm[n_train:]
    train_samples = [samples[i] for i in train_idx]
    val_samples = [samples[i] for i in val_idx]

    # 정규화 통계는 train split 만 사용 (data leakage 방지)
    train_features = np.array(
        [s["features"] for s in train_samples], dtype=np.float32
    )
    mean = train_features.mean(axis=0)
    std = train_features.std(axis=0)
    std[std < 1e-6] = 1.0  # 분산 0 feature 보호

    print(f"[train_normalized] samples train={n_train} val={n_val}")
    print(f"[train_normalized] feature mean[:5]={mean[:5].round(3)}")
    print(f"[train_normalized] feature std[:5] ={std[:5].round(3)}")
    print(f"[train_normalized] early-stopping patience={patience} epochs")

    train_ds = NormalizedGraspDataset(train_samples, mean, std)
    val_ds = NormalizedGraspDataset(val_samples, mean, std)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    model = GraspScoreMLP(input_dim=FeatureExtractor.FEATURE_DIM)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    best_val_loss = float("inf")
    best_val_acc = 0.0
    best_epoch = -1
    best_state: dict | None = None
    epochs_since_improve = 0

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for x, y in train_loader:
            optimizer.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        val_loss_sum, correct, total = 0.0, 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                out = model(x)
                val_loss_sum += criterion(out, y).item()
                pred = (out > 0.5).float()
                total += y.size(0)
                correct += (pred == y).sum().item()
        val_loss = val_loss_sum / max(len(val_loader), 1)
        val_acc = 100.0 * correct / total if total > 0 else 0.0

        # best-by-val-loss 기준 (loss 가 acc 보다 부드러운 신호)
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
                f"Epoch {epoch + 1:>3}/{epochs} | "
                f"Train Loss: {train_loss / max(len(train_loader), 1):.4f} | "
                f"Val Loss: {val_loss:.4f} | "
                f"Val Acc: {val_acc:.2f}%{mark}"
            )

        if epochs_since_improve >= patience:
            print(f"[train_normalized] early stop (no val_loss improvement for {patience} epochs)")
            break

    if best_state is None:
        raise SystemExit("모델이 한 epoch 도 못 돌았음")

    save_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": best_state,
            "feature_dim": FeatureExtractor.FEATURE_DIM,
            "norm_mean": mean.tolist(),
            "norm_std": std.tolist(),
            "best_epoch": best_epoch,
            "best_val_loss": float(best_val_loss),
            "best_val_acc": float(best_val_acc),
        },
        save_path,
    )
    print(
        f"\n학습 완료. best epoch={best_epoch} "
        f"val_loss={best_val_loss:.4f} val_acc={best_val_acc:.2f}% → {save_path}"
    )


def main(args: argparse.Namespace) -> None:
    train_normalized(
        data_path=Path(args.data),
        save_path=Path(args.out),
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        seed=args.seed,
        patience=args.patience,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="정규화 + 학습 검증")
    parser.add_argument(
        "--data", type=str,
        default="ai/experiments/probability_v1/data/synthetic_log.jsonl",
    )
    parser.add_argument(
        "--out", type=str,
        default="ai/experiments/probability_v1/models/evaluator_normalized.pth",
    )
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--patience", type=int, default=15)
    main(parser.parse_args())
