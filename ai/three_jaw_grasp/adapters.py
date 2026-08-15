from abc import ABC, abstractmethod
from typing import List, Any
import math
import numpy as np
from .candidate import GraspCandidate
from .factory import AdapterFactory

class BaseGraspAdapter(ABC):
    """
    모델별 raw output을 GraspCandidate 리스트로 변환하는 기본 인터페이스.

    기여 가이드:
        새로운 모델 포맷을 지원하려면 이 클래스를 상속하고
        adapt() 메서드를 구현하세요.
        반드시 docstring에 다음을 명시하세요:
            - raw_output 타입과 포맷
            - center_x / center_y 좌표계 (픽셀 또는 미터 등)
            - center_z 기준 (카메라 좌표계 미터 / 바닥 기준 미터 / 미사용 등)
            - angle 단위 (라디안)
    """

    @abstractmethod
    def adapt(self, raw_output: Any) -> List[GraspCandidate]:
        pass


@AdapterFactory.register("graspnet")
class GraspGroupAdapter(BaseGraspAdapter):
    """
    GraspGroup 계열 (예: graspnet-baseline) 어댑터.

    좌표계:
        center_x, center_y, center_z: 카메라 좌표계 기준 미터 (m)
        angle: 라디안 (rad)

    raw_output 포맷:
        속성 .x, .y, .z, .width, .theta, .score 를 가지는 객체 리스트.
        예: GraspGroup (graspnetAPI) 순회 결과.
    """

    def adapt(self, raw_output: Any) -> List[GraspCandidate]:
        candidates = []
        for g in raw_output:
            candidates.append(GraspCandidate(
                center_x=float(getattr(g, 'x', 0.0)),
                center_y=float(getattr(g, 'y', 0.0)),
                center_z=float(getattr(g, 'z', 0.0)),
                width=float(getattr(g, 'width', 0.0)),
                angle=float(getattr(g, 'theta', 0.0)),
                original_score=float(getattr(g, 'score', 0.0)),
                raw={'source': 'GraspGroupAdapter'}
            ))
        return candidates


@AdapterFactory.register("grconvnet")
class Grasp3DoFAdapter(BaseGraspAdapter):
    """
    GR-ConvNet Grasp3DoF 리스트 → GraspCandidate 변환 어댑터.

    raw_output: list[Grasp3DoF]  (from GRConvNetWrapper.predict / GraspInfer.predict)
        각 원소: x (px), y (px), z (m or None), score (0~1)
    """

    def adapt(self, raw_output: Any) -> List[GraspCandidate]:
        if not raw_output:
            return []

        candidates = []
        for g in raw_output:
            candidates.append(GraspCandidate(
                center_x=float(g.x),
                center_y=float(g.y),
                center_z=float(g.z) if g.z is not None else 0.0,
                width=0.0,
                angle=0.0,
                original_score=float(g.score),
                raw=getattr(g, 'metadata', {}),
            ))
        return candidates


@AdapterFactory.register("anygrasp")
class PoseArrayAdapter(BaseGraspAdapter):
    """
    6DoF Pose Array 계열 (예: AnyGrasp) 어댑터.

    좌표계:
        center_x, center_y, center_z: 카메라 좌표계 기준 미터 (m)
        angle: 라디안. Z축 회전 성분만 추출 (단순화).
                정밀한 변환이 필요하면 _rotation_to_angle() 오버라이드.

    raw_output 포맷:
        딕셔너리 리스트. 각 원소:
            {
                'translation': [x, y, z],         # float, 미터
                'rotation'   : [[r00,...],[...]], # 3×3 회전 행렬 (선택)
                'width'      : float,              # 미터 (없으면 기본값 사용)
                'score'      : float,              # 0~1
            }
    """

    DEFAULT_WIDTH: float = 0.05  # 미터

    def adapt(self, raw_output: Any) -> List[GraspCandidate]:
        candidates = []
        for g in raw_output:
            t = g['translation']
            angle = self._rotation_to_angle(g.get('rotation', None))
            candidates.append(GraspCandidate(
                center_x=float(t[0]),
                center_y=float(t[1]),
                center_z=float(t[2]),
                width=float(g.get('width', self.DEFAULT_WIDTH)),
                angle=angle,
                original_score=float(g['score']),
                raw=g
            ))
        return candidates

    def _rotation_to_angle(self, rotation) -> float:
        """
        3×3 회전 행렬에서 Z축 회전 성분(Yaw)을 추출하여 라디안으로 반환.
        rotation이 없으면 0.0 반환.
        커스텀 변환이 필요하면 이 메서드를 override하세요.
        """
        if rotation is None:
            return 0.0
        r = rotation
        # atan2(r[1][0], r[0][0]) = Yaw (Z축 회전)
        try:
            return float(math.atan2(r[1][0], r[0][0]))
        except (IndexError, TypeError):
            return 0.0

# ─── YOLO 객체 인식 기반 어댑터 ──────────────────────────────────
@AdapterFactory.register("yolo_box")
class YoloBoxGraspAdapter(BaseGraspAdapter):
    """
    YOLO Bounding Box 기반 어댑터.
    raw_output: dict
        - 'box': [xmin, ymin, xmax, ymax]
        - 'score': float
    """
    def adapt(self, raw_output: Any) -> List[GraspCandidate]:
        candidates = []
        if isinstance(raw_output, list):
            items = raw_output
        else:
            items = [raw_output]
            
        for item in items:
            if isinstance(item, list) and len(item) == 8: # Cornell 8-point fallback
                pts = np.array(item).reshape(4, 2)
                cx, cy = pts.mean(axis=0)
                width = np.linalg.norm(pts[0] - pts[3])
                dy = pts[1][1] - pts[0][1]
                dx = pts[1][0] - pts[0][0]
                angle = math.atan2(dy, dx)
                candidates.append(GraspCandidate(
                    center_x=float(cx), center_y=float(cy), center_z=0.30, 
                    width=float(width), angle=float(angle), original_score=1.0, 
                    box=[float(pts[:,0].min()), float(pts[:,1].min()), float(pts[:,0].max()), float(pts[:,1].max())],
                    raw={'pts': pts.tolist()}
                ))
            elif isinstance(item, dict) and 'box' in item:
                box = item['box']
                cx = (box[0] + box[2]) / 2.0
                cy = (box[1] + box[3]) / 2.0
                width = min(box[2] - box[0], box[3] - box[1])
                angle = 0.0
                score = item.get('score', 1.0)
                candidates.append(GraspCandidate(
                    center_x=float(cx), center_y=float(cy), center_z=0.0,
                    width=float(width), angle=angle, original_score=float(score),
                    box=box,
                    raw=item
                ))
        return candidates

@AdapterFactory.register("yolo_seg")
class YoloSegGraspAdapter(BaseGraspAdapter):
    """
    YOLO Segmentation (Mask) 기반 어댑터.
    raw_output: dict
        - 'mask': np.ndarray (2D boolean/binary array)
        - 'box': [xmin, ymin, xmax, ymax] (optional)
        - 'score': float
    """
    def adapt(self, raw_output: Any) -> List[GraspCandidate]:
        import cv2
        candidates = []
        if isinstance(raw_output, list):
            items = raw_output
        else:
            items = [raw_output]
            
        for item in items:
            if not isinstance(item, dict) or 'mask' not in item:
                continue
            
            mask = item['mask']
            if mask.dtype == bool:
                mask = mask.astype(np.uint8) * 255
            elif mask.max() == 1:
                mask = (mask * 255).astype(np.uint8)
                
            # 무게중심 (Centroid) 계산
            M = cv2.moments(mask)
            if M["m00"] != 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
            else:
                continue
                
            # 윤곽선 추출 및 PCA/장축단축 계산
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            
            contour = max(contours, key=cv2.contourArea)
            
            if len(contour) >= 5:
                # 타원 피팅을 통해 장축 각도 및 단축 길이 추출
                ellipse = cv2.fitEllipse(contour)
                (center, axes, angle_deg) = ellipse
                # opencv fitEllipse angle: 수직(0도)에서 시계방향 회전. 
                # GraspCandidate angle: 수평축 기준(X축) 반시계방향 라디안.
                # 보정 처리
                angle_rad = math.radians(angle_deg) - (math.pi / 2)
                width = min(axes[0], axes[1])
            else:
                x, y, w, h = cv2.boundingRect(contour)
                angle_rad = 0.0
                width = min(w, h)
                
            # 집게 하드웨어 최대 벌림 폭 (픽셀 단위 근사값 90px) 초과 방지
            max_hardware_width = 90.0
            width = min(width, max_hardware_width)
            
            score = item.get('score', 1.0)
            box = item.get('box', None)
            
            binary_mask = (mask > 0).astype(np.uint8)
            
            candidates.append(GraspCandidate(
                center_x=float(cx), center_y=float(cy), center_z=0.0,
                width=float(width), angle=float(angle_rad), original_score=float(score),
                mask=binary_mask, box=box,
                raw=item
            ))
            
        return candidates
