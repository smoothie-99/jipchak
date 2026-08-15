#include "Claw.h"
#include "../config.h"

void ClawManager::init() {
    servo.write(CLAW_ANGLE_IDLE); // 0도로 미리 타겟을 세팅하여 튀는 현상 방지
    servo.attach(PIN_SERVO);
    setIdle();
    isWaiting = false;
}

void ClawManager::update() {
    if (isWaiting && millis() - actionStartTime >= waitDuration) {
        isWaiting = false;
    }
}

void ClawManager::open() {
    Serial.println("SERVO CLAW OPEN");
    servo.write(CLAW_ANGLE_OPEN);
}

void ClawManager::close() {
    Serial.println("SERVO CLAW CLOSE");
    servo.write(CLAW_ANGLE_CLOSE);
}

void ClawManager::setIdle() {
    Serial.println("SERVO CLAW IDLE");
    servo.write(CLAW_ANGLE_IDLE);
}

void ClawManager::wait(unsigned long ms) {
    actionStartTime = millis();
    waitDuration = ms;
    isWaiting = true;
}

bool ClawManager::isWaitFinished() const {
    return !isWaiting;
}
