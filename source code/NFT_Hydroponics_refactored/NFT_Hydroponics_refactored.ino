#include "HydroponicsController.h"

// Construction performs no I/O. Hardware setup remains in begin(), matching
// Arduino's setup()/loop() lifecycle.
HydroponicsController controller;

void setup() {
  controller.begin();
}

void loop() {
  controller.update();
}
