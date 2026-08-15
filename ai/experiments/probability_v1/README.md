# Probability v1: 파지 성공 확률 분석 / 학습 파이프라인 검증

## 목적

키오스크 화면에 표시되는 "%" 가 실제 파지 성공률에 근접한 **진짜 확률** 이 되도록 만드는
학습 + calibration 파이프라인을 운영 코드 (`ai/three_jaw_grasp/`) 안 건드리고 검증한다.

실제 하드웨어 데이터 수집 전에 다음을 확인:
- `trainer.py` end-to-end 동작
- Feature normalization 효과
- Early stopping / best-model 저장
- Calibration 방법 비교 (Platt vs Isotonic)
- `.pth` 포맷 확장 (norm stats, iso mapping)

## 폴더 구조

```
ai/experiments/probability_v1/
├── README.md                       ← 이 파일
├── generate_synthetic.py           ← 합성 데이터 생성
├── train_test.py                   ← baseline (정규화 X) trainer 호출
├── train_test_normalized.py        ← 정규화 + early stopping 학습
├── analyze_calibration.py          ← ECE + Platt + Isotonic 분석
├── data/
│   └── synthetic_log.jsonl         ← 합성 (features, success) jsonl
└── models/
    ├── evaluator_synthetic.pth     ← baseline 학습 결과
    ├── evaluator_normalized.pth    ← 정규화 + early stop 학습 결과
    └── evaluator_with_iso.pth      ← 운영 trainer 포함 결과 (norm + iso)
```

## 사용법

### 1. 합성 데이터 생성

```bash
python ai/experiments/probability_v1/generate_synthetic.py --n 2000
```

옵션:
- `--n`: 샘플 개수 (기본 200, 권장 2000)
- `--seed`: 랜덤 시드 (기본 42)
- `--out`: 출력 jsonl 경로

`FeatureExtractor.FEATURE_DIM=11` 과 일치하는 11차원 vector + binary success 라벨.
라벨은 width/sensor_invalid/relative_grasp_y 조합으로 결정 + 5% 라벨 플립 노이즈.

### 2. 학습 (정규화 + early stopping)

```bash
python ai/experiments/probability_v1/train_test_normalized.py
```

- train/val 80/20 split
- train split 만 사용해 feature mean/std 계산
- patience=15 early stopping
- best val_loss 모델 저장 (`.pth` dict 포맷)

### 3. Calibration 분석

```bash
python ai/experiments/probability_v1/analyze_calibration.py
```

출력:
- raw 룰 점수의 reliability diagram + ECE
- Platt scaling 학습 + 보정 후 ECE
- Isotonic regression 학습 + 보정 후 ECE
- 70/30 fit/eval split 으로 정직한 일반화 ECE 측정

## 핵심 발견

### Finding 1: Feature normalization 필수

`feature_extractor.extract()` 출력은 scale 차이가 큼 (예: width 20~100, ratio 0~1).
정규화 없이 학습 시도하면 큰 값 feature 가 gradient 다 먹어서 학습 안 됨.

| 정규화 | Val Acc | 진단 |
|---|---|---|
| ❌ | 57.5% | majority baseline 근처. 학습 실패 |
| ✅ | 87~89% | 정상 학습 |

운영 `trainer.py` 에 통합됨 (커밋 0089aab) — train split mean/std 자동 계산 + `.pth` 저장.

### Finding 2: Feature 17 → 11 차원 축소 가능

도메인 추론으로 중복/약신호 feature 6개 드롭:
- 드롭: depth 통계 5개 (mean/min/max/p25/p75 — median과 중복) + relative_grasp_x
- 합성 데이터에서 val acc 동일 유지 (87.50%)
- 데이터 수집 목표 1000건 → ~300건으로 완화 가능

### Finding 3: 룰 기반 점수는 진짜 확률 아님

`ChickEvaluator._calculate_rule_score()` 출력은 ranking 신호일 뿐:

| 방법 | ECE (eval 30% 정직한 측정) |
|---|---|
| raw 룰 점수 | 0.2752 |
| Platt scaling | 0.2386 |
| **Isotonic regression** | **0.0213** ← 추천 |

룰 점수는 0.5 경계 절벽 효과 ("55%" 표시되지만 실제론 5% 또는 95%).
Isotonic regression 으로 후처리하면 진짜 성공률에 근접.

### Finding 4: 운영 통합 (Isotonic)

운영 `trainer.py` + `evaluator.py` 에 isotonic calibration 통합 (별도 PR):
- 학습 후 val split sigmoid 출력으로 PAV 알고리즘 학습
- `.pth` 에 `iso_x`, `iso_y` 함께 저장
- 추론 시 `evaluator._mlp_scores()` 가 자동 적용

## 실제 데이터 흐름 (강한솔 합류)

```
[운영 데이터 수집]
키오스크 게임 → 성공/실패 → ai/data_logger.py → grasp_log.jsonl

[학습]
python -m three_jaw_grasp.trainer \
    --data grasp_log.jsonl \
    --out evaluator_model.pth
        ↓
.pth 안에:
- state_dict (MLP 가중치)
- norm_mean, norm_std (정규화 통계)
- iso_x, iso_y (calibration 매핑)
- best_epoch, best_val_acc

[추론 (자동)]
ChickEvaluator(model_path="evaluator_model.pth")
    → 자동으로 정규화 + sigmoid + isotonic 적용
    → 화면에 표시되는 "%" 가 진짜 성공률
```

## 실제 데이터 학습 시 주의사항

1. **데이터 1000건 → ~300건** 도 가능 (11차원이라)
2. **정규화 / early stopping / isotonic** 모두 trainer.py 에 자동 통합됨 — 그대로 호출만
3. **인형 종류 다 섞기** — 병아리만 학습하고 너구리 val 에 넣으면 망함
4. **시간 분리** — 5월 1일~10일 → train, 11일~14일 → val (data leak 방지)
5. **`analyze_calibration.py --data <실제 jsonl>`** 로 ECE 다시 확인

## 한계 / TODO

- 합성 데이터는 임의 공식으로 만든 라벨이라 진짜 학습 가능성을 검증한 것일 뿐, 실제 성능은 데이터 수집 후 재측정 필요
- K-fold cross validation 미구현 (1회 80/20 split)
- 도메인 갭 (핸드폰 학습 → D435 추론) 은 별도 해결 필요 (`interactive_grasp_hotkey.py` 실연결)
- YOLO 검출 단계 정확도는 본 실험 scope 밖 (강한솔 영역)
