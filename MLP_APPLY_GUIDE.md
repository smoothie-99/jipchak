# JIPCHAK MLP 변경 파일 적용 안내

이 ZIP은 `smoothie-99/jipchak`의 `feat/ai` 브랜치 최신 커밋
`b1c7b758fa0805675af10a1d1baa5ab5376e328e`를 기준으로 작성한 변경 파일 묶음입니다.

## 적용 순서

1. 현재 브랜치와 작업 상태를 확인합니다.

   ```bash
   git switch feat/ai
   git pull --ff-only origin feat/ai
   git status
   ```

2. ZIP 내부의 `README.md`, `ai/`, `backend/`, `frontend/`를 기존
   `jipchak` 폴더 최상위에 복사하고 파일 덮어쓰기를 허용합니다.

3. 변경 내용을 확인하고 커밋합니다.

   ```bash
   git status
   git diff --check
   git add README.md ai backend frontend
   git commit -m "feat: learn and upload grasp success probability"
   git push origin feat/ai
   ```

## 주요 구현

- 16차원 파지 특징을 입력으로 사용하는 `16 -> 64 -> 32 -> 1` MLP
- 성공·실패 결과의 JSONL 누적과 백그라운드 자동 재학습
- 계층 분할, feature 표준화, Early Stopping, Isotonic calibration
- 새 모델의 원자적 교체와 추론기 Hot Reload
- 학습 전 규칙 기반 확률, 학습 후 MLP 성공 확률 사용
- 성공 확률·실제 결과·영상의 Spring Boot 업로드 및 저장

