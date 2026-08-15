#include "Comm.h"
#include <ArduinoJson.h>
#include "../config.h"

void CommManager::init() {
    Serial.begin(BAUD_RATE);
    Serial.setTimeout(10);
}

void CommManager::sendStatus(float currentX, float currentY, int currentState) {
    // 송신 형식: {"t":"s","x":<float>,"y":<float>,"st":<int>}
    // RPi (rpi_full.py / streamer.py) 가 이 메시지의 st 전이로 게임 START/STOP 을 감지하고
    // AI 서버의 영상 녹화 세션을 트리거한다. 비활성화하면 자동 녹화 흐름이 끊긴다.
    StaticJsonDocument<128> doc;
    doc["t"] = "s";
    doc["x"] = currentX;
    doc["y"] = currentY;
    doc["st"] = currentState;

    serializeJson(doc, Serial);
    Serial.println();
}

void CommManager::sendEvent(const char* name) {
    // 송신 형식: {"t":"e","e":"<name>"}
    // 예: IDLE 상태에서 빨강 버튼 누르면 sendEvent("GUIDE") → 브라우저 가이드 모달 호출.
    StaticJsonDocument<64> doc;
    doc["t"] = "e";
    doc["e"] = name;
    serializeJson(doc, Serial);
    Serial.println();
}

CommandType CommManager::receiveCommand() {
    if (Serial.available() > 0) {
        String jsonString = Serial.readStringUntil('\n');
        jsonString.trim();

        StaticJsonDocument<128> doc;
        DeserializationError error = deserializeJson(doc, jsonString);

        if (error) return CMD_NONE;

        const char* type = doc["t"];
        if (type != nullptr && strcmp(type, "c") == 0) {
            targetX = doc["x"];
            targetY = doc["y"];
            return CMD_CATCH;
        }
    }
    return CMD_NONE;
}

float CommManager::getTargetX() const { return targetX; }
float CommManager::getTargetY() const { return targetY; }
