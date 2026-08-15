#include "Input.h"
#include "../config.h"

void InputManager::init() {
    pinMode(PIN_JOY_Y_UP,    INPUT_PULLUP);
    pinMode(PIN_JOY_Y_DOWN,  INPUT_PULLUP);
    pinMode(PIN_JOY_X_LEFT,  INPUT_PULLUP);
    pinMode(PIN_JOY_X_RIGHT, INPUT_PULLUP);

    pinMode(PIN_BTN_MAIN, INPUT_PULLUP);
    pinMode(PIN_BTN_SUB,  INPUT_PULLUP);

    prevBtnMain = HIGH;
    prevBtnSub = HIGH;
}

int InputManager::getJoystickX() {
    static int debouncedX = 0;
    static unsigned long lastChangeX = 0;
    int rawX = 0;
    if (digitalRead(PIN_JOY_X_LEFT) == LOW) rawX = -1;
    else if (digitalRead(PIN_JOY_X_RIGHT) == LOW) rawX = 1;
    
    if (rawX != debouncedX) {
        if (millis() - lastChangeX > 50) {
            debouncedX = rawX;
            lastChangeX = millis();
            if (debouncedX == -1) Serial.println("JOY X LEFT");
            else if (debouncedX == 1) Serial.println("JOY X RIGHT");
        }
    }
    return debouncedX;
}

int InputManager::getJoystickY() {
    static int debouncedY = 0;
    static unsigned long lastChangeY = 0;
    int rawY = 0;
    if (digitalRead(PIN_JOY_Y_DOWN) == LOW) rawY = -1;
    else if (digitalRead(PIN_JOY_Y_UP) == LOW) rawY = 1;

    if (rawY != debouncedY) {
        if (millis() - lastChangeY > 50) {
            debouncedY = rawY;
            lastChangeY = millis();
            if (debouncedY == -1) Serial.println("JOY Y DOWN");
            else if (debouncedY == 1) Serial.println("JOY Y UP");
        }
    }
    return debouncedY;
}

bool InputManager::isBtnMainPressed() {
    static unsigned long lastChangeMain = 0;
    bool current = digitalRead(PIN_BTN_MAIN);
    bool pressed = false;
    
    if (current != prevBtnMain) {
        if (millis() - lastChangeMain > 50) {
            prevBtnMain = current;
            lastChangeMain = millis();
            if (current == LOW) {
                pressed = true;
                Serial.println("BTN MAIN PRESSED");
            }
        }
    }
    return pressed;
}

bool InputManager::isBtnSubPressed() {
    static unsigned long lastChangeSub = 0;
    bool current = digitalRead(PIN_BTN_SUB);
    bool pressed = false;
    
    if (current != prevBtnSub) {
        if (millis() - lastChangeSub > 50) {
            prevBtnSub = current;
            lastChangeSub = millis();
            if (current == LOW) {
                pressed = true;
                Serial.println("BTN SUB PRESSED");
            }
        }
    }
    return pressed;
}
