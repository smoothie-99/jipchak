import numpy as np
from typing import List, Optional
from .candidate import GraspCandidate

class FeatureExtractor:
    """
    GraspCandidate를 평가 모델용 특징 벡터로 변환.

    Feature 11개 (정보 중복 제거 + 데이터 효율):
        [0]  width                  그리퍼 폭
        [1]  original_score         YOLO 검출 신뢰도
        [2]  center_z               중심점 깊이 (단일 픽셀)
        [3]  sin(angle)             그리퍼 회전 (각도 wrap-around 방지용 1쌍)
        [4]  cos(angle)
        [5]  depth_median           20x20 패치 깊이 중앙값 (mean/min/max/p25/p75 보다 안정)
        [6]  depth_roughness        유효 깊이 std (표면 굴곡)
        [7]  sensor_invalid_ratio   깊이 0 픽셀 비율 (센서 신뢰도)
        [8]  aspect_ratio           마스크 세로/가로 (인형 타입 지표)
        [9]  width_variance         열별 너비 std/너비 (목 존재 여부)
        [10] relative_grasp_y       마스크 내 상하 위치 (목/몸 구분)

    드롭: depth_mean/min/max/p25/p75 (median과 중복), relative_grasp_x (좌우 대칭이라 약함)
    """
    FEATURE_DIM = 11

    def extract(self, grasp: GraspCandidate, depth: Optional[np.ndarray] = None) -> np.ndarray:
        """
        단일 파지 후보에 대한 특징 추출.
        """
        # 기본 특징 (5개) — center_x/y 는 모양 특징의 상대 좌표(_y만 유지)로 대체
        features = [
            grasp.width,
            grasp.original_score,
            grasp.center_z,
            np.sin(grasp.angle),
            np.cos(grasp.angle)
        ]

        # Depth 기반 추가 특징 (3개)
        if depth is not None:
            depth_patch = self._get_depth_patch(grasp, depth)
            valid_depth_patch = depth_patch[depth_patch > 0]

            features.extend([
                np.median(depth_patch),
                np.std(valid_depth_patch) if valid_depth_patch.size > 0 else 0.0,  # depth_roughness
                np.mean(depth_patch == 0),  # sensor_invalid_ratio
            ])
        else:
            features.extend([0.0] * 3)

        # 모양 기반 추가 특징 (3개: aspect_ratio, width_variance, relative_grasp_y)
        features.extend(self._shape_features(grasp, depth))

        return np.array(features, dtype=np.float32)

    def extract_batch(self, candidates: List[GraspCandidate], depth: Optional[np.ndarray] = None) -> np.ndarray:
        """
        학습 또는 추론 시 배치 처리를 위한 특징 추출.
        """
        features_list = [self.extract(c, depth) for c in candidates]
        return np.stack(features_list)

    def _get_depth_patch(self, grasp: GraspCandidate, depth: np.ndarray, size: int = 20) -> np.ndarray:
        """
        파지 중심 주변의 depth 맵 패치 추출.
        주 좌표계 불일치 시 보정 로직이 필요할 수 있음.
        """
        h, w = depth.shape
        # 단순화를 위해 center_x, center_y를 픽셀 좌표로 가정 (현실적으로는 좌표계 변환 필요)
        cx, cy = int(grasp.center_x), int(grasp.center_y)
        
        x1 = max(0, cx - size // 2)
        x2 = min(w, cx + size // 2)
        y1 = max(0, cy - size // 2)
        y2 = min(h, cy + size // 2)
        
        patch = depth[y1:y2, x1:x2]
        if patch.size == 0:
            return np.zeros((size, size))
        return patch

    def _shape_features(self, grasp: GraspCandidate, depth: Optional[np.ndarray]) -> list:
        """
        인형의 전체적인 모양과 관련된 특징 3개를 반환.
        - aspect_ratio: 마스크 세로/가로 (인형 타입 지표)
        - width_variance: 열별 너비 표준편차 / 너비 (목 존재 여부)
        - relative_grasp_y: 마스크 내 상하 위치 (목/몸 구분 핵심)
        relative_grasp_x 는 좌우 대칭성으로 약한 신호라 제외.
        """
        if getattr(grasp, "mask", None) is None:
            return [0.0] * 3

        # 마스크의 바운딩 박스 계산
        rows = np.any(grasp.mask, axis=1)
        cols = np.any(grasp.mask, axis=0)
        if not np.any(rows) or not np.any(cols):
            return [0.0] * 3

        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]

        h = float(y_max - y_min)
        w = float(x_max - x_min)

        aspect_ratio = h / (w + 1e-6)

        # 마스크의 열별 너비 표준편차 (정규화)
        col_widths = np.sum(grasp.mask, axis=0)[x_min:x_max]
        width_variance = np.std(col_widths) / (w + 1e-6) if w > 0 else 0.0

        # 인형 기준 상대 좌표 (y만 사용)
        relative_grasp_y = (grasp.center_y - y_min) / (h + 1e-6)

        return [
            aspect_ratio,
            width_variance,
            relative_grasp_y,
        ]
