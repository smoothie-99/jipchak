import os
from dataclasses import dataclass
from typing import Tuple, List, Optional

import numpy as np


@dataclass
class Detection:
    bbox: Tuple[int, int, int, int]  # (xmin, ymin, xmax, ymax)
    score: float
    label: int


class ObjectDetector:
    """
    물체를 탐지하여 Bounding Box를 반환하는 객체 인식기 인터페이스
    """
    def detect(self, rgb, **kwargs) -> Tuple[int, int, int, int]:
        raise NotImplementedError

    def detect_all(self, rgb, **kwargs) -> List[Detection]:
        raise NotImplementedError


class SSDLiteDetector(ObjectDetector):
    """
    torchvision ssdlite320_mobilenet_v3_large 기반 객체 탐지기.
    COCO pretrained, CPU 추론 가능 (~37ms).
    """

    def __init__(
        self,
        score_threshold: float = 0.35,
        target_labels: Optional[List[int]] = None,
        device: str = "cpu",
    ):
        import torch
        import torchvision

        self.device = torch.device(device)
        self.score_threshold = score_threshold
        self.target_labels = set(target_labels) if target_labels else None

        weights = torchvision.models.detection.SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
        self.model = torchvision.models.detection.ssdlite320_mobilenet_v3_large(
            weights=weights,
        )
        self.model.to(self.device)
        self.model.eval()
        print(f"[SSDLiteDetector] loaded (device={device}, threshold={score_threshold})")

    def _run_model(self, rgb):
        import torch

        img_tensor = torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255.0
        img_tensor = img_tensor.to(self.device)

        with torch.no_grad():
            preds = self.model([img_tensor])[0]

        return (
            preds["boxes"].cpu().numpy(),
            preds["scores"].cpu().numpy(),
            preds["labels"].cpu().numpy(),
        )

    def detect(self, rgb, **kwargs) -> Tuple[int, int, int, int]:
        h, w = rgb.shape[:2]
        boxes, scores, labels = self._run_model(rgb)

        best_score = 0.0
        best_box = (0, 0, w, h)

        for box, score, label in zip(boxes, scores, labels):
            if score < self.score_threshold:
                continue
            if self.target_labels and int(label) not in self.target_labels:
                continue
            if score > best_score:
                best_score = score
                best_box = (
                    max(0, int(box[0])),
                    max(0, int(box[1])),
                    min(w, int(box[2])),
                    min(h, int(box[3])),
                )

        return best_box

    def detect_all(self, rgb, **kwargs) -> List[Detection]:
        h, w = rgb.shape[:2]
        boxes, scores, labels = self._run_model(rgb)

        results = []
        for box, score, label in zip(boxes, scores, labels):
            if score < self.score_threshold:
                continue
            if self.target_labels and int(label) not in self.target_labels:
                continue
            results.append(Detection(
                bbox=(
                    max(0, int(box[0])),
                    max(0, int(box[1])),
                    min(w, int(box[2])),
                    min(h, int(box[3])),
                ),
                score=float(score),
                label=int(label),
            ))

        return results

class YoloMockDetector(ObjectDetector):
    """
    YOLO 26 기반 객체 탐지기를 모사(Mock)하는 클래스.
    실제 가중치가 없으므로 Cornell Dataset의 파지 정답 파일(cpos.txt)을
    읽어 점들을 모두 포함하는 Bounding Box를 임시로 반환합니다.
    """
    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        print("[YoloMockDetector] YOLO 26 객체 탐지기 초기화 완료 (전처리 Crop용)")

    def detect(self, rgb, filename_prefix: str = None) -> Tuple[int, int, int, int]:
        h, w = rgb.shape[:2]
        if not self.data_dir or not filename_prefix:
            # 중앙 50% Crop 임시 반환
            return (w//4, h//4, 3*w//4, 3*h//4)

        cpos_file = os.path.join(self.data_dir, f"{filename_prefix}cpos.txt")
        if not os.path.exists(cpos_file):
            return (0, 0, w, h)

        x_coords = []
        y_coords = []
        with open(cpos_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    x_coords.append(float(parts[0]))
                    y_coords.append(float(parts[1]))

        if not x_coords:
            return (0, 0, w, h)

        # 박스 여유(Padding)를 20픽셀 정도 줍니다.
        xmin = max(0, int(min(x_coords)) - 20)
        ymin = max(0, int(min(y_coords)) - 20)
        xmax = min(w, int(max(x_coords)) + 20)
        ymax = min(h, int(max(y_coords)) + 20)

        # Box 크기가 너무 작으면 (10x10 미만) 안전장치
        if (xmax - xmin) < 10 or (ymax - ymin) < 10:
            return (0, 0, w, h)

        return (xmin, ymin, xmax, ymax)
