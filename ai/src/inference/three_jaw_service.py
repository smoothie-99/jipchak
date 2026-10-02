import os
import numpy as np

# ai/three_jaw_grasp 패키지 사용 (ai/three-jaw-grasp 디렉토리는 docs/examples만)
from three_jaw_grasp import GraspPipeline
from three_jaw_grasp.adapters import YoloSegGraspAdapter
from three_jaw_grasp.evaluator_chick import ChickEvaluator
from three_jaw_grasp.success_feature_extractor import SuccessFeatureExtractor
from src.learning import AutoSuccessLearner
from src.learning.promotion import PromotionPolicy


class Yolo26sSegWrapper:
    """Ultralytics YOLO26s-seg 모델 래퍼"""

    def __init__(
        self,
        model_path: str,
        min_box_area_ratio: float = 0.04,
        max_box_area_ratio: float = 0.60,
        min_mask_fill_ratio: float = 0.35,
        face_only_max_area_ratio: float = 0.12,
    ):
        try:
            from ultralytics import YOLO

            self.model = YOLO(model_path)
            self.valid = True
        except ImportError:
            print("[Yolo26sSegWrapper] ultralytics 패키지가 설치되지 않았습니다.")
            self.valid = False
        except Exception as e:
            print(f"[Yolo26sSegWrapper] 모델 로드 실패: {e}")
            self.valid = False
        self.min_box_area_ratio = min_box_area_ratio
        self.max_box_area_ratio = max_box_area_ratio
        self.min_mask_fill_ratio = min_mask_fill_ratio
        self.face_only_max_area_ratio = face_only_max_area_ratio

    def predict(self, rgb, depth=None, **kwargs):
        if not self.valid:
            return []

        # 진단 모드: conf 임계값을 0.05로 낮춰서 raw 검출이 뭐든 잡히는지 확인
        results = self.model.predict(rgb, conf=0.05, verbose=False)
        output = []
        for r in results:
            # 진단: r.boxes 정보 전체 출력 (mask 유무 무관)
            if r.boxes is not None and len(r.boxes) > 0:
                cls_arr = r.boxes.cls.cpu().numpy()
                conf_arr = r.boxes.conf.cpu().numpy()
                raw_summary = [
                    f"cls={int(c)}:conf={cf:.2f}" for c, cf in zip(cls_arr, conf_arr)
                ]
                print(f"[Yolo26sSeg] raw detections (n={len(cls_arr)}): {raw_summary}")
            else:
                print("[Yolo26sSeg] raw detections: 0")

            if r.masks is not None:
                masks = r.masks.data.cpu().numpy()
                boxes = r.boxes.xyxy.cpu().numpy()
                classes = r.boxes.cls.cpu().numpy()
                confs = r.boxes.conf.cpu().numpy()

                h, w = rgb.shape[:2]
                total_area = h * w

                for i in range(len(masks)):
                    # 1. 클래스 체크: 0번(병아리)만 허용
                    if int(classes[i]) != 0:
                        print(
                            f"[Yolo26sSeg] dropped: cls={int(classes[i])} != 0 (conf={confs[i]:.2f})"
                        )
                        continue
                    print(
                        f"[Yolo26sSeg] accepted: cls={int(classes[i])} (conf={confs[i]:.2f})"
                    )  # 어떤 클래스가 잡히는지 확인용 로그

                    # 2. bbox area ratio filtering
                    box = boxes[i]
                    bw, bh = box[2] - box[0], box[3] - box[1]
                    box_area = float(max(bw, 0.0) * max(bh, 0.0))
                    box_area_ratio = box_area / float(total_area)
                    if box_area_ratio < self.min_box_area_ratio:
                        print(
                            f"[Yolo26sSeg] dropped: too small ({box_area_ratio*100:.1f}%)"
                        )
                        continue
                    if box_area_ratio > self.max_box_area_ratio:
                        print(
                            f"[Yolo26sSeg] dropped: too large ({box_area_ratio*100:.1f}%)"
                        )
                        continue

                    m = masks[i]
                    if m.shape[0] != h or m.shape[1] != w:
                        import cv2

                        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
                    m = (m > 0.5).astype(np.uint8)

                    x0 = int(max(0, min(box[0], w - 1)))
                    y0 = int(max(0, min(box[1], h - 1)))
                    x1 = int(max(x0 + 1, min(box[2], w)))
                    y1 = int(max(y0 + 1, min(box[3], h)))
                    crop_mask = m[y0:y1, x0:x1]
                    if crop_mask.size == 0:
                        print("[Yolo26sSeg] dropped: empty crop mask")
                        continue

                    mask_fill_ratio = float(crop_mask.mean())
                    # face-only rejection heuristic: small + round-ish + dense
                    aspect = float((bw + 1e-6) / (bh + 1e-6))
                    is_roundish = 0.8 <= aspect <= 1.25
                    if (
                        box_area_ratio <= self.face_only_max_area_ratio
                        and is_roundish
                        and mask_fill_ratio >= self.min_mask_fill_ratio
                    ):
                        print(
                            "[Yolo26sSeg] dropped: likely face-only "
                            f"(area={box_area_ratio:.3f}, aspect={aspect:.2f}, fill={mask_fill_ratio:.2f})"
                        )
                        continue

                    output.append(
                        {"mask": m, "box": boxes[i].tolist(), "score": float(confs[i])}
                    )
        return output


class ThreeJawGraspService:
    def __init__(
        self,
        min_box_area_ratio: float = 0.04,
        max_box_area_ratio: float = 0.60,
        min_mask_fill_ratio: float = 0.35,
        face_only_max_area_ratio: float = 0.12,
        success_learning_enabled: bool = True,
        success_learning_data_path: str = "/data/learning/grasp_attempts.jsonl",
        success_model_path: str = "/data/learning/success_evaluator.pth",
        success_learning_min_samples: int = 30,
        success_learning_retrain_every: int = 10,
        success_learning_min_class_samples: int = 5,
        success_learning_epochs: int = 120,
        success_learning_batch_size: int = 32,
        success_holdout_ratio: float = 0.2,
        success_max_observation_age: float = 2.0,
        success_promotion_policy: PromotionPolicy | None = None,
    ):
        self._pipeline = None
        self._learner = None
        self._image_wh = (640, 480)  # D435 기본 해상도
        self._min_box_area_ratio = min_box_area_ratio
        self._max_box_area_ratio = max_box_area_ratio
        self._min_mask_fill_ratio = min_mask_fill_ratio
        self._face_only_max_area_ratio = face_only_max_area_ratio
        self._success_learning_enabled = success_learning_enabled
        self._success_learning_data_path = success_learning_data_path
        self._success_model_path = success_model_path
        self._success_learning_min_samples = success_learning_min_samples
        self._success_learning_retrain_every = success_learning_retrain_every
        self._success_learning_min_class_samples = success_learning_min_class_samples
        self._success_learning_epochs = success_learning_epochs
        self._success_learning_batch_size = success_learning_batch_size
        self._success_holdout_ratio = success_holdout_ratio
        self._success_max_observation_age = success_max_observation_age
        self._success_promotion_policy = success_promotion_policy

    def load(self, model_path: str) -> None:
        """
        YOLO26s-seg 모델과 파이프라인 초기화
        """
        if not os.path.exists(model_path):
            print(f"[ThreeJawGraspService] 모델 파일을 찾을 수 없습니다: {model_path}")
            return

        model = Yolo26sSegWrapper(
            model_path,
            min_box_area_ratio=self._min_box_area_ratio,
            max_box_area_ratio=self._max_box_area_ratio,
            min_mask_fill_ratio=self._min_mask_fill_ratio,
            face_only_max_area_ratio=self._face_only_max_area_ratio,
        )
        adapter = YoloSegGraspAdapter()
        evaluator = ChickEvaluator(
            jaw_count=3,
            extractor=SuccessFeatureExtractor(),
            model_path=(
                self._success_model_path
                if os.path.exists(self._success_model_path)
                else None
            ),
        )

        self._pipeline = GraspPipeline(
            model=model, adapter=adapter, evaluator=evaluator
        )
        self._learner = AutoSuccessLearner(
            data_path=self._success_learning_data_path,
            model_path=self._success_model_path,
            evaluator=evaluator,
            enabled=self._success_learning_enabled,
            min_samples=self._success_learning_min_samples,
            retrain_every=self._success_learning_retrain_every,
            min_class_samples=self._success_learning_min_class_samples,
            epochs=self._success_learning_epochs,
            batch_size=self._success_learning_batch_size,
            holdout_ratio=self._success_holdout_ratio,
            max_observation_age=self._success_max_observation_age,
            promotion_policy=self._success_promotion_policy,
        )
        print(f"[ThreeJawGraspService] Pipeline 로드 완료 (YOLO: {model_path})")

    def infer(
        self,
        color_bgr: np.ndarray,
        depth_mm: np.ndarray,
        session_id: str | None = None,
        observed_at: float | None = None,
        attempt_id: str | None = None,
    ) -> dict | None:
        if self._pipeline is None:
            print("[ThreeJawGraspService] _pipeline is None (load 실패?)")
            return None

        if color_bgr is None:
            print("[ThreeJawGraspService] color_bgr is None (D435 RGB 미수신)")
            return None

        try:
            # depth를 미터 단위로 변환
            depth_m = None
            if depth_mm is not None:
                depth_m = depth_mm.astype("float32") / 1000.0

            print(
                f"[ThreeJawGraspService] infer start: "
                f"rgb_shape={color_bgr.shape} depth={'O' if depth_m is not None else 'X'}"
            )
            # 해상도 업데이트 (들어오는 영상 기준)
            if color_bgr is not None:
                h, w = color_bgr.shape[:2]
                self._image_wh = (w, h)
            else:
                w, h = self._image_wh

            # --- 조준 정확도 점수(Centering Score) 계산 ---
            # 카메라 중심(화면 중앙) 좌표
            cam_x, cam_y = w / 2, h / 2

            # 카메라와 집게 간의 물리적 오프셋 보정 (mm -> 픽셀 변환)
            # 카메라(원래 기준)는 왼쪽으로 60mm, 앞(위)으로 10mm 이동해 설치되어 있음
            PX_PER_MM = 1.0
            CAM_LEFT_OFFSET_MM = 60.0
            CAM_FORWARD_OFFSET_MM = 10.0

            # 물리적(실제) 집게 중심 좌표 (이미지 기준, 회전 전)
            gripper_x = cam_x - (CAM_LEFT_OFFSET_MM * PX_PER_MM)
            gripper_y = cam_y - (CAM_FORWARD_OFFSET_MM * PX_PER_MM)

            candidates = self._pipeline.predict_candidates(color_bgr, depth_m)
            for candidate in candidates:
                candidate_distance = np.sqrt(
                    (candidate.center_x - gripper_x) ** 2
                    + (candidate.center_y - gripper_y) ** 2
                )
                candidate.raw["gripper_distance_ratio"] = float(
                    candidate_distance / max(float(candidate.width), 1e-6)
                )
                detail = self._pipeline.evaluator.score_detail(candidate, depth_m)
                for name in ("top_bias", "neck_capture", "support", "clearance"):
                    candidate.raw[name] = float(
                        detail.get(name, {}).get("raw", 0.0)
                    )
            best = self._pipeline.evaluator.select_best(candidates, depth=depth_m)

            # --- ChickEvaluator의 세부 규칙 점수(로그/설명용) ---
            score_info = self._pipeline.evaluator.score_detail(best, depth_m)

            # 병아리(검출된 목표)와 '실제 집게 중심' 사이의 거리 (정밀도 가중치 계산용)
            dist = np.sqrt(
                (best.center_x - gripper_x) ** 2 + (best.center_y - gripper_y) ** 2
            )

            # UI 오버레이 위치: 집게 물리 위치에서 검출 위치 쪽으로 일부 이동시켜
            # 오버레이가 인형에 더 가까이 보이도록 함 (프론트엔드에서 이 좌표로 그려짐).
            # ALPHA: 0.0 = 물리집게, 1.0 = 검출 중심. 0.6 정도면 충분히 가까워 보임.
            ALPHA = 0.6
            overlay_x = gripper_x + (best.center_x - gripper_x) * ALPHA
            overlay_y = gripper_y + (best.center_y - gripper_y) * ALPHA

            # 인형의 크기(best.width)를 기준으로 거리에 따른 감점 요인 계산 (범위 0.8로 완화)
            sigma = max(best.width * 0.8, 1e-6)
            centering_weight = np.exp(-(dist**2) / (2 * (sigma**2)))

            # 학습 모델이 있으면 실제 성공/실패 데이터로 보정된 확률을 사용한다.
            # 데이터 부족 시에만 기존 규칙 점수가 초기값으로 동작한다.
            grasp_probability, prediction_source, prediction_version = self._pipeline.evaluator.predict_with_source(
                best, depth_m
            )
            # ML 모델은 gripper_distance_ratio를 직접 학습하므로 거리 감점을
            # 다시 곱하지 않는다. 규칙 기반 초기 단계에서만 centering을 별도 반영한다.
            final_confidence = float(
                np.clip(
                    grasp_probability
                    if prediction_source == "ml"
                    else grasp_probability * centering_weight,
                    0.0,
                    1.0,
                )
            )
            if self._learner is not None and session_id:
                self._learner.remember_attempt(
                    session_id=session_id,
                    candidate=best,
                    depth=depth_m,
                    predicted_probability=final_confidence,
                    observed_at=observed_at,
                    attempt_id=attempt_id,
                    metadata={
                        "prediction_source": prediction_source,
                        "model_version": prediction_version,
                        "rule_score": float(score_info.get("total", 0.0)),
                        "centering_weight": float(centering_weight),
                        "doll_type": score_info.get("doll_type", "unknown"),
                        "yolo_confidence": float(best.original_score),
                    },
                )

            print(
                f"[ThreeJawGraspService] candidate: "
                f"doll=({best.center_x:.0f},{best.center_y:.0f}) gripper=({gripper_x:.0f},{gripper_y:.0f}) "
                f"width={best.width:.1f} angle={best.angle:.2f} "
                f"grasp_prob={grasp_probability:.3f} centering={centering_weight:.3f} "
                f"final={final_confidence:.3f} source={prediction_source}"
            )

            # 최종 필터링: 디버깅을 위해 임계값을 0.01로 낮춤
            DEBUG_THRESHOLD = 0.01
            if final_confidence < DEBUG_THRESHOLD:
                print(
                    f"[ThreeJawGraspService] filtered: final={final_confidence:.3f} < {DEBUG_THRESHOLD}"
                )
                return None

            return {
                "event": "GRASP_POSE",
                "center_x": float(overlay_x),
                "center_y": float(overlay_y),
                "angle_rad": float(best.angle),
                "radius": float(best.width * 1.5),  # (인형 크기에 맞춰 배율 1.5로 상향)
                "jaw_count": 3,
                "confidence": final_confidence,
                "prediction_source": prediction_source,
                "image_width": w,
                "image_height": h,
            }
        except ValueError as ve:
            # "탐지된 파지 후보가 없습니다." 등의 에러
            print(f"[ThreeJawGraspService] no candidates: {ve}")
            return None
        except Exception as e:
            print(f"[ThreeJawGraspService] infer error: {e}")
            return None

    def begin_attempt(self, session_id: str, attempt_id: str) -> None:
        if self._learner is not None:
            self._learner.begin_attempt(session_id, attempt_id)

    def freeze_attempt(self, session_id: str) -> float | None:
        return self._learner.freeze_attempt(session_id) if self._learner else None

    def record_outcome(self, session_id: str, success: bool, **kwargs) -> bool:
        """마지막 파지 관측값에 성공/실패 라벨을 붙이고 자동 재학습을 예약한다."""
        if self._learner is None:
            return False
        return self._learner.complete_attempt(session_id, success, **kwargs)

    def discard_attempt(self, session_id: str) -> None:
        if self._learner is not None:
            self._learner.discard_attempt(session_id)

    @property
    def learning_status(self) -> dict:
        if self._learner is None:
            return {"enabled": False}
        stats = self._learner.dataset_stats()
        return {
            "enabled": self._learner.enabled,
            "training": self._learner.training,
            "samples": stats.total,
            "success": stats.success,
            "failure": stats.failure,
            "prediction_source": self._pipeline.evaluator.prediction_source,
            "training_samples": self._learner.dataset_stats("train").total,
            "holdout_samples": self._learner.dataset_stats("promotion").total,
            "model_version": self._pipeline.evaluator.model_metadata.get("model_version", "legacy"),
            "recovery_source": self._learner.recovery_source,
            "last_promotion": self._learner.last_promotion,
        }
