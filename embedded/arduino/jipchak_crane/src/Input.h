#pragma once
#include <Arduino.h>

class InputManager {
private:
    bool prevBtnMain;
    bool prevBtnSub;

public:
    void init();
    int getJoystickX();
    int getJoystickY();
    bool isBtnMainPressed();
    bool isBtnSubPressed();
};
