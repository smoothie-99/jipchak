import json
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np

from .candidate import GraspCandidate
from .feature_extractor import FeatureExtractor


class GraspDataLogger:
    """
    파지 시도 결과를 학습 데이터셋으로 기록하는 로거.
    """
    def __init__(self, log_file: str, extractor: FeatureExtractor):
        self.log_path = Path(log_file)
        self.extractor = extractor
        # 로그 파일을 저장할 디렉토리가 없으면 생성
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_attempt(self, candidate: GraspCandidate, depth: Optional[np.ndarray], success: bool, metadata: Dict[str, Any] = None):
        """파지 시도 1건을 로그 파일에 추가합니다."""
        features = self.extractor.extract(candidate, depth)

        log_entry = {
            "features": features.tolist(),
            "success": int(success),
            "candidate": candidate.__dict__, # GraspCandidate의 모든 필드를 기록
            "metadata": metadata or {}
        }
        # mask는 용량이 크므로 직렬화에서 제외
        if 'mask' in log_entry['candidate'] and log_entry['candidate']['mask'] is not None:
            log_entry['candidate']['mask'] = "omitted"

        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        print(f"[DataLogger] 파지 시도 기록 완료: {'성공' if success else '실패'} -> {self.log_path}")