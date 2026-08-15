#pragma once
#include <Arduino.h>
#include <AccelStepper.h>

enum MotorState {
    MOTOR_HOMING_X,
    MOTOR_HOMING_Y,
    MOTOR_READY,
    MOTOR_MANUAL
};

enum class LimitAction { 
    STOP_ONLY, 
    STOP_AND_RESET_ORIGIN 
};

typedef void (*MotorCallback)();

class MotorManager {
private:
    AccelStepper stepperX;
    AccelStepper stepperY;
    AccelStepper stepperZ;

    MotorState currentState;
    MotorCallback _onReady;

    void checkLimit(AccelStepper& stepper, int pin, bool checkNegative, LimitAction action);

public:
    MotorManager();
    void init();
    
    void update();
    bool isReady() const;

    void onHomingComplete(MotorCallback cb) { _onReady = cb; }

    void setManualMode(bool isManual);

    // Getters for other modules
    AccelStepper& getStepperX() { return stepperX; }
    AccelStepper& getStepperY() { return stepperY; }
    AccelStepper& getStepperZ() { return stepperZ; }
};
