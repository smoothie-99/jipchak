"""GR-ConvNet inference wrapper.

torch.load 로 저장된 체크포인트는 pickle 이 원래 클래스 경로
(inference.models.grconvnet3.GenerativeResnet) 를 참조한다.
이 모듈 디렉토리를 sys.path 에 추가해 해당 import 가 해결되도록 한다.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import numpy as np
import torch

_GRCONVNET_ROOT = os.path.dirname(os.path.abspath(__file__))
if _GRCONVNET_ROOT not in sys.path:
    sys.path.insert(0, _GRCONVNET_ROOT)

from grasp_to_3dof import Grasp3DoF, grasp_to_3dof  # noqa: E402
from inference.post_process import post_process_output  # noqa: E402
from utils.data.camera_data import CameraData  # noqa: E402


class GraspInfer:

    def __init__(
        self,
        checkpoint: str,
        device: str = "cpu",
        output_size: int = 224,
    ) -> None:
        self.device = torch.device(device)
        self.output_size = output_size
        self.checkpoint = checkpoint
        self.net = torch.load(checkpoint, map_location=self.device)
        self.net.eval()
        print(f"[GraspInfer] loaded {checkpoint} on {device}")

    def predict(
        self,
        rgb: np.ndarray,
        depth_m: np.ndarray,
        *,
        depth_raw: Optional[np.ndarray] = None,
        top_k: int = 5,
        peak_min_distance: int = 20,
        peak_threshold: float = 0.2,
    ) -> list[Grasp3DoF]:
        H, W = rgb.shape[:2]
        if depth_raw is None:
            depth_raw = (depth_m * 1000.0).astype(np.float32)

        depth_in = depth_raw[..., None] if depth_raw.ndim == 2 else depth_raw

        cam = CameraData(
            width=W, height=H, output_size=self.output_size,
            include_depth=True, include_rgb=True,
        )
        x, _, _ = cam.get_data(rgb=rgb, depth=depth_in)
        if x.dim() == 3:
            x = x.unsqueeze(0)
        x = x.to(self.device)

        with torch.no_grad():
            pred = self.net.predict(x)
            q_img, _, _ = post_process_output(
                pred["pos"], pred["cos"], pred["sin"], pred["width"]
            )

        return grasp_to_3dof(
            q_img, depth_m,
            original_size=(W, H),
            crop_size=self.output_size,
            top_k=top_k,
            peak_min_distance=peak_min_distance,
            peak_threshold=peak_threshold,
        )
