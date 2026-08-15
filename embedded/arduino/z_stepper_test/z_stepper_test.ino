#include <AccelStepper.h>

const int PIN_STEP_Z = 4;
const int PIN_DIR_Z = 7;
const int PIN_ENABLE = 8;

const int PIN_BTN_UP = A4;
const int PIN_BTN_DOWN = A5;

AccelStepper stepperZ(AccelStepper::DRIVER, PIN_STEP_Z, PIN_DIR_Z);

long lastPosition = 0;
bool isMoving = false;

void setup() {
  Serial.begin(115200);

  pinMode(PIN_ENABLE, OUTPUT);
  digitalWrite(PIN_ENABLE, LOW);

  pinMode(PIN_BTN_UP, INPUT_PULLUP);
  pinMode(PIN_BTN_DOWN, INPUT_PULLUP);

  stepperZ.setMaxSpeed(300.0);
  stepperZ.setAcceleration(50000.0);
  stepperZ.setPinsInverted(true, false, false);

  Serial.println("=== Z-Axis Step Measurement Tool ===");
  Serial.println("[A4] 버튼: 누르고 있으면 상승 (UP)");
  Serial.println("[A5] 버튼: 누르고 있으면 하강 (DOWN)");
  Serial.println("버튼에서 손을 떼면 멈추고 이동한 스텝 수가 출력됩니다.");
  Serial.println("--------------------------------------------------");
}

void loop() {
  bool upPressed = (digitalRead(PIN_BTN_UP) == LOW);
  bool downPressed = (digitalRead(PIN_BTN_DOWN) == LOW);

  if (upPressed && !downPressed) {
    stepperZ.moveTo(1000000);
    isMoving = true;
  }
  else if (downPressed && !upPressed) {
    stepperZ.moveTo(-1000000);
    isMoving = true;
  }
  else {
    if (stepperZ.distanceToGo() != 0) {
      stepperZ.stop();
    }
  }

  stepperZ.run();

  if (isMoving && stepperZ.distanceToGo() == 0) {
    isMoving = false;
    long currentPos = stepperZ.currentPosition();
    long delta = currentPos - lastPosition;

    if (delta != 0) {
      Serial.print("방향: ");
      Serial.print(delta > 0 ? "상승(UP)  " : "하강(DOWN)");
      Serial.print(" | 이동 스텝: ");
      Serial.print(abs(delta));
      Serial.print(" steps | 현재 총 Z축 스텝: ");
      Serial.println(currentPos);

      lastPosition = currentPos;
    }
  }
}
