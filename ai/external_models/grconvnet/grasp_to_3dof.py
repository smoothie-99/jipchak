from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from skimage.feature import peak_local_max


@dataclass
class Grasp3DoF:
    x: float
    y: float
    z: Optional[float]
    score: float
    metadata: dict = field(default_factory=dict)


def grasp_to_3dof(
    q_img: np.ndarray,
    depth_full: np.ndarray,
    *,
    original_size: tuple[int, int],
    crop_size: int = 224,
    top_k: int = 10,
    peak_min_distance: int = 20,
    peak_threshold: float = 0.2,
    workspace_mask: Optional[np.ndarray] = None,
) -> list[Grasp3DoF]:
    W, H = original_size
    if q_img.shape != (crop_size, crop_size):
        raise ValueError(
            f"q_img shape {q_img.shape} != ({crop_size}, {crop_size})"
        )
    if depth_full.shape != (H, W):
        raise ValueError(
            f"depth_full shape {depth_full.shape} != ({H}, {W})"
        )

    local_max = peak_local_max(
        q_img,
        min_distance=peak_min_distance,
        threshold_abs=peak_threshold,
        num_peaks=top_k,
    )

    top = (H - crop_size) // 2
    left = (W - crop_size) // 2

    candidates: list[Grasp3DoF] = []
    for (yy, xx) in local_max:
        score = float(q_img[yy, xx])
        orig_x = int(xx + left)
        orig_y = int(yy + top)

        if not (0 <= orig_y < H and 0 <= orig_x < W):
            continue

        if workspace_mask is not None and not bool(workspace_mask[orig_y, orig_x]):
            continue

        z: Optional[float] = None
        d = float(depth_full[orig_y, orig_x])
        if d > 0:
            z = d

        candidates.append(
            Grasp3DoF(
                x=float(orig_x),
                y=float(orig_y),
                z=z,
                score=score,
                metadata={
                    "crop_y": int(yy),
                    "crop_x": int(xx),
                },
            )
        )

    candidates.sort(key=lambda g: g.score, reverse=True)
    return candidates
