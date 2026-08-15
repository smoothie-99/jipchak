#pragma once
#include "MotorManager.h"

class MotorManual {
public:
    explicit MotorManual(MotorManager& manager);

    void setDirectionX(int dir);
    void setDirectionY(int dir);

private:
    MotorManager& _manager;
};
