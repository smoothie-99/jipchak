#include "MotorAuto.h"
#include "../../config.h"
#include <math.h>

MotorAuto::MotorAuto(MotorManager& manager) : _manager(manager) {}

void MotorAuto::setTarget(float xMm, float yMm) {
    // 입력 검증: NaN / Inf 차단.
    // static_cast<long>(NaN) 은 정의되지 않은 동작이고, 결과적으로 모터 폭주 위험.
    if (isnan(xMm) || isnan(yMm) || isinf(xMm) || isinf(yMm)) {
        Serial.print("[SAFETY] setTarget rejected (NaN/Inf): X=");
        Serial.print(xMm);
        Serial.print(" Y=");
        Serial.println(yMm);
        return;
    }

    // 범위 검증: 작업 영역 밖이면 명령 거부.
    // AI 서버 버그 / 통신 오염으로 들어온 비정상 좌표가 리밋 스위치까지 직진하는 것을 막음.
    if (xMm < AUTO_TARGET_X_MIN_MM || xMm > AUTO_TARGET_X_MAX_MM ||
        yMm < AUTO_TARGET_Y_MIN_MM || yMm > AUTO_TARGET_Y_MAX_MM) {
        Serial.print("[SAFETY] setTarget rejected (out of range): X=");
        Serial.print(xMm);
        Serial.print(" Y=");
        Serial.println(yMm);
        return;
    }

    Serial.print("MOTOR AUTO TARGET X: ");
    Serial.print(xMm);
    Serial.print(" Y: ");
    Serial.println(yMm);
    _manager.getStepperX().moveTo(static_cast<long>(xMm * STEPS_PER_MM_X));
    _manager.getStepperY().moveTo(static_cast<long>(yMm * STEPS_PER_MM_Y));
}

void MotorAuto::moveZ(int steps) {
    Serial.print("MOTOR Z MOVE: ");
    Serial.println(steps);
    _manager.getStepperZ().move(steps);
}

bool MotorAuto::isReachedTarget() const {
    return _manager.getStepperX().distanceToGo() == 0 && _manager.getStepperY().distanceToGo() == 0;
}

bool MotorAuto::isZReachedTarget() const {
    return _manager.getStepperZ().distanceToGo() == 0;
}
