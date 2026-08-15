#include "StateMachine.h"
#include "../config.h"

/**
 * 게임 한 판 흐름 (GameCountModal 도입 후):
 *   IDLE → READY (파랑) → PLAYING (조이스틱 첫 입력) → 집기 시퀀스 → POST_GAME → 다음판 자동 or 세션 종료
 *
 * READY 단계:
 *   - 캠 ON, Frontend 의 GameCountModal 표시
 *   - 조이스틱 좌/우 edge → 모달 옵션 순환 이벤트 (JOY_LEFT/RIGHT)
 *   - 파랑 → PLAYING 진입 (모달의 "시작" 트리거)
 *   - 빨강 → IDLE + BACK_TO_HOME 이벤트 (모달의 "뒤로" 트리거)
 *
 * PLAYING 단계:
 *   - PLAYING 진입 시점엔 playStartTime = 0 (아직 타이머 미작동)
 *   - 첫 조이스틱 입력 시 playStartTime 설정 + ROUND_TIMER_START 이벤트 송신
 *   - playStartTime 설정 후 PLAY_TIMEOUT_MS (20초) 만료 시 자동 GRAB
 *   - 빨강 → 즉시 GRAB
 *   - PLAYING_IDLE_TIMEOUT_MS (60초) 동안 조이스틱 무동작 → 사용자 이탈 추정, IDLE 진입
 *
 * POST_GAME 단계:
 *   - 결과 표시 + POST_GAME_TO_PLAYING_MS (5초) 후 자동 PLAYING 진입
 *   - 중간 종료 불가 (빨강/파랑 무동작)
 *   - 세션 전체 종료는 Frontend 의 maxGames 도달 시 또는 PLAYING IDLE_TIMEOUT 으로
 */

StateMachine::StateMachine(
    CommManager* c, MotorManager* m, MotorAuto* ma,
    MotorManual* mm, ClawManager* cl, InputManager* in)
    : comm(c), motor(m), motorAuto(ma), motorManual(mm),
      claw(cl), input(in),
      currentState(IDLE),
      lastStatusTime(0),
      playStartTime(0),
      playingEnteredTime(0),
      postGameEnteredTime(0),
      idleEnteredTime(0),
      roundsPlayed(0),
      subState(0),
      prevJoyX(0),
      prevJoyY(0) {}

void StateMachine::init() {
    motor->init();
    claw->init();
    input->init();
    // 부팅 직후 3초 쿨다운 적용. millis() 0 기준이면 부팅 직후 가드가
    // 통과되어 손에 닿은 버튼이 즉시 READY 진입을 트리거할 수 있다.
    idleEnteredTime = millis();
}

bool StateMachine::isPlayingTimeout() const {
    // 조이스틱 첫 입력 후에만 타이머 작동.
    return playStartTime > 0 && (millis() - playStartTime) >= PLAY_TIMEOUT_MS;
}

void StateMachine::startGrabSequence() {
    // 조이스틱 잔재 제거 (manual mode → ready)
    motorManual->setDirectionX(0);
    motorManual->setDirectionY(0);
    motor->setManualMode(false);

    motorAuto->moveZ(-Z_MOVE_STEPS_DOWN);
    currentState = GRAB_DOWN;
}

void StateMachine::enterPlaying() {
    // PLAYING 진입 시 공통: 집게 열림 보장 + 배출구 복귀 target + 타이머 초기화 + 조이스틱 edge 초기화.
    // 명시적 open() 으로 매 판 시작 시 열림 상태 보장. Z 하강 시점엔 서보가 이미 위치 도달.
    claw->open();
    motorAuto->setTarget(DROP_OFF_X_MM, DROP_OFF_Y_MM);
    playStartTime = 0;                    // 조이스틱 첫 입력까지 타이머 정지
    playingEnteredTime = millis();        // safety timeout 기준점
    prevJoyX = 0;
    prevJoyY = 0;
    currentState = PLAYING;
}

void StateMachine::update() {
    // 100ms 마다 RPi 에 현재 위치 + state 송신
    if (millis() - lastStatusTime >= 100) {
        comm->sendStatus(
            motor->getStepperX().currentPosition() / STEPS_PER_MM_X,
            motor->getStepperY().currentPosition() / STEPS_PER_MM_Y,
            currentState);
        lastStatusTime = millis();
    }

    motor->update();
    claw->update();

    switch (currentState) {
    // ────────────────────────────────────────
    // 1. IDLE — 캠 OFF, 파란=캠ON / 빨간=가이드모달
    // ────────────────────────────────────────
    case IDLE:
        // IDLE 진입 후 3초간 버튼 무시 (디바운스 및 오작동 방지)
        if (millis() - idleEnteredTime >= 3000 && input->isBtnMainPressed()) {
            // 파랑 → READY (캠 ON, GameCountModal 표시 시점)
            roundsPlayed = 0;
            currentState = READY;
        } else if (millis() - idleEnteredTime >= 3000 && input->isBtnSubPressed()) {
            // 빨강 → 메인 페이지의 가이드 모달
            comm->sendEvent("GUIDE");
        }
        break;

    // ────────────────────────────────────────
    // 2. READY — 캠 ON, GameCountModal 인터랙션
    // ────────────────────────────────────────
    case READY: {
        if (input->isBtnMainPressed()) {
            // 파랑 → 모달 "시작" → PLAYING 진입
            enterPlaying();
            break;
        }
        // 빨강 버튼은 READY 에서 홈 이동 트리거로 사용하지 않는다.
        // (오입력으로 홈 화면으로 빠지는 문제 방지)
        input->isBtnSubPressed();
        // 조이스틱 X edge → 모달 옵션 순환 이벤트
        int xDir = input->getJoystickX();
        if (xDir != 0 && prevJoyX == 0) {
            comm->sendEvent(xDir > 0 ? "JOY_RIGHT" : "JOY_LEFT");
        }
        prevJoyX = xDir;
        // Y 는 옵션 순환에 사용 안 함. edge 만 추적 (혹시 모를 충돌 방지).
        prevJoyY = input->getJoystickY();
        break;
    }

    // ────────────────────────────────────────
    // 3. PLAYING — 조이스틱 첫 입력 시 타이머 시작, 그 후 자유 이동
    //              빨강 또는 타이머 만료 → 집기 시퀀스
    // ────────────────────────────────────────
    case PLAYING: {
        if (!motor->isReady()) break;

        // safety: 60초간 조이스틱 무동작 → 사용자 이탈, IDLE 진입
        if (playStartTime == 0 &&
            (millis() - playingEnteredTime) >= PLAYING_IDLE_TIMEOUT_MS) {
            comm->sendEvent("PLAYING_IDLE_TIMEOUT");
            currentState = IDLE;
            idleEnteredTime = millis();
            break;
        }

        // 조이스틱 입력 처리
        int xDir = input->getJoystickX();
        int yDir = input->getJoystickY();
        bool joyMoved = (xDir != 0 || yDir != 0);

        // 첫 입력 시점 캐치 → 타이머 시작 + ROUND_TIMER_START 이벤트
        if (playStartTime == 0 && joyMoved) {
            playStartTime = millis();
            comm->sendEvent("ROUND_TIMER_START");
        }

        handleManualInput();

        if (input->isBtnSubPressed() || isPlayingTimeout()) {
            comm->sendEvent("GRAB_START");
            startGrabSequence();
        }
        break;
    }

    // ────────────────────────────────────────
    // 4. GRAB_DOWN → GRAB_CLOSE → GRAB_UP : 집기 시퀀스
    // ────────────────────────────────────────
    case GRAB_DOWN:
        if (motorAuto->isZReachedTarget()) {
            claw->close();
            claw->wait(2000);   // 2초 동안 잡은 채로 유지
            currentState = GRAB_CLOSE;
        }
        break;

    case GRAB_CLOSE:
        if (claw->isWaitFinished()) {
            motorAuto->moveZ(Z_MOVE_STEPS_UP);
            currentState = GRAB_UP;
        }
        break;

    case GRAB_UP:
        if (motorAuto->isZReachedTarget()) {
            // 배출구로 이동 (endstop chatter 회피 위해 정확히 0 이 아닌 1mm 안쪽).
            motorAuto->setTarget(DROP_OFF_X_MM, DROP_OFF_Y_MM);
            currentState = RETURN_MOVE;
        }
        break;

    // ────────────────────────────────────────
    // 5. RETURN_MOVE → RETURN_DOWN → RETURN_OPEN → RETURN_UP : 배출구에서 인형 놓기
    // ────────────────────────────────────────
    case RETURN_MOVE:
        if (motorAuto->isReachedTarget()) {
            motorAuto->moveZ(-Z_CLAW_UP_STEPS);
            currentState = RETURN_DOWN;
        }
        break;

    case RETURN_DOWN:
        if (motorAuto->isZReachedTarget()) {
            claw->open();
            claw->wait(2000);
            currentState = RETURN_OPEN;
        }
        break;

    case RETURN_OPEN:
        if (claw->isWaitFinished()) {
            motorAuto->moveZ(Z_CLAW_UP_STEPS);
            currentState = RETURN_UP;
        }
        break;

    case RETURN_UP:
        if (motorAuto->isZReachedTarget()) {
            roundsPlayed += 1;
            postGameEnteredTime = millis();
            currentState = POST_GAME;
        }
        break;

    // ────────────────────────────────────────
    // 6. POST_GAME — 결과 표시 + 5초 후 자동 PLAYING (중간 종료 불가)
    // ────────────────────────────────────────
    case POST_GAME:
        if ((millis() - postGameEnteredTime) >= POST_GAME_TO_PLAYING_MS) {
            if (roundsPlayed >= MAX_ROUNDS_PER_SESSION) {
                // 세션 최대 판수 도달 시 즉시 종료. 이후 조이스틱은 READY/PLAYING에 진입하기 전까지 무효.
                currentState = IDLE;
                idleEnteredTime = millis();
            } else {
                enterPlaying();
            }
        }
        // 빨강/파랑 무동작 (Frontend 가 maxGames 도달 시 QR 화면, Arduino safety 는 PLAYING_IDLE_TIMEOUT 으로).
        break;
    }
}

void StateMachine::handleManualInput() {
    int xDir = input->getJoystickX();
    int yDir = input->getJoystickY();

    if (xDir != 0 || yDir != 0) {
        motorManual->setDirectionX(xDir);
        motorManual->setDirectionY(yDir);
    } else {
        motorManual->setDirectionX(0);
        motorManual->setDirectionY(0);
        // setDirectionX(0) 내부에서 stop + setManualMode(false) 호출됨.
        // 여기서 추가로 호출하지 않아 자동 모드 target 이 보존되도록 한다.
    }
}
