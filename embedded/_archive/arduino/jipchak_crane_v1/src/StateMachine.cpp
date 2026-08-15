#include "StateMachine.h"
#include "../config.h"

StateMachine::StateMachine(
    CommManager* c, MotorManager* m, MotorAuto* ma,
    MotorManual* mm, ClawManager* cl, InputManager* in)
    : comm(c), motor(m), motorAuto(ma), motorManual(mm),
      claw(cl), input(in), currentState(IDLE), lastStatusTime(0), subState(0) {}

void StateMachine::init() {
    motor->init();
    claw->init();
    input->init();
}

void StateMachine::update() {
    if (millis() - lastStatusTime >= 100) {
        comm->sendStatus(
            motor->getStepperX().currentPosition() / STEPS_PER_MM_X,
            motor->getStepperY().currentPosition() / STEPS_PER_MM_Y,
            currentState);
        lastStatusTime = millis();
    }

    motor->update();
    claw->update();

    CommandType cmd = comm->receiveCommand();

    switch (currentState) {
    case IDLE:
        if (!motor->isReady()) break;

        handleManualInput();

        if (cmd == CMD_CATCH) {
            motorAuto->setTarget(comm->getTargetX(), comm->getTargetY());
            currentState = AUTO_SEQ_MOVE;
            subState = 0;
        } else if (input->isBtnMainPressed()) {
            claw->open();
            claw->wait(500);
            currentState = SEQ_OPEN;
            subState = 0;
        } else if (input->isBtnSubPressed()) {
            claw->open();
            // 서브 버튼(A5)은 출구에서 인형을 놓기 위해 벌리는 용도입니다.
            // 놓은 후에는 다음 게임을 위해 계속 벌어진 상태(IDLE)를 유지합니다.
        }
        break;

    case AUTO_SEQ_MOVE:
        if (motorAuto->isReachedTarget()) {
            claw->open();
            claw->wait(500);
            currentState = AUTO_SEQ_OPEN;
        }
        break;

    case AUTO_SEQ_OPEN:
    case SEQ_OPEN:
        if (claw->isWaitFinished()) {
            motorAuto->moveZ(-Z_MOVE_STEPS_DOWN);
            currentState = (currentState == AUTO_SEQ_OPEN) ? AUTO_SEQ_DOWN : SEQ_DOWN;
        }
        break;

    case AUTO_SEQ_DOWN:
    case SEQ_DOWN:
        if (motorAuto->isZReachedTarget()) {
            claw->wait(500);
            currentState = (currentState == AUTO_SEQ_DOWN) ? AUTO_SEQ_GRAB : SEQ_GRAB;
            subState = 0;
        }
        break;

    case AUTO_SEQ_GRAB:
    case SEQ_GRAB:
        if (claw->isWaitFinished() && subState == 0) {
            claw->close();
            claw->wait(1000);
            subState = 1;
        } else if (claw->isWaitFinished() && subState == 1) {
            motorAuto->moveZ(Z_MOVE_STEPS_UP);
            currentState = (currentState == AUTO_SEQ_GRAB) ? AUTO_SEQ_UP : SEQ_UP;
            subState = 0;
        }
        break;

    case AUTO_SEQ_UP:
    case SEQ_UP:
        if (motorAuto->isZReachedTarget()) {
            if (currentState == AUTO_SEQ_UP) {
                motorAuto->setTarget(0.0f, 0.0f);
                currentState = AUTO_SEQ_RETURN;
            } else {
                currentState = IDLE;
            }
        }
        break;

    case AUTO_SEQ_RETURN:
        if (motorAuto->isReachedTarget()) {
            claw->open();
            currentState = IDLE;
        }
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
        motor->setManualMode(false);
    }
}
