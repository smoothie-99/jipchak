import os
from dotenv import load_dotenv

load_dotenv()

# FastAPI
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Spring Boot Backend
SPRING_API_BASE_URL = os.getenv("SPRING_API_BASE_URL", "http://app-jipchak:8080")
SPRING_GAME_LOG_PATH = "/api/game/log"

# 녹화 설정
RECORDING_DIR = os.getenv("RECORDING_DIR", "/data/recordings")
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_CODEC = os.getenv("VIDEO_CODEC", "mp4v")

# GR-ConvNet 체크포인트
GRCONVNET_CHECKPOINT = os.getenv(
    "GRCONVNET_CHECKPOINT",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "trained-models",
        "cornell-randsplit-rgbd-grconvnet3-drop1-ch16",
        "epoch_30_iou_0.97",
    ),
)
GRASP_DEVICE = os.getenv("GRASP_DEVICE", "cpu")

# Object Detection (SSDLite)
DETECTION_ENABLED = False  # 무조건 비활성화 (기존: os.getenv("DETECTION_ENABLED", "true").lower() == "true")
DETECTION_THRESHOLD = float(os.getenv("DETECTION_THRESHOLD", "0.35"))
DETECTION_TARGET_LABELS = [
    int(x) for x in os.getenv("DETECTION_TARGET_LABELS", "88").split(",") if x.strip()
]

# YOLO26s-seg + ThreeJawGrasp 파이프라인 (병아리/오리인형 전용 학습 모델)
THREE_JAW_ENABLED = os.getenv("THREE_JAW_ENABLED", "true").lower() == "true"
THREE_JAW_MODEL_PATH = os.getenv(
    "THREE_JAW_MODEL_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "trained-models",
        "best_v4.pt",
    ),
)

# YOLO26s-seg candidate filtering (to hide overlay on partial views like face-only)
THREE_JAW_MIN_BOX_AREA_RATIO = float(os.getenv("THREE_JAW_MIN_BOX_AREA_RATIO", "0.04"))
THREE_JAW_MAX_BOX_AREA_RATIO = float(os.getenv("THREE_JAW_MAX_BOX_AREA_RATIO", "0.60"))
THREE_JAW_MIN_MASK_FILL_RATIO = float(os.getenv("THREE_JAW_MIN_MASK_FILL_RATIO", "0.35"))
THREE_JAW_FACE_ONLY_MAX_AREA_RATIO = float(os.getenv("THREE_JAW_FACE_ONLY_MAX_AREA_RATIO", "0.12"))

# 로그
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
