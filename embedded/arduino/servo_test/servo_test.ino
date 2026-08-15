#include <Servo.h>

Servo myServo;
const int PIN_SERVO = 13;

void setup() {
  Serial.begin(115200);

  myServo.write(90);
  myServo.attach(PIN_SERVO);

  Serial.println("=== Claw Angle Test (180 Degree Servo) ===");
  Serial.println("Waiting for manual input...");
  Serial.println("Enter an angle (0 ~ 180) to test your claw.");
  Serial.println("Example: Type '145' and press Enter to see the closed state.");
}

void loop() {
  if (Serial.available() > 0) {
    int angle = Serial.parseInt();

    if (angle >= 0 && angle <= 180) {
      Serial.print("Moving to Angle: ");
      Serial.println(angle);

      myServo.write(angle);
    } else if (angle != 0) {
      Serial.println("Please enter a valid angle (0~180).");
    }

    while(Serial.available() > 0) {
      char t = Serial.read();
    }
  }
}
