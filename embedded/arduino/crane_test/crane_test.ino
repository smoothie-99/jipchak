#include <AccelStepper.h>
#include <Servo.h>

// --- Pins ---
const int PIN_BTN_MAIN = A4;
const int PIN_BTN_SUB  = A5;
const int PIN_STEP_Z = 4;
const int PIN_DIR_Z = 7;
const int PIN_ENABLE = 8;
const int PIN_SERVO = 13;

// --- Config ---
const int CLAW_ANGLE_OPEN  = 90;
const int CLAW_ANGLE_CLOSE = 0;
const int Z_MOVE_STEPS_DOWN = 640;
const int Z_MOVE_STEPS_UP = 670;
const float MAX_SPEED_Z = 300.0;
const float ACCELERATION_Z = 50000.0;

AccelStepper stepperZ(AccelStepper::DRIVER, PIN_STEP_Z, PIN_DIR_Z);
Servo clawServo;

bool isMovingZ = false;
int nextClawAction = -1;

void setup() {
    Serial.begin(115200);
    pinMode(PIN_BTN_MAIN, INPUT_PULLUP);
    pinMode(PIN_BTN_SUB, INPUT_PULLUP);

    pinMode(PIN_ENABLE, OUTPUT);
    digitalWrite(PIN_ENABLE, LOW);

    stepperZ.setMaxSpeed(MAX_SPEED_Z);
    stepperZ.setAcceleration(ACCELERATION_Z);
    stepperZ.setPinsInverted(true, false, false); // Z축 회전 방향 반전

    clawServo.write(CLAW_ANGLE_OPEN);
    clawServo.attach(PIN_SERVO);

    Serial.println("=== Manual Split Sequence Test ===");
    Serial.println("[A4]: Z축 하강 -> 도착하면 집게 열기(90도)");
    Serial.println("[A5]: 집게 닫기(0도) -> Z축 상승");
}

void loop() {
    stepperZ.run();

    if (!isMovingZ && stepperZ.distanceToGo() == 0) {

        if (nextClawAction == 1) {
            Serial.println("-> Z축 하강 완료.");
            nextClawAction = -1;
        }
        else if (nextClawAction == 0) {
            Serial.println("-> Z축 상승 완료.");
            nextClawAction = -1;
        }

        if (digitalRead(PIN_BTN_MAIN) == LOW) {
            if (digitalRead(PIN_BTN_MAIN) == LOW) {
                Serial.println("[A4 입력] 집게 확인/열기(90도) -> Z축 하강 시작...");
                clawServo.write(CLAW_ANGLE_OPEN);

                stepperZ.move(-Z_MOVE_STEPS_DOWN);
                isMovingZ = true;
                nextClawAction = 1;
                while(digitalRead(PIN_BTN_MAIN) == LOW);
            }
        }
        else if (digitalRead(PIN_BTN_SUB) == LOW) {
            delay(50);
            if (digitalRead(PIN_BTN_SUB) == LOW) {
                Serial.println("[A5 입력] 집게 닫기 (0도)");
                clawServo.write(CLAW_ANGLE_CLOSE);

                unsigned long waitStart = millis();
                while(millis() - waitStart < 1000) {
                    stepperZ.run();
                }

                Serial.println("-> Z축 상승 시작...");
                stepperZ.move(Z_MOVE_STEPS_UP);
                isMovingZ = true;
                nextClawAction = 0;
                while(digitalRead(PIN_BTN_SUB) == LOW);
            }
        }
    }

    if (isMovingZ && stepperZ.distanceToGo() == 0) {
        isMovingZ = false;
    }
}
