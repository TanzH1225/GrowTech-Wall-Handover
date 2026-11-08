#include <AccelStepper.h>

#include "GantryCommandProcessor.h"
#include "GantryConfig.h"
#include "GantryMotion.h"

// The motion constructor configures Arduino pins before setup(); the command
// processor separately owns logical grid, enabled state, and inactivity time.
GantryMotion gantryMotion;
GantryCommandProcessor gantryCommands(gantryMotion);

// Startup requests a full home without waiting for a Pi command. The matching
// Serial open/reset behavior and physical homing must be validated separately.
void setup() {
  Serial.begin(GantryConfig::SERIAL_BAUD);
  while (!Serial) {
  }

  delay(GantryConfig::STARTUP_DELAY_MS);

  Serial.println("INIT: Starting homing on startup...");
  gantryMotion.homeAllAxes();
  gantryMotion.setCurrentPositionsToZero();
  Serial.println("INIT: Homing complete. Ready.");
}

// Both calls are cooperative: blocking moves/homing prevent this loop from
// reading a new command. Timeout is checked before queued serial input.
void loop() {
  gantryCommands.checkTimeoutAndDisable();
  gantryCommands.processSerialCommand();
}
