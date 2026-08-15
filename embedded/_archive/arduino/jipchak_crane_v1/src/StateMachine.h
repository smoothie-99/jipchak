#pragma once
#include "Comm.h"
#include "motor/MotorManager.h"
#include "motor/MotorAuto.h"
#include "motor/MotorManual.h"
#include "Claw.h"
#include "Input.h"

enum SystemState {
    IDLE = 1,
    AUTO_SEQ_MOVE,
    AUTO_SEQ_OPEN,
    AUTO_SEQ_DOWN,
    AUTO_SEQ_GRAB,
    AUTO_SEQ_UP,
    AUTO_SEQ_RETURN,
    SEQ_OPEN,
    SEQ_DOWN,
    SEQ_GRAB,
    SEQ_UP,
    SEQ_RETURN
};

class StateMachine {
private:
    SystemState currentState;
    CommManager* comm;
    MotorManager* motor;
    MotorAuto* motorAuto;
    MotorManual* motorManual;
    ClawManager* claw;
    InputManager* input;

    unsigned long lastStatusTime;
    int subState;

public:
    StateMachine(CommManager* c, MotorManager* m, MotorAuto* ma, MotorManual* mm, ClawManager* cl, InputManager* in);
    void init();
    void update(); 
    
private:
    void handleManualInput();
    void handleCatchSequence(bool isAuto);
};
