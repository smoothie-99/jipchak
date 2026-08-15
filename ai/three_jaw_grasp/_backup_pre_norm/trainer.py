import json

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split

from .evaluator import GraspScoreMLP
from .feature_extractor import FeatureExtractor


class GraspDataset(Dataset):
    """JSONL 형식의 파지 로그 파일을 위한 PyTorch Dataset."""
    def __init__(self, data_path: str):
        self.samples = []
        with open(data_path, 'r', encoding='utf-8') as f:
            for line in f:
                log = json.loads(line)
                # 특징 벡터의 차원이 모델과 일치하는지 확인
                if len(log.get('features', [])) == FeatureExtractor.FEATURE_DIM:
                    self.samples.append({
                        "features": torch.tensor(log['features'], dtype=torch.float32),
                        "label": torch.tensor([float(log['success'])], dtype=torch.float32)
                    })

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]['features'], self.samples[idx]['label']


def train_evaluator_model(data_path: str, save_path: str, epochs: int = 50, lr: float = 1e-3, batch_size: int = 32):
    """데이터셋으로 GraspScoreMLP 모델을 학습하고 저장합니다."""
    dataset = GraspDataset(data_path)
    if len(dataset) == 0:
        print(f"오류: '{data_path}'에서 유효한 학습 데이터를 찾을 수 없습니다.")
        return

    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    model = GraspScoreMLP(input_dim=FeatureExtractor.FEATURE_DIM)
    criterion = nn.BCELoss()  # Sigmoid 출력에 맞는 이진 교차 엔트로피 손실
    optimizer = optim.Adam(model.parameters(), lr=lr)

    print(f"총 {len(dataset)}개의 샘플 중 {len(train_dataset)}개로 학습을 시작합니다...")

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for features, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(features)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        val_loss, correct, total = 0.0, 0, 0
        with torch.no_grad():
            for features, labels in val_loader:
                outputs = model(features)
                val_loss += criterion(outputs, labels).item()
                predicted = (outputs > 0.5).float()
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        val_accuracy = 100 * correct / total if total > 0 else 0
        print(f"Epoch {epoch+1}/{epochs} | "
              f"Train Loss: {train_loss/len(train_loader):.4f} | "
              f"Val Loss: {val_loss/len(val_loader):.4f} | "
              f"Val Acc: {val_accuracy:.2f}%")

    torch.save(model.state_dict(), save_path)
    print(f"\n학습 완료! 모델이 '{save_path}'에 저장되었습니다.")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Grasp Evaluator MLP 모델 학습")
    parser.add_argument("--data", type=str, default="grasp_log.jsonl", help="학습 데이터 파일 경로 (.jsonl)")
    parser.add_argument("--out", type=str, default="evaluator_model.pth", help="학습된 모델을 저장할 경로 (.pth)")
    args = parser.parse_args()
    train_evaluator_model(data_path=args.data, save_path=args.out)