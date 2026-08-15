"""
합성 데이터로 trainer.py 검증.

trainer.py 가 정상 작동하는지(차원 일치 / 수렴 / .pth 저장) end-to-end 테스트.

사용법:
    python -m ai.experiments.probability_v1.train_test \
        --data ai/experiments/probability_v1/data/synthetic_log.jsonl \
        --out  ai/experiments/probability_v1/models/evaluator_synthetic.pth
"""

import argparse
import sys
from pathlib import Path

# ai/three_jaw_grasp 패키지 import 를 위해 프로젝트 루트의 ai/ 경로 추가
_AI_ROOT = Path(__file__).resolve().parents[2]
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from three_jaw_grasp.trainer import train_evaluator_model


def main(args: argparse.Namespace) -> None:
    data_path = Path(args.data)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        raise SystemExit(
            f"데이터 파일 없음: {data_path}\n"
            f"먼저 generate_synthetic.py 를 실행하세요."
        )

    print(f"[train_test] data={data_path}")
    print(f"[train_test] out ={out_path}")
    train_evaluator_model(
        data_path=str(data_path),
        save_path=str(out_path),
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
    )
    print("[train_test] 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="합성 데이터로 trainer 검증")
    parser.add_argument(
        "--data", type=str,
        default="ai/experiments/probability_v1/data/synthetic_log.jsonl",
    )
    parser.add_argument(
        "--out", type=str,
        default="ai/experiments/probability_v1/models/evaluator_synthetic.pth",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=32)
    main(parser.parse_args())
