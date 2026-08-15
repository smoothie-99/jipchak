import cv2
import numpy as np
from openni import openni2
from typing import Tuple, Optional

from .base import BaseCamera
from ..config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS, OPENNI2_REDIST_PATH

class AstraCamera(BaseCamera):
    def __init__(self):
        self.device = None
        self.depth_stream = None
        self.color_stream = None

    def start(self) -> None:
        """OpenNI2 초기화 및 스트림 시작 (Device Sync 활성화)"""
        try:
            # SDK 경로가 설정되어 있으면 해당 경로의 라이브러리 로드
            if OPENNI2_REDIST_PATH:
                openni2.initialize(OPENNI2_REDIST_PATH)
            else:
                openni2.initialize()
                
            self.device = openni2.Device.open_any()
            
            # --- Device-level Synchronization (가장 중요) ---
            if self.device.get_depth_color_sync_enabled() is False:
                try:
                    self.device.set_depth_color_sync_enabled(True)
                    print("[AstraCamera] Device-level Depth-Color sync enabled.")
                except Exception as e:
                    print(f"[AstraCamera] Warning: Could not enable depth-color sync: {e}")
            
            # Depth Stream 설정
            self.depth_stream = self.device.create_depth_stream()
            self.depth_stream.set_video_mode(
                openni2.c_api.OniVideoMode(
                    pixelFormat=openni2.c_api.OniPixelFormat.ONI_PIXEL_FORMAT_DEPTH_100_UM,
                    resolutionX=CAMERA_WIDTH,
                    resolutionY=CAMERA_HEIGHT,
                    fps=CAMERA_FPS
                )
            )
            
            # Color Stream 설정
            self.color_stream = self.device.create_color_stream()
            self.color_stream.set_video_mode(
                openni2.c_api.OniVideoMode(
                    pixelFormat=openni2.c_api.OniPixelFormat.ONI_PIXEL_FORMAT_RGB888,
                    resolutionX=CAMERA_WIDTH,
                    resolutionY=CAMERA_HEIGHT,
                    fps=CAMERA_FPS
                )
            )
            
            self.depth_stream.start()
            self.color_stream.start()
            print("[AstraCamera] Camera streams started successfully.")
            
        except Exception as e:
            print(f"[AstraCamera] Error starting camera: {e}")
            self.stop()
            raise

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """RGB, Depth 동기화 프레임 반환"""
        if not self.depth_stream or not self.color_stream:
            return None, None
            
        rgb_array = None
        depth_array = None
        
        try:
            color_frame = self.color_stream.read_frame()
            color_data = color_frame.get_buffer_as_uint8()
            rgb_array = np.ndarray((color_frame.height, color_frame.width, 3),
                                   dtype=np.uint8,
                                   buffer=color_data)
                                   
            depth_frame = self.depth_stream.read_frame()
            depth_data = depth_frame.get_buffer_as_uint16()
            depth_array = np.ndarray((depth_frame.height, depth_frame.width),
                                     dtype=np.uint16,
                                     buffer=depth_data)
        except Exception as e:
            # 타임아웃이나 스트림 오류 발생 시 로깅만 하고 확보된 프레임까지만 반환
            print(f"[AstraCamera] Stream reading partial error: {e}")
            
        return rgb_array, depth_array

    def stop(self) -> None:
        """스트림 정지 및 리소스 해제"""
        if self.depth_stream:
            self.depth_stream.stop()
            self.depth_stream = None
        if self.color_stream:
            self.color_stream.stop()
            self.color_stream = None
        if self.device:
            self.device.close()
            self.device = None
        openni2.unload()
        print("[AstraCamera] Camera stopped and resources released.")
