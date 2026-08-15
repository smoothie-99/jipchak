#pragma once
#include "MotorManager.h"

class MotorAuto {
public:
    explicit MotorAuto(MotorManager& manager);

    void setTarget(float xMm, float yMm);
    void moveZ(int steps);
    
    bool isReachedTarget() const;
    bool isZReachedTarget() const;

private:
    MotorManager& _manager;
};
