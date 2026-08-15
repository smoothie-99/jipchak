import json
import os
import shutil
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import numpy as np

from three_jaw_grasp.candidate import GraspCandidate
from three_jaw_grasp.evaluator import ThreeJawEvaluator
from three_jaw_grasp.feature_extractor import FeatureExtractor
from three_jaw_grasp.trainer import train_evaluator_model


@dataclass(frozen=True)
class DatasetStats:
    total: int = 0
    success: int = 0
    failure: int = 0


@dataclass
class _PendingAttempt:
    features: list[float]
    predicted_probability: float
    metadata: dict[str, Any]


class AutoSuccessLearner:
    """
    마지막 파지 특징과 실제 성공/실패를 연결해 JSONL로 누적하고,
    데이터가 충분해지면 별도 스레드에서 MLP를 재학습한다.

    학습 완료 파일은 임시 경로에서 검증한 뒤 os.replace로 교체하므로
    추론 중 불완전한 체크포인트를 읽지 않는다.
    """

    def __init__(
        self,
        data_path: str,
        model_path: str,
        evaluator: ThreeJawEvaluator,
        enabled: bool = True,
        min_samples: int = 30,
        retrain_every: int = 10,
        min_class_samples: int = 5,
        epochs: int = 120,
        batch_size: int = 32,
    ) -> None:
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.evaluator = evaluator
        self.extractor: FeatureExtractor = evaluator.extractor
        self.enabled = enabled
        self.min_samples = max(4, int(min_samples))
        self.retrain_every = max(1, int(retrain_every))
        self.min_class_samples = max(1, int(min_class_samples))
        self.epochs = max(1, int(epochs))
        self.batch_size = max(1, int(batch_size))

        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        self._pending: dict[str, _PendingAttempt] = {}
        self._data_lock = threading.RLock()
        self._training_lock = threading.Lock()
        self._training = False
        self._training_thread: Optional[threading.Thread] = None
        self._last_trained_count = int(
            evaluator.model_metadata.get("sample_count", 0)
        )

    @property
    def training(self) -> bool:
        with self._training_lock:
            return self._training

    def remember_attempt(
        self,
        session_id: str,
        candidate: GraspCandidate,
        depth: Optional[np.ndarray],
        predicted_probability: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if not self.enabled or not session_id:
            return

        features = self.extractor.extract(candidate, depth)
        if features.shape != (self.extractor.FEATURE_DIM,) or not np.all(
            np.isfinite(features)
        ):
            print(f"[AutoSuccessLearner] invalid features skipped: session={session_id}")
            return

        with self._data_lock:
            # 한 게임에서 추론이 여러 번 실행되므로 실제 집게 하강 직전에 가장 가까운
            # 마지막 관측값만 정답 라벨과 연결한다.
            self._pending[session_id] = _PendingAttempt(
                features=features.astype(float).tolist(),
                predicted_probability=float(
                    np.clip(predicted_probability, 0.0, 1.0)
                ),
                metadata=dict(metadata or {}),
            )

    def discard_attempt(self, session_id: str) -> None:
        with self._data_lock:
            self._pending.pop(session_id, None)

    def complete_attempt(self, session_id: str, success: bool) -> bool:
        """결과를 기록하고 필요하면 비동기 재학습을 시작한다."""
        if not self.enabled:
            return False

        with self._data_lock:
            attempt = self._pending.pop(session_id, None)
            if attempt is None:
                return False

            entry = {
                "session_id": session_id,
                "features": attempt.features,
                "success": int(bool(success)),
                "predicted_probability": attempt.predicted_probability,
                "feature_dim": self.extractor.FEATURE_DIM,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "metadata": attempt.metadata,
            }
            with self.data_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

        print(
            f"[AutoSuccessLearner] outcome saved: session={session_id} "
            f"result={'success' if success else 'failure'}"
        )
        return self.start_retraining_if_needed()

    def dataset_stats(self) -> DatasetStats:
        with self._data_lock:
            return self._dataset_stats_for(self.data_path)

    def _dataset_stats_for(self, path: Path) -> DatasetStats:
        if not path.exists():
            return DatasetStats()

        total = success = failure = 0
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    features = row.get("features", [])
                    label = int(row.get("success"))
                    if len(features) != self.extractor.FEATURE_DIM or label not in (0, 1):
                        continue
                    if not np.all(np.isfinite(np.asarray(features, dtype=np.float32))):
                        continue
                    total += 1
                    success += label
                    failure += 1 - label
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
        return DatasetStats(total=total, success=success, failure=failure)

    def start_retraining_if_needed(self) -> bool:
        stats = self.dataset_stats()
        if not self._is_trainable(stats):
            return False

        with self._training_lock:
            if self._training:
                return False
            self._training = True
            self._training_thread = threading.Thread(
                target=self._train_worker,
                args=(stats,),
                name="jipchak-success-trainer",
                daemon=True,
            )
            self._training_thread.start()
        return True

    def _is_trainable(self, stats: DatasetStats) -> bool:
        if not self.enabled or stats.total < self.min_samples:
            return False
        if min(stats.success, stats.failure) < self.min_class_samples:
            return False
        if self._last_trained_count == 0:
            return True
        return stats.total - self._last_trained_count >= self.retrain_every

    def _train_worker(self, stats: DatasetStats) -> None:
        temp_path = self.model_path.with_name(
            f".{self.model_path.name}.{uuid4().hex}.tmp"
        )
        snapshot_path = self.data_path.with_name(
            f".{self.data_path.name}.{uuid4().hex}.snapshot"
        )
        try:
            # 학습 중 새 게임 결과가 추가되어도 이번 학습 데이터와 metadata의
            # sample_count가 달라지지 않도록 잠깐 잠근 뒤 스냅샷을 만든다.
            with self._data_lock:
                shutil.copyfile(self.data_path, snapshot_path)
            stats = self._dataset_stats_for(snapshot_path)
            metadata = {
                **asdict(stats),
                "sample_count": stats.total,
                "feature_dim": self.extractor.FEATURE_DIM,
                "trained_at": datetime.now(timezone.utc).isoformat(),
            }
            train_evaluator_model(
                data_path=str(snapshot_path),
                save_path=str(temp_path),
                epochs=self.epochs,
                batch_size=self.batch_size,
                feature_dim=self.extractor.FEATURE_DIM,
                metadata=metadata,
            )
            os.replace(temp_path, self.model_path)
            if not self.evaluator.load_model(str(self.model_path)):
                raise RuntimeError("새 모델 hot-reload 실패")
            self._last_trained_count = stats.total
            print(
                f"[AutoSuccessLearner] retraining complete: "
                f"samples={stats.total} success={stats.success} failure={stats.failure}"
            )
        except Exception as exc:
            print(f"[AutoSuccessLearner] retraining failed: {exc}")
        finally:
            if temp_path.exists():
                temp_path.unlink()
            if snapshot_path.exists():
                snapshot_path.unlink()
            with self._training_lock:
                self._training = False

    def wait_for_training(self, timeout: Optional[float] = None) -> None:
        """테스트와 정상 종료 시 사용할 수 있는 선택적 대기 메서드."""
        thread = self._training_thread
        if thread is not None:
            thread.join(timeout=timeout)
