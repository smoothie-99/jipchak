import cv2
import numpy as np
from typing import Tuple, Optional

from .base import BaseCamera
from ..config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, WEBCAM_PORT

class WebcamCamera(BaseCamera):
    """일반 USB 웹캠 제어 클래스"""
    
    def __init__(self):
        self.cap = None

    def start(self) -> None:
        """웹캠 캡처를 시작합니다."""
        # Linux 환경에서 USB 포트 번호를 기반으로 카메라 열기
        try:
            self.cap = cv2.VideoCapture(WEBCAM_PORT)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot open webcam on port {WEBCAM_PORT}")
                
            # 해상도 및 FPS 설정
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
            
            print(f"[WebcamCamera] Started successfully on port {WEBCAM_PORT}.")
        except Exception as e:
            print(f"[WebcamCamera] Error starting webcam: {e}")
            self.stop()
            raise

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """웹캠 RGB 프레임 획득 (Depth는 항상 None)"""
        if not self.cap or not self.cap.isOpened():
            return None, None
            
        try:
            ret, frame = self.cap.read()
            if not ret:
                return None, None
                
            # 패커가 OpenCV 포맷(BGR)을 처리하므로 변환 없이 반환
            return frame, None
            
        except Exception as e:
            print(f"[WebcamCamera] Error reading frame: {e}")
            return None, None

    def stop(self) -> None:
        """웹캠 리소스 해제"""
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        print("[WebcamCamera] Stopped.")
