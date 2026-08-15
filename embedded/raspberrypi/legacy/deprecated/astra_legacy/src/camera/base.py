from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np

class BaseCamera(ABC):
    """카메라 디바이스의 추상 기본 클래스"""
    
    @abstractmethod
    def start(self) -> None:
        """카메라 스트림을 시작합니다."""
        pass
        
    @abstractmethod
    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """RGB(uint8) 및 Depth(uint16) 프레임 획득"""
        pass
        
    @abstractmethod
    def stop(self) -> None:
        """카메라 스트림 종료 및 리소스 해제"""
        pass
