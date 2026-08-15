#include "config.h"
#include "src/Comm.h"
#include "src/motor/MotorManager.h"
#include "src/motor/MotorAuto.h"
#include "src/motor/MotorManual.h"
#include "src/Claw.h"
#include "src/Input.h"
#include "src/StateMachine.h"

// Create global objects
CommManager comm;
MotorManager motor;
MotorAuto motorAuto(motor);
MotorManual motorManual(motor);
ClawManager claw;
InputManager input;

// Create StateMachine object
StateMachine fsm(&comm, &motor, &motorAuto, &motorManual, &claw, &input);

// Initialize communication
// Initialize all hardware modules inside the state machine
void setup() {
    comm.init();
    fsm.init();
}

// Encapsulate all logic inside the StateMachine and individual objects
void loop() {
    fsm.update();
}
