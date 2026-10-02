from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import (
    APP_HOST, APP_PORT,
    GRCONVNET_CHECKPOINT, GRASP_DEVICE,
    DETECTION_ENABLED, DETECTION_THRESHOLD, DETECTION_TARGET_LABELS,
    THREE_JAW_ENABLED, THREE_JAW_MODEL_PATH,
    THREE_JAW_MIN_BOX_AREA_RATIO, THREE_JAW_MAX_BOX_AREA_RATIO,
    THREE_JAW_MIN_MASK_FILL_RATIO, THREE_JAW_FACE_ONLY_MAX_AREA_RATIO,
    SUCCESS_LEARNING_ENABLED, SUCCESS_LEARNING_DATA_PATH, SUCCESS_MODEL_PATH,
    SUCCESS_LEARNING_MIN_SAMPLES, SUCCESS_LEARNING_RETRAIN_EVERY,
    SUCCESS_LEARNING_MIN_CLASS_SAMPLES, SUCCESS_LEARNING_EPOCHS,
    SUCCESS_LEARNING_BATCH_SIZE,
    SUCCESS_HOLDOUT_RATIO, SUCCESS_MAX_OBSERVATION_AGE,
    SUCCESS_PROMOTION_MIN_SAMPLES, SUCCESS_PROMOTION_MIN_CLASS_SAMPLES,
    SUCCESS_PROMOTION_MIN_BRIER_IMPROVEMENT, SUCCESS_PROMOTION_MAX_LOG_LOSS_REGRESSION,
    SUCCESS_PROMOTION_MIN_SLICE_SAMPLES, SUCCESS_PROMOTION_MAX_SLICE_BRIER_REGRESSION,
)
from src.learning.promotion import PromotionPolicy
from src.inference.detection_service import DetectionService
from src.inference.judge import CatchJudge
from src.inference.grasp_service import GraspService
from src.inference.three_jaw_service import ThreeJawGraspService
from src.network import ws_browser, ws_rpi
from src.network.spring_client import SpringClient
from src.recorder.video_recorder import VideoRecorder
from src.session_manager import SessionManager
from src.stream.relay_hub import RelayHub

# 의존성 인스턴스 (전역 1회 생성)
relay_hub = RelayHub()
recorder = VideoRecorder()
judge = CatchJudge()
spring = SpringClient()
grasp_service = GraspService(
    checkpoint_path=GRCONVNET_CHECKPOINT,
    device=GRASP_DEVICE,
)
detection_service = None
if DETECTION_ENABLED:
    detection_service = DetectionService(
        score_threshold=DETECTION_THRESHOLD,
        target_labels=DETECTION_TARGET_LABELS,
        device=GRASP_DEVICE,
    )
three_jaw_service = None
if THREE_JAW_ENABLED:
    three_jaw_service = ThreeJawGraspService(
        min_box_area_ratio=THREE_JAW_MIN_BOX_AREA_RATIO,
        max_box_area_ratio=THREE_JAW_MAX_BOX_AREA_RATIO,
        min_mask_fill_ratio=THREE_JAW_MIN_MASK_FILL_RATIO,
        face_only_max_area_ratio=THREE_JAW_FACE_ONLY_MAX_AREA_RATIO,
        success_learning_enabled=SUCCESS_LEARNING_ENABLED,
        success_learning_data_path=SUCCESS_LEARNING_DATA_PATH,
        success_model_path=SUCCESS_MODEL_PATH,
        success_learning_min_samples=SUCCESS_LEARNING_MIN_SAMPLES,
        success_learning_retrain_every=SUCCESS_LEARNING_RETRAIN_EVERY,
        success_learning_min_class_samples=SUCCESS_LEARNING_MIN_CLASS_SAMPLES,
        success_learning_epochs=SUCCESS_LEARNING_EPOCHS,
        success_learning_batch_size=SUCCESS_LEARNING_BATCH_SIZE,
        success_holdout_ratio=SUCCESS_HOLDOUT_RATIO,
        success_max_observation_age=SUCCESS_MAX_OBSERVATION_AGE,
        success_promotion_policy=PromotionPolicy(
            min_samples=SUCCESS_PROMOTION_MIN_SAMPLES,
            min_class_samples=SUCCESS_PROMOTION_MIN_CLASS_SAMPLES,
            min_brier_improvement=SUCCESS_PROMOTION_MIN_BRIER_IMPROVEMENT,
            max_log_loss_regression=SUCCESS_PROMOTION_MAX_LOG_LOSS_REGRESSION,
            min_slice_samples=SUCCESS_PROMOTION_MIN_SLICE_SAMPLES,
            max_slice_brier_regression=SUCCESS_PROMOTION_MAX_SLICE_BRIER_REGRESSION,
        ),
    )
session_manager = SessionManager(
    recorder=recorder, judge=judge, spring=spring,
    grasp_service=grasp_service,
    detection_service=detection_service,
    three_jaw_service=three_jaw_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    grasp_service.load()
    if detection_service is not None:
        detection_service.load()
    if three_jaw_service is not None:
        three_jaw_service.load(THREE_JAW_MODEL_PATH)
    print(f"[main] FastAPI ready on {APP_HOST}:{APP_PORT}")
    try:
        yield
    finally:
        await spring.close()
        print("[main] shutdown complete")


app = FastAPI(title="JIPCHAK AI Server", lifespan=lifespan)
app.include_router(ws_rpi.build_router(relay_hub, session_manager))
app.include_router(ws_browser.build_router(relay_hub, session_manager))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "subscribers": relay_hub.subscriber_count,
        "grasp_loaded": grasp_service.is_ready,
        "detection_loaded": detection_service.is_ready if detection_service else False,
        "three_jaw_loaded": (
            three_jaw_service is not None and three_jaw_service._pipeline is not None
        ),
        "success_learning": (
            three_jaw_service.learning_status if three_jaw_service else {"enabled": False}
        ),
    }
