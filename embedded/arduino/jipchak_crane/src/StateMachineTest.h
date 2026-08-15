#pragma once
#include "Comm.h"
#include "motor/MotorManager.h"
#include "motor/MotorAuto.h"
#include "motor/MotorManual.h"
#include "Claw.h"
#include "Input.h"

class StateMachineTest {
private:
    MotorManager* motor;
    MotorAuto* motorAuto;
    ClawManager* claw;
    InputManager* input;

    int testState;

public:
    StateMachineTest(CommManager* c, MotorManager* m, MotorAuto* ma, MotorManual* mm, ClawManager* cl, InputManager* in);
    void init();
    void update(); 
};
