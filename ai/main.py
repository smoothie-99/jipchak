from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import (
    APP_HOST, APP_PORT,
    GRCONVNET_CHECKPOINT, GRASP_DEVICE,
    DETECTION_ENABLED, DETECTION_THRESHOLD, DETECTION_TARGET_LABELS,
    THREE_JAW_ENABLED, THREE_JAW_MODEL_PATH,
    THREE_JAW_MIN_BOX_AREA_RATIO, THREE_JAW_MAX_BOX_AREA_RATIO,
    THREE_JAW_MIN_MASK_FILL_RATIO, THREE_JAW_FACE_ONLY_MAX_AREA_RATIO,
)
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
    }
