#pragma once
#include <Arduino.h>
#include <Servo.h>

class ClawManager {
private:
    Servo servo;
    unsigned long actionStartTime;
    unsigned long waitDuration;
    bool isWaiting;

public:
    void init();
    void update(); // millis 기반 비동기 처리용 (필요시)
    
    void open();
    void close();
    void setIdle();

    void wait(unsigned long ms);
    bool isWaitFinished() const;
};
