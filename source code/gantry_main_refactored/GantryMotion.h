#ifndef GANTRY_MOTION_H
#define GANTRY_MOTION_H

#include <AccelStepper.h>

#ifndef MOTOR_INTERFACE_TYPE
#define MOTOR_INTERFACE_TYPE AccelStepper::DRIVER
#endif

class GantryMotion {
 public:
  GantryMotion();

  void enableMotors();
  void disableMotors();

  void bumpHomeX();
  void bumpHomeDualY();
  void homeAllAxes();
  void setCurrentPositionsToZero();

  // Caller must provide col 1..6 and row 1..4 before array indexing. These
  // methods block until step-counter targets finish and do not parse Serial.
  void goToGridPosition(int col, int row);
  void moveXRelativeSteps(int steps, float intervalMm, bool rightDirection);
  void moveYBy(float deltaMm);

 private:
  AccelStepper stepperX_;
  AccelStepper stepperY1_;
  AccelStepper stepperY2_;

  // Stop scheduling steps, disable every active-low driver-enable output, then
  // remain halted so a homing fault cannot silently continue operation.
  void errorStop(const char* axisName);
};

#endif  // GANTRY_MOTION_H
