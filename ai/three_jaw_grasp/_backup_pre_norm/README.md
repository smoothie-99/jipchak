# Backup: 정규화 통합 작업 직전 스냅샷

## 목적

`trainer.py` 와 `evaluator.py` 에 feature normalization (mean/std) 을
통합하기 직전의 원본 파일 백업.

작업이 잘못되면 이 폴더의 파일로 즉시 복원 가능.

## 복원 방법

```bash
cp ai/three_jaw_grasp/_backup_pre_norm/trainer.py   ai/three_jaw_grasp/trainer.py
cp ai/three_jaw_grasp/_backup_pre_norm/evaluator.py ai/three_jaw_grasp/evaluator.py
```

## 통합 작업 성공 + dev 머지 후 이 폴더는 삭제할 것.
