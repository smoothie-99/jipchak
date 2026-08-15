"""
GR-ConvNet 모델을 Three-Jaw-Grasp 파이프라인에 주입하는 플러그인.

GraspInfer 를 내부적으로 사용하며, predict() 는 Grasp3DoF 리스트를 반환한다.
RectGraspAdapter 대신 Grasp3DoFAdapter 와 함께 사용해야 한다.
"""
import numpy as np

from three_jaw_grasp.factory import ModelFactory


@ModelFactory.register("grconvnet")
class GRConvNetWrapper:

    def __init__(self, checkpoint_path=None, device='cpu'):
        self._infer = None
        try:
            from external_models.grconvnet.infer import GraspInfer
            if checkpoint_path:
                self._infer = GraspInfer(
                    checkpoint=checkpoint_path,
                    device=device,
                )
        except Exception as e:
            print(f"[GRConvNet] load failed: {e}, dummy mode")

    def predict(self, rgb, depth, **kwargs):
        if self._infer is None:
            return []

        depth_m = depth.astype(np.float32) if depth is not None else np.zeros(rgb.shape[:2], dtype=np.float32)
        try:
            return self._infer.predict(rgb, depth_m, top_k=5)
        except Exception:
            return []
