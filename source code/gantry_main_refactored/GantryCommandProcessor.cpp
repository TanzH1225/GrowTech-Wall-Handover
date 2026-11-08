#include "GantryCommandProcessor.h"

#include "GantryConfig.h"

GantryCommandProcessor::GantryCommandProcessor(GantryMotion& motion)
    : motion_(motion),
      currentCol_(0),
      currentRow_(0),
      lastCommandTime_(millis()),
      motorsEnabled_(true) {}

void GantryCommandProcessor::checkTimeoutAndDisable() {
  if (motorsEnabled_ &&
      (millis() - lastCommandTime_) >= GantryConfig::INACTIVITY_TIMEOUT_MS) {
    // Source-verified behavior: timeout causes motion (full homing) before
    // disabling. A passive timeout or emergency-stop policy is deferred.
    Serial.println("TIMEOUT: Homing and disabling motors...");
    motion_.homeAllAxes();
    motion_.disableMotors();
    motorsEnabled_ = false;
    lastCommandTime_ = millis();
  }
}

// X is checked only between blocking moves. Other lines consumed by these
// patrol checks are discarded; normal command dispatch does not run here.
void GantryCommandProcessor::patrolGrid() {
  Serial.println("Patrolling grid... send 'X' to stop.");
  for (int row = 1; row <= GantryConfig::MAX_ROWS; ++row) {
    if (Serial.available() > 0) {
      String terminateCmd = Serial.readStringUntil('\n');
      terminateCmd.trim();
      if (terminateCmd.equalsIgnoreCase("X")) {
        Serial.println("Patrol terminated.");
        return;
      }
    }

    if (row % 2 == 1) {
      for (int col = 1; col <= GantryConfig::MAX_COLUMNS; ++col) {
        if (Serial.available() > 0) {
          String cmd = Serial.readStringUntil('\n');
          cmd.trim();
          if (cmd.equalsIgnoreCase("X")) {
            Serial.println("Patrol terminated.");
            return;
          }
        }

        // Keep the legacy duplicate START: goToGridPosition() prints another.
        Serial.print("START ");
        Serial.print(col);
        Serial.print(" ");
        Serial.println(row);

        motion_.goToGridPosition(col, row);
        delay(GantryConfig::MOTION_SETTLE_DELAY_MS);
      }
    } else {
      for (int col = GantryConfig::MAX_COLUMNS; col >= 1; --col) {
        if (Serial.available() > 0) {
          String cmd = Serial.readStringUntil('\n');
          cmd.trim();
          if (cmd.equalsIgnoreCase("X")) {
            Serial.println("Patrol terminated.");
            return;
          }
        }

        // Keep the legacy duplicate START: goToGridPosition() prints another.
        Serial.print("START ");
        Serial.print(col);
        Serial.print(" ");
        Serial.println(row);

        motion_.goToGridPosition(col, row);
        delay(GantryConfig::MOTION_SETTLE_DELAY_MS);
      }
    }
  }
  Serial.println("Patrol complete.");
}

void GantryCommandProcessor::goNextGridPosition() {
  if (currentRow_ == 0 && currentCol_ == 0) {
    currentRow_ = 1;
    currentCol_ = 1;
  } else if (currentRow_ % 2 == 1) {
    if (currentCol_ < GantryConfig::MAX_COLUMNS) {
      ++currentCol_;
    } else if (currentRow_ < GantryConfig::MAX_ROWS) {
      ++currentRow_;
      currentCol_ = GantryConfig::MAX_COLUMNS;
    } else {
      currentRow_ = 1;
      currentCol_ = 1;
    }
  } else {
    if (currentCol_ > 1) {
      --currentCol_;
    } else if (currentRow_ < GantryConfig::MAX_ROWS) {
      ++currentRow_;
      currentCol_ = 1;
    } else {
      currentRow_ = 1;
      currentCol_ = 1;
    }
  }

  // Keep the legacy duplicate START: goToGridPosition() prints another.
  Serial.print("START ");
  Serial.print(currentCol_);
  Serial.print(" ");
  Serial.println(currentRow_);

  motion_.goToGridPosition(currentCol_, currentRow_);
}

void GantryCommandProcessor::processSerialCommand() {
  if (Serial.available() <= 0) {
    return;
  }

  String input = Serial.readStringUntil('\n');
  input.trim();
  if (input.length() == 0) {
    return;
  }

  // Preserve the legacy O behavior: it homes dual Y before disabling and is
  // not an immediate stop. Changing that contract requires physical validation.
  if (input.equalsIgnoreCase("O")) {
    Serial.println("Received 'O': Disabling motors.");
    motion_.bumpHomeDualY();
    motion_.disableMotors();
    motorsEnabled_ = false;
    lastCommandTime_ = millis();
    return;
  }

  // Recovery precedes validation: even a malformed nonempty command can
  // enable outputs and request a full home when logically disabled.
  if (!motorsEnabled_) {
    Serial.println("Re-enabling motors and re-homing.");
    motion_.enableMotors();
    motorsEnabled_ = true;
    motion_.homeAllAxes();
    motion_.setCurrentPositionsToZero();
    currentCol_ = 0;
    currentRow_ = 0;
  }

  // A long operation may exceed the inactivity interval before returning;
  // the next outer-loop check can therefore home and disable immediately.
  lastCommandTime_ = millis();

  if (input.equalsIgnoreCase("P")) {
    Serial.println("Starting patrol...");
    patrolGrid();
    return;
  }
  if (input.equalsIgnoreCase("G")) {
    Serial.println("Go Next command received.");
    goNextGridPosition();
    return;
  }

  if (input.length() == 1) {
    const char cmd = input.charAt(0);
    switch (cmd) {
      case 'U':
      case 'u':
        Serial.println("Moving up.");
        motion_.moveYBy(GantryConfig::RELATIVE_Y_MM);
        break;
      case 'D':
      case 'd':
        Serial.println("Moving down.");
        motion_.moveYBy(-GantryConfig::RELATIVE_Y_MM);
        break;
      case 'L':
      case 'l':
        Serial.println("Moving left.");
        motion_.moveXRelativeSteps(1, GantryConfig::RELATIVE_X_MM, false);
        break;
      case 'R':
      case 'r':
        Serial.println("Moving right.");
        motion_.moveXRelativeSteps(1, GantryConfig::RELATIVE_X_MM, true);
        break;
      default:
        Serial.println("Unknown single-letter command.");
        break;
    }
    return;
  }

  const int spaceIndex = input.indexOf(' ');
  if (spaceIndex == -1) {
    Serial.println("Invalid command format.");
    return;
  }

  // Arduino String numeric conversion is permissive; malformed fields may
  // become zero. Keep this parser contract separate from Pi-side validation.
  const int col = input.substring(0, spaceIndex).toInt();
  const int row = input.substring(spaceIndex + 1).toInt();

  // Home reports Homing complete. but no POS; homed zero is not grid (1,1).
  if (col == 0 && row == 0) {
    Serial.println("Re-homing all axes...");
    motion_.homeAllAxes();
    motion_.setCurrentPositionsToZero();
    currentCol_ = 0;
    currentRow_ = 0;
    return;
  }

  if (col < 1 || col > GantryConfig::MAX_COLUMNS || row < 1 ||
      row > GantryConfig::MAX_ROWS) {
    Serial.println("Error: Grid coordinates out of range.");
    return;
  }

  currentCol_ = col;
  currentRow_ = row;
  motion_.goToGridPosition(col, row);
}
