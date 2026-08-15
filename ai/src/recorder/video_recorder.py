import os
import time
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np

from ..config import RECORDING_DIR, VIDEO_FPS, VIDEO_CODEC


class VideoRecorder:
    """
    세션(=한 게임 한 판)별로 mp4 파일을 적재한다.

    동시성 가정: 같은 session_id에 대해 start/write/stop 은 단일 호출자
    (RPi WS 핸들러)에서만 호출된다. 다른 session_id 끼리는 await 없이
    수행되는 동기 dict 연산이라 asyncio race-free.

    사용 흐름:
        recorder.start_session(session_id, frame_shape)
        recorder.write(session_id, bgr_frame)   # 매 프레임
        path = recorder.stop_session(session_id) # 종료 → 파일 경로 반환
    """

    def __init__(self) -> None:
        self._writers: Dict[str, cv2.VideoWriter] = {}
        self._paths: Dict[str, str] = {}
        Path(RECORDING_DIR).mkdir(parents=True, exist_ok=True)

    def start_session(self, session_id: str, frame_shape: tuple) -> str:
        """frame_shape = (H, W, C) 또는 (H, W). 컬러만 지원."""
        if session_id in self._writers:
            print(f"[VideoRecorder] session {session_id} already recording, restarting")
            self.stop_session(session_id)

        h, w = frame_shape[:2]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.mp4"
        path = os.path.join(RECORDING_DIR, filename)

        fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
        writer = cv2.VideoWriter(path, fourcc, VIDEO_FPS, (w, h))
        if not writer.isOpened():
            raise RuntimeError(f"Cannot open VideoWriter for {path}")

        self._writers[session_id] = writer
        self._paths[session_id] = path
        print(f"[VideoRecorder] start session={session_id} -> {path}")
        return path

    def write(self, session_id: str, frame_bgr: np.ndarray) -> None:
        writer = self._writers.get(session_id)
        if writer is None:
            return  # 세션 시작 전에 들어온 프레임은 버린다
        writer.write(frame_bgr)

    def stop_session(self, session_id: str) -> Optional[str]:
        writer = self._writers.pop(session_id, None)
        path = self._paths.pop(session_id, None)
        if writer is not None:
            writer.release()
            print(f"[VideoRecorder] stop session={session_id} -> {path}")
        return path

    def is_recording(self, session_id: str) -> bool:
        return session_id in self._writers
