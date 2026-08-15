import os
from dotenv import load_dotenv

load_dotenv()

# Server
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws/camera")
RECONNECT_INTERVAL = float(os.getenv("RECONNECT_INTERVAL", "3.0"))

# Camera
WEBCAM_PORT = int(os.getenv("WEBCAM_PORT", "0"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))
OPENNI2_REDIST_PATH = os.getenv("OPENNI2_REDIST_PATH", "")

# Compression
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
