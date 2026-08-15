#include "StateMachineTest.h"
#include "../config.h"

StateMachineTest::StateMachineTest(CommManager* c, MotorManager* m, MotorAuto* ma, MotorManual* mm, ClawManager* cl, InputManager* in)
    : motor(m), motorAuto(ma), claw(cl), input(in), testState(0) {
}

void StateMachineTest::init() {
    input->init();
    motor->init();
    claw->init();
    testState = 0;
}

void StateMachineTest::update() {
    motor->update();
    claw->update();

    switch(testState) {
        case 0: // IDLE
            if (input->isBtnMainPressed()) { // A4 버튼
                Serial.println("[TEST] Main Button Pressed: Moving Z Down");
                motorAuto->moveZ(-Z_MOVE_STEPS_DOWN); // Z축 하강
                testState = 1;
            } else if (input->isBtnSubPressed()) { // A5 (오른쪽 서브버튼)
                Serial.println("[TEST] Sub Button Pressed: Closing Claw");
                claw->close(); // 그랩 닫기 (0도)
                claw->wait(1000); // 1초 대기
                testState = 3;
            }
            break;

        case 1: // Z Down moving
            if (motorAuto->isZReachedTarget()) {
                Serial.println("[TEST] Z Reached Bottom: Opening Claw");
                claw->open(); // 그랩 열기 (135도)
                claw->wait(1000); // 1초 대기
                testState = 2;
            }
            break;

        case 2: // Opened and waiting
            if (claw->isWaitFinished()) {
                Serial.println("[TEST] Claw Opened. Returning to IDLE.");
                testState = 0;
            }
            break;

        case 3: // Closing claw wait
            if (claw->isWaitFinished()) {
                Serial.println("[TEST] Claw Closed: Moving Z Up");
                motorAuto->moveZ(Z_MOVE_STEPS_UP); // Z축 상승
                testState = 4;
            }
            break;

        case 4: // Z Up moving
            if (motorAuto->isZReachedTarget()) {
                Serial.println("[TEST] Z Reached Top: Sequence Complete. Returning to IDLE.");
                testState = 0;
            }
            break;
    }
}
