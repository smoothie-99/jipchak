#include "MotorManual.h"

MotorManual::MotorManual(MotorManager& manager) : _manager(manager) {}

void MotorManual::setDirectionX(int dir) {
    static int prevDirX = 0;
    if (dir != prevDirX) {
        if (dir > 0) {
            Serial.println("MOTOR X RIGHT (Manual)");
            _manager.getStepperX().move(1000000);
        } else if (dir < 0) {
            Serial.println("MOTOR X LEFT (Manual)");
            _manager.getStepperX().move(-1000000);
        } else {
            Serial.println("MOTOR X STOP (Manual)");
            _manager.getStepperX().stop();
        }
        prevDirX = dir;
    }
    if (dir != 0) _manager.setManualMode(true);
}

void MotorManual::setDirectionY(int dir) {
    static int prevDirY = 0;
    if (dir != prevDirY) {
        if (dir > 0) {
            Serial.println("MOTOR Y UP (Manual)");
            _manager.getStepperY().move(1000000);
        } else if (dir < 0) {
            Serial.println("MOTOR Y DOWN (Manual)");
            _manager.getStepperY().move(-1000000);
        } else {
            Serial.println("MOTOR Y STOP (Manual)");
            _manager.getStepperY().stop();
        }
        prevDirY = dir;
    }
    if (dir != 0) _manager.setManualMode(true);
}
