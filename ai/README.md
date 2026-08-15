# JIPCHAK AI Server

라즈베리파이에서 송출한 카메라 스트림을 받아
**브라우저 릴레이 / mp4 녹화 / 잡힘 판정 / Spring 결과 전송**을 수행하는 FastAPI 서버.

```
[RPi] ──WS──► [AI 서버] ──┬──► [React 브라우저] (영상 미리보기)
                          ├──► [mp4 파일]      (영상 녹화)
                          └──► [Spring Boot]   (게임 결과 POST)
```

---

## 요구사항

- Python 3.11 이상 (테스트 환경: 3.12)
- (옵션) Docker

## 빠른 시작 (로컬)

```bash
cd ai
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt    # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # Linux/Mac

cp .env.example .env       # 환경변수 편집
.venv/Scripts/python -m uvicorn main:app --reload --port 8000
```

서버가 뜨면 헬스체크:
```bash
curl http://localhost:8000/health
# → {"status":"ok","subscribers":0}
```

## 빠른 시작 (Docker)

```bash
cd ai
docker build -t jipchak-ai .
docker run --rm -p 8000:8000 \
  -v $(pwd)/data:/data \
  -e SPRING_API_BASE_URL=http://host.docker.internal:8080 \
  jipchak-ai
```

`infra/docker-compose.yml` 통합은 별도 브랜치에서 진행 (`ai-jipchak` 서비스 추가 예정).

---

## 환경변수

| 키 | 기본값 | 설명 |
|----|--------|------|
| `APP_HOST` | `0.0.0.0` | FastAPI 바인드 주소 |
| `APP_PORT` | `8000` | FastAPI 포트 |
| `SPRING_API_BASE_URL` | `http://app-jipchak:8080` | Spring Boot 컨테이너 URL |
| `RECORDING_DIR` | `/data/recordings` | mp4 저장 경로 |
| `VIDEO_FPS` | `30` | mp4 재생 FPS |
| `VIDEO_CODEC` | `mp4v` | OpenCV FourCC |
| `LOG_LEVEL` | `INFO` | (예약) |

---

## WebSocket 프로토콜

### `/ws/camera` — RPi → AI

라즈베리파이가 **송신 전용**으로 사용하는 엔드포인트.

| 메시지 형태 | 내용 | 예시 |
|-------------|------|------|
| **텍스트 (제어)** | JSON | `{"event":"START","session_id":"abc"}` / `{"event":"STOP","session_id":"abc"}` |
| **바이너리 (프레임)** | msgpack | `embedded/raspberrypi/.../utils/packer.py::FramePacker.pack()` 출력 그대로 |

#### 바이너리 페이로드 스키마

```python
{
  "timestamp": int,          # 나노초
  "color_2d": bytes,         # JPEG 인코딩된 일반 웹캠 RGB
  "color_3d": bytes,         # JPEG 인코딩된 D435 RGB
  "depth_3d": bytes,         # LZ4 압축된 uint16 Depth
  "depth_3d_shape": tuple    # (H, W)
}
```

#### 동작 시퀀스

1. RPi가 WS 연결 후 **START** 텍스트 송신
2. 30fps 바이너리 프레임 송신
3. 프레임 수신 시 AI 서버는:
   - **즉시** 모든 브라우저 구독자에게 fan-out (지연 최소화)
   - 활성 세션이면 디코딩 → mp4 적재 + 마지막 프레임 보관
4. 게임 종료 시 RPi가 **STOP** 텍스트 송신
5. AI 서버는 `CatchJudge` 호출 → Spring Boot에 multipart 업로드
6. WS 연결이 STOP 없이 끊겨도 활성 세션은 자동 정리됨

### `/ws/stream` — AI → 브라우저

브라우저가 **수신 전용**으로 구독하는 엔드포인트.

- 페이로드는 RPi가 보낸 바이너리를 **그대로** 릴레이
- 브라우저는 `msgpack-lite` + `cv2.imdecode` 와 동등한 디코딩을 직접 수행
- 송신 실패 시 자동 구독 해제 (느린 클라이언트가 전체를 막지 않음)

브라우저 예시:
```js
const ws = new WebSocket("ws://localhost:8000/ws/stream");
ws.binaryType = "arraybuffer";
ws.onmessage = (e) => {
  // msgpack.decode(e.data) → JPEG 바이트 → <img src="blob:..."> 또는 canvas
};
```

---

## 디렉토리 구조

```
ai/
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── .env.example
├── main.py                          # FastAPI 엔트리 + DI 결합
├── scripts/
│   └── mock_rpi.py                  # RPi 없이 ai 서버를 단독 검증
├── src/
│   ├── config.py                    # 환경변수 로딩
│   ├── session_manager.py           # 세션 lifecycle 조율
│   ├── stream/
│   │   ├── unpacker.py              # FramePacker 역방향 (msgpack 디코딩)
│   │   └── relay_hub.py             # RPi → 다중 브라우저 fan-out
│   ├── network/
│   │   ├── ws_rpi.py                # /ws/camera 엔드포인트
│   │   ├── ws_browser.py            # /ws/stream 엔드포인트
│   │   └── spring_client.py         # Spring /api/game/log POST
│   ├── recorder/
│   │   └── video_recorder.py        # 세션별 mp4 녹화
│   └── inference/
│       └── judge.py                 # 잡힘 판정 (현재 더미)
└── tests/
    ├── test_unpacker.py
    ├── test_relay_hub.py
    ├── test_video_recorder.py
    ├── test_session_manager.py
    └── test_judge.py
```

---

## 테스트

```bash
.venv/Scripts/python -m pytest tests/ -v
# 21 passed in <1s
```

## RPi 없이 검증하기

서버를 띄운 채로 다른 터미널에서:

```bash
cd ai
.venv/Scripts/python scripts/mock_rpi.py \
  --url ws://localhost:8000/ws/camera \
  --frames 60 \
  --fps 30
```

종료 후 `RECORDING_DIR` 에 mp4 파일이 생성되어 있어야 함.

브라우저 릴레이까지 확인하려면 `wscat` 같은 도구로 `/ws/stream` 에 접속:

```bash
npx wscat -c ws://localhost:8000/ws/stream --no-color
```

---

## 향후 개선 사항

- [ ] `print()` → `logging` 전환 (uvicorn 라이브 로그 출력 정렬)
- [ ] 잡힘 판정 실로직 (Depth 임계값 → ONNX 모델)
- [ ] cv2.VideoWriter 동기 호출을 `asyncio.to_thread` 로 오프로드
- [ ] 영상 업로드 실패 시 재시도 큐
- [ ] WSS (TLS) — Nginx upstream에서 종단

## 컴포넌트 책임 (RPi vs AI)

상세는 팀 위키 / 인프라 구성도 참조. 핵심 원칙:

- **RPi**: 카메라 캡처, 모터·아두이노 직접 제어 (실시간성 ms 단위)
- **AI**: 영상 분석·녹화·릴레이·백엔드 통신 (실시간성 100ms 이상 OK)
