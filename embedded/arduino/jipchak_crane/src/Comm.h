#pragma once
#include <Arduino.h>

enum CommandType {
    CMD_NONE = 0,
    CMD_CATCH = 1
};

class CommManager {
private:
    float targetX;
    float targetY;

public:
    void init();
    void sendStatus(float currentX, float currentY, int currentState);
    /**
     * 일회성 이벤트 송신. 예: 메인 페이지에서 빨강 버튼 누르면 GUIDE 모달 호출.
     * 형식: {"t":"e","e":"<name>"}
     * RPi (rpi_full.py) 가 받아서 WS 로 forward → 브라우저 streamStore 가 처리.
     */
    void sendEvent(const char* name);
    CommandType receiveCommand();
    float getTargetX() const;
    float getTargetY() const;
};
