#include <AccelStepper.h>

// --- Joystick & Button Pins ---
const int PIN_JOY_Y_DOWN  = A0;
const int PIN_JOY_X_LEFT  = A1;
const int PIN_JOY_Y_UP    = A2;
const int PIN_JOY_X_RIGHT = A3;
const int PIN_BTN_MAIN    = A4;
const int PIN_BTN_SUB     = A5;

// --- Stepper Pins ---
const int PIN_STEP_X = 2; const int PIN_DIR_X = 5;
const int PIN_STEP_Y = 3; const int PIN_DIR_Y = 6;
const int PIN_STEP_Z = 4; const int PIN_DIR_Z = 7;
const int PIN_ENABLE = 8;

// --- Limit Switch Pins ---
const int PIN_ENDSTOP_X_LEFT  = 9;
const int PIN_ENDSTOP_X_RIGHT = 10;
const int PIN_ENDSTOP_Y_UP    = 11;
const int PIN_ENDSTOP_Y_DOWN  = 12;

AccelStepper stepperX(AccelStepper::DRIVER, PIN_STEP_X, PIN_DIR_X);
AccelStepper stepperY(AccelStepper::DRIVER, PIN_STEP_Y, PIN_DIR_Y);
AccelStepper stepperZ(AccelStepper::DRIVER, PIN_STEP_Z, PIN_DIR_Z);

long prevPosX = 0, prevPosY = 0, prevPosZ = 0;

void setup() {
  Serial.begin(115200);

  pinMode(PIN_JOY_Y_UP, INPUT_PULLUP);
  pinMode(PIN_JOY_Y_DOWN, INPUT_PULLUP);
  pinMode(PIN_JOY_X_LEFT, INPUT_PULLUP);
  pinMode(PIN_JOY_X_RIGHT, INPUT_PULLUP);
  pinMode(PIN_BTN_MAIN, INPUT_PULLUP);
  pinMode(PIN_BTN_SUB, INPUT_PULLUP);

  pinMode(PIN_ENDSTOP_X_LEFT, INPUT_PULLUP);
  pinMode(PIN_ENDSTOP_X_RIGHT, INPUT_PULLUP);
  pinMode(PIN_ENDSTOP_Y_UP, INPUT_PULLUP);
  pinMode(PIN_ENDSTOP_Y_DOWN, INPUT_PULLUP);

  pinMode(PIN_ENABLE, OUTPUT);
  digitalWrite(PIN_ENABLE, LOW);

  stepperX.setMaxSpeed(400); stepperX.setAcceleration(500);
  stepperY.setMaxSpeed(400); stepperY.setAcceleration(500);
  stepperZ.setMaxSpeed(300); stepperZ.setAcceleration(2000);

  Serial.println("=== Stepper Calibration Tool ===");
  Serial.println("1. Manual Jog (수동 조작):");
  Serial.println("   - Joystick: Move X, Y axis");
  Serial.println("   - Main Button(A4): Z Down, Sub Button(A5): Z Up");
  Serial.println("2. Serial Commands (시리얼 명령어):");
  Serial.println("   - 'X1000' -> X축 1000스텝 이동");
  Serial.println("   - 'Y-500' -> Y축 -500스텝 이동");
  Serial.println("   - 'Z650'  -> Z축 650스텝 이동");
  Serial.println("================================");
}

void loop() {
  static int lastDirX = 0, lastDirY = 0;
  int dirX = 0, dirY = 0;
  float speedZ = 0;

  if (digitalRead(PIN_JOY_X_LEFT) == LOW) dirX = -1;
  else if (digitalRead(PIN_JOY_X_RIGHT) == LOW) dirX = 1;

  if (digitalRead(PIN_JOY_Y_DOWN) == LOW) dirY = -1;
  else if (digitalRead(PIN_JOY_Y_UP) == LOW) dirY = 1;

  if (digitalRead(PIN_BTN_MAIN) == LOW) speedZ = 300;
  else if (digitalRead(PIN_BTN_SUB) == LOW) speedZ = -300;

  if (dirX != lastDirX) {
    if (dirX == -1) stepperX.move(-1000000);
    else if (dirX == 1) stepperX.move(1000000);
    else stepperX.stop();
    lastDirX = dirX;
  }

  if (digitalRead(PIN_ENDSTOP_X_LEFT) == LOW && stepperX.distanceToGo() < 0) {
    stepperX.setCurrentPosition(0);
    stepperX.moveTo(5);
    Serial.println("X LEFT LIMIT TRIGGERED! Origin Reset to 0. Bouncing back...");
  }
  if (digitalRead(PIN_ENDSTOP_X_RIGHT) == LOW && stepperX.distanceToGo() > 0) {
    long curX = stepperX.currentPosition();
    stepperX.setCurrentPosition(curX);
    stepperX.moveTo(curX - 5);
    Serial.println("X RIGHT LIMIT TRIGGERED! Bouncing back...");
  }
  stepperX.run();

  if (dirY != lastDirY) {
    if (dirY == -1) stepperY.move(-1000000);
    else if (dirY == 1) stepperY.move(1000000);
    else stepperY.stop();
    lastDirY = dirY;
  }

  if (digitalRead(PIN_ENDSTOP_Y_DOWN) == LOW && stepperY.distanceToGo() < 0) {
    stepperY.setCurrentPosition(0);
    stepperY.moveTo(5);
    Serial.println("Y DOWN LIMIT TRIGGERED! Origin Reset to 0. Bouncing back...");
  }
  if (digitalRead(PIN_ENDSTOP_Y_UP) == LOW && stepperY.distanceToGo() > 0) {
    long curY = stepperY.currentPosition();
    stepperY.setCurrentPosition(curY);
    stepperY.moveTo(curY - 5);
    Serial.println("Y UP LIMIT TRIGGERED! Bouncing back...");
  }
  stepperY.run();

  static bool wasJoggingZ = false;
  if (speedZ != 0) {
    stepperZ.setSpeed(speedZ);
    stepperZ.runSpeed();
    wasJoggingZ = true;
  } else {
    if (wasJoggingZ) {
      stepperZ.setSpeed(0);
      stepperZ.moveTo(stepperZ.currentPosition());
      wasJoggingZ = false;
    }
    stepperZ.run();
  }

  if (dirX == 0 && stepperX.distanceToGo() == 0 && prevPosX != stepperX.currentPosition()) {
    Serial.print("[X] Current Position: "); Serial.println(stepperX.currentPosition());
    prevPosX = stepperX.currentPosition();
  }
  if (dirY == 0 && stepperY.distanceToGo() == 0 && prevPosY != stepperY.currentPosition()) {
    Serial.print("[Y] Current Position: "); Serial.println(stepperY.currentPosition());
    prevPosY = stepperY.currentPosition();
  }
  if (speedZ == 0 && stepperZ.distanceToGo() == 0 && prevPosZ != stepperZ.currentPosition()) {
    Serial.print("[Z] Current Position: "); Serial.println(stepperZ.currentPosition());
    prevPosZ = stepperZ.currentPosition();
  }

  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      char axis = input.charAt(0);
      long steps = input.substring(1).toInt();

      if (axis == 'X' || axis == 'x') {
        stepperX.move(steps);
        Serial.print("Command: Move X by "); Serial.println(steps);
      } else if (axis == 'Y' || axis == 'y') {
        stepperY.move(steps);
        Serial.print("Command: Move Y by "); Serial.println(steps);
      } else if (axis == 'Z' || axis == 'z') {
        stepperZ.move(steps);
        Serial.print("Command: Move Z by "); Serial.println(steps);
      }
    }
  }
}
