#pragma once

#include "Comm.h"
#include "Claw.h"
#include "Input.h"
#include "motor/MotorManager.h"
#include "motor/MotorAuto.h"
#include "motor/MotorManual.h"

/**
 * SystemState — 게임 한 판의 흐름 단계.
 *
 * 사용자 시나리오:
 *   IDLE         사이트 진입 / 세션 종료 → 캠 OFF
 *   READY        빨간(1) → 캠 ON, 게임 시작 대기
 *   PLAYING      빨간(2) → 게임 진행. 조이스틱 자유 이동 + 15 초 타이머
 *   GRAB_DOWN    파란 또는 타이머 만료 → Z 축 하강
 *   GRAB_CLOSE   집게 닫기 (인형 잡기 시도)
 *   GRAB_UP      Z 축 상승
 *   RETURN_MOVE  배출구(0, 0) 로 X/Y 이동
 *   RETURN_DOWN  배출구 위치에서 Z 축 하강
 *   RETURN_OPEN  집게 벌리기 (인형 놓기)
 *   RETURN_UP    Z 축 상승
 *   POST_GAME    한 판 종료. 빨간=다음 판, 파란=세션 종료
 *
 * RPi (rpi_full.py) 가 sendStatus 의 st 값으로 이 enum 을 추적하여
 * SESSION_START / GAME_RESULT / 카메라 lifecycle 을 트리거한다.
 *
 * AUTO_SEQ_* (AI 자동 잡기) 는 별도 작업 (`_archive/arduino/jipchak_crane_v1/`) 으로 분리.
 */
enum SystemState {
    IDLE        = 1,
    READY       = 2,
    PLAYING     = 3,
    GRAB_DOWN   = 4,
    GRAB_CLOSE  = 5,
    GRAB_UP     = 6,
    RETURN_MOVE = 7,
    RETURN_DOWN = 8,
    RETURN_OPEN = 9,
    RETURN_UP   = 10,
    POST_GAME   = 11,
};

class StateMachine {
public:
    StateMachine(
        CommManager* c,
        MotorManager* m,
        MotorAuto* ma,
        MotorManual* mm,
        ClawManager* cl,
        InputManager* in);

    void init();
    void update();

private:
    CommManager* comm;
    MotorManager* motor;
    MotorAuto* motorAuto;
    MotorManual* motorManual;
    ClawManager* claw;
    InputManager* input;

    SystemState currentState;
    unsigned long lastStatusTime;     // sendStatus 100ms 주기 트래커
    unsigned long playStartTime;      // 조이스틱 첫 입력 시각 (PLAY_TIMEOUT_MS 타이머용). 0 이면 아직 미입력
    unsigned long playingEnteredTime; // PLAYING 진입 시각 (PLAYING_IDLE_TIMEOUT_MS safety 용)
    unsigned long postGameEnteredTime;// POST_GAME 진입 시각 (POST_GAME_TO_PLAYING_MS 자동 진입 용)
    unsigned long idleEnteredTime;    // IDLE 진입 시각 (재진입 쿨다운 용)
    int roundsPlayed;                 // 현재 START 세션에서 완료된 판 수
    int subState;                     // 일부 상태에서 단계 진행 캐치용

    // 조이스틱 edge detection (READY 의 모달 옵션 순환 / PLAYING 첫 입력 트리거 용)
    int prevJoyX;
    int prevJoyY;

    void handleManualInput();
    bool isPlayingTimeout() const;
    void startGrabSequence();         // PLAYING → GRAB_DOWN 진입 시 공통 처리
    void enterPlaying();              // READY / POST_GAME → PLAYING 진입 시 공통 reset
};
