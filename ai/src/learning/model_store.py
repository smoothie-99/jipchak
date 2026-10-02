"""Durable model installation, previous-version recovery and offline rollback."""
import os
import shutil
import tempfile
from pathlib import Path


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream, source.open("rb") as reader:
            shutil.copyfileobj(reader, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        if os.name == "posix":
            directory = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


class ModelStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.previous_path = self.path.with_name(self.path.name + ".previous")
        self.versions_dir = self.path.with_name(self.path.stem + "_versions")
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def recover(self, evaluator) -> str:
        for path in (self.path, self.previous_path):
            if not path.exists():
                continue
            try:
                prepared = evaluator.prepare_model(str(path))
                if path == self.previous_path:
                    atomic_copy(path, self.path)
                evaluator.activate_model(prepared)
                return "previous" if path == self.previous_path else "active"
            except Exception as exc:
                print(f"[ModelStore] recovery skipped {path.name}: {exc}")
        # No usable checkpoint: retain a healthy in-memory model, or the rule fallback.
        return "memory" if evaluator.snapshot_model() else "rule"

    def install(self, candidate_path: Path, evaluator, prepared=None) -> None:
        prepared = prepared or evaluator.prepare_model(str(candidate_path))
        original = evaluator.snapshot_model()
        has_previous = False
        if self.path.exists():
            # Do not overwrite a known-good backup with an invalid active file.
            evaluator.prepare_model(str(self.path))
            atomic_copy(self.path, self.previous_path)
            has_previous = True
        try:
            atomic_copy(candidate_path, self.path)
            evaluator.activate_model(prepared)
        except Exception:
            if has_previous:
                atomic_copy(self.previous_path, self.path)
            else:
                self.path.unlink(missing_ok=True)
            evaluator.activate_model(original)
            raise

    def rollback(self, evaluator) -> None:
        prepared = evaluator.prepare_model(str(self.previous_path))
        # Keep an immutable copy because install updates the previous pointer.
        rollback_path = self.versions_dir / "rollback-source.pth"
        atomic_copy(self.previous_path, rollback_path)
        self.install(rollback_path, evaluator, prepared)


if __name__ == "__main__":
    import argparse
    from three_jaw_grasp.evaluator import ThreeJawEvaluator
    from three_jaw_grasp.success_feature_extractor import SuccessFeatureExtractor

    parser = argparse.ArgumentParser(description="Rollback success model (stop AI server first)")
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    store = ModelStore(args.model)
    evaluator = ThreeJawEvaluator(extractor=SuccessFeatureExtractor())
    store.recover(evaluator)
    store.rollback(evaluator)
    print(f"Rolled back {store.path}; restart the AI server to apply.")
