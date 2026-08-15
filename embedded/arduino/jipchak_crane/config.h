#pragma once

// --- UART Communication ---
const unsigned long BAUD_RATE = 115200;

// --- Joystick Pins ---
const int PIN_JOY_Y_DOWN  = A0;
const int PIN_JOY_X_LEFT  = A1;
const int PIN_JOY_Y_UP    = A2;
const int PIN_JOY_X_RIGHT = A3;

// --- Button Pins ---
// 역할 스왑: 파랑(A4) = 게임 시작 / 다음 판 (MAIN 의도), 빨강(A5) = 집게 내리기 / 세션 종료 (SUB 의도).
// 물리 배선 그대로, 코드의 의미만 바뀜.
const int PIN_BTN_MAIN = A4;
const int PIN_BTN_SUB  = A5;

// --- Stepper Motor Pins ---
const int PIN_STEP_X = 2;
const int PIN_DIR_X  = 5;

const int PIN_STEP_Y = 3;
const int PIN_DIR_Y  = 6;

const int PIN_STEP_Z = 4;
const int PIN_DIR_Z  = 7;

const int PIN_ENABLE = 8; // LOW to enable

// --- Limit Switch Pins ---
const int PIN_ENDSTOP_X_LEFT  = 9;
const int PIN_ENDSTOP_X_RIGHT = 10;
const int PIN_ENDSTOP_Y_UP    = 11;
const int PIN_ENDSTOP_Y_DOWN  = 12;

// --- Servo Motor Pins & Angles ---
const int PIN_SERVO = 13;

const int CLAW_ANGLE_OPEN  = 90;
const int CLAW_ANGLE_CLOSE = 0;
const int CLAW_ANGLE_IDLE  = 90;

// --- Stepper Motor Configuration ---
const float MAX_SPEED_X = 400.0;
const float ACCELERATION_X = 500.0;
const float MAX_SPEED_Y = 400.0;
const float ACCELERATION_Y = 500.0;
const float MAX_SPEED_Z = 300.0;
const float ACCELERATION_Z = 50000.0; // Z축 등속도를 위해 가속도 무한대 설정

// Z-axis movement steps
const int Z_MOVE_STEPS_DOWN = 670;
const int Z_MOVE_STEPS_UP = 670;

// 부팅 시 Z 를 위로 올리기 위한 stroke.
// 게임 한 판 stroke (670) 보다 약간 크게 잡아 자중으로 더 떨어진 케이스 흡수.
// 도달 못 해도 MOTOR_READY 에서 stepperZ.run() 계속 호출되어 끝까지 진행.
const int Z_HOMING_UP_STEPS = 680;

const int Z_CLAW_UP_STEPS = 500;

// --- Conversion & Homing Configuration ---
const float STEPS_PER_MM_X = 80.0f;
const float STEPS_PER_MM_Y = 80.0f;

// --- Homing Travel Steps Configuration ---
// 호밍 끝나면 (0,0) = X 왼쪽 끝 + Y 아래쪽 끝 = 배출구 (좌하단).
// 작업 영역 실측 전이라 안전 마진으로 크게 (-10000 step ≈ 125mm) 잡음.
// endstop 만나면 즉시 멈추니까 over-shoot 위험 없음.
const long HOMING_TRAVEL_STEPS_X = -10000;
const long HOMING_TRAVEL_STEPS_Y = -10000;

// --- Auto Target Safety Limits (mm) ---
// 호밍 후 (0,0) = 좌하단(배출구) → 작업영역은 X+, Y+ 방향으로 펼쳐짐.
// 실제 작업영역 측정 전까지 보수적 값으로 설정 (대각선 ~40mm 정도만 허용).
const float AUTO_TARGET_X_MIN_MM = -10.0f;
const float AUTO_TARGET_X_MAX_MM = 40.0f;
const float AUTO_TARGET_Y_MIN_MM = -10.0f;
const float AUTO_TARGET_Y_MAX_MM = 40.0f;

// --- Drop-off Position (mm) ---
// 인형 떨굼 좌표. endstop 에 직접 닿으면 chatter 가 checkLimit 트리거를
// 무한 반복시켜 모터가 멈추지 않는다. 1mm 정도 안쪽으로 잡아 endstop 회피.
const float DROP_OFF_X_MM = -1.0f;
const float DROP_OFF_Y_MM = -1.0f;

// --- Game Flow ---
// 조이스틱 첫 입력 후 사용자가 자유 조작 가능한 시간. 만료 시 자동 집기.
const unsigned long PLAY_TIMEOUT_MS = 20000UL;

// POST_GAME (결과 표시) 후 자동으로 다음 판 PLAYING 진입까지의 대기 시간.
const unsigned long POST_GAME_TO_PLAYING_MS = 500UL;

// START 이후 허용할 최대 판수. 기본 2판 고정.
const int MAX_ROUNDS_PER_SESSION = 2;

// PLAYING 진입 후 조이스틱 무동작 safety. 이 시간 안에 조이스틱 입력 없으면
// 사용자 이탈로 판단하고 IDLE 진입 (캠 OFF + 세션 종료).
const unsigned long PLAYING_IDLE_TIMEOUT_MS = 60000UL;
