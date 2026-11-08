#include "GantryMotion.h"

#include <Arduino.h>

#include "GantryConfig.h"

GantryMotion::GantryMotion()
    : stepperX_(MOTOR_INTERFACE_TYPE,
                GantryConfig::X_STEP_PIN,
                GantryConfig::X_DIR_PIN),
      stepperY1_(MOTOR_INTERFACE_TYPE,
                 GantryConfig::Y1_STEP_PIN,
                 GantryConfig::Y1_DIR_PIN),
      stepperY2_(MOTOR_INTERFACE_TYPE,
                 GantryConfig::Y2_STEP_PIN,
                 GantryConfig::Y2_DIR_PIN) {
  pinMode(GantryConfig::LIMIT_PIN_X, INPUT_PULLUP);
  pinMode(GantryConfig::LIMIT_PIN_Y1, INPUT_PULLUP);
  pinMode(GantryConfig::LIMIT_PIN_Y2, INPUT_PULLUP);

  pinMode(GantryConfig::ENABLE_PIN_X, OUTPUT);
  pinMode(GantryConfig::ENABLE_PIN_Y1, OUTPUT);
  pinMode(GantryConfig::ENABLE_PIN_Y2, OUTPUT);

  stepperX_.setMaxSpeed(GantryConfig::MOVE_SPEED_MM_PER_SEC *
                        GantryConfig::STEPS_PER_MM_X);
  stepperY1_.setMaxSpeed(GantryConfig::MOVE_SPEED_MM_PER_SEC *
                         GantryConfig::STEPS_PER_MM_Y);
  stepperY2_.setMaxSpeed(GantryConfig::MOVE_SPEED_MM_PER_SEC *
                         GantryConfig::STEPS_PER_MM_Y);

  stepperX_.setAcceleration(GantryConfig::ACCELERATION_STEPS_PER_SEC2);
  stepperY1_.setAcceleration(GantryConfig::ACCELERATION_STEPS_PER_SEC2);
  stepperY2_.setAcceleration(GantryConfig::ACCELERATION_STEPS_PER_SEC2);

  stepperX_.setPinsInverted(true, false, false);
  stepperY1_.setPinsInverted(true, false, false);
  stepperY2_.setPinsInverted(false, false, false);
}

void GantryMotion::enableMotors() {
  digitalWrite(GantryConfig::ENABLE_PIN_X, LOW);
  digitalWrite(GantryConfig::ENABLE_PIN_Y1, LOW);
  digitalWrite(GantryConfig::ENABLE_PIN_Y2, LOW);
  Serial.println("Motors enabled.");
}

void GantryMotion::disableMotors() {
  digitalWrite(GantryConfig::ENABLE_PIN_X, HIGH);
  digitalWrite(GantryConfig::ENABLE_PIN_Y1, HIGH);
  digitalWrite(GantryConfig::ENABLE_PIN_Y2, HIGH);
  Serial.println("Motors disabled.");
}

// This pre-existing refactor fault path differs from legacy GantryController:
// it writes disable outputs before the error/halt. Source intent is not a
// physical stop validation record; no serial command can recover this loop.
void GantryMotion::errorStop(const char* axisName) {
  // A homing fault must not leave the drivers energized.  Stop scheduling
  // pulses first, then raise all three active-low enable lines before
  // reporting and entering the deliberate fault halt.
  stepperX_.setSpeed(0);
  stepperY1_.setSpeed(0);
  stepperY2_.setSpeed(0);
  disableMotors();
  Serial.print("ERROR: Homing error on ");
  Serial.print(axisName);
  Serial.println(". Halting.");
  while (true) {
  }
}

void GantryMotion::bumpHomeX() {
  const float fastSpeed = GantryConfig::HOMING_SPEED_MM_PER_SEC *
                          GantryConfig::STEPS_PER_MM_X;
  const float slowSpeed = GantryConfig::SLOW_HOMING_SPEED_MM_PER_SEC *
                          GantryConfig::STEPS_PER_MM_X;

  Serial.println("X-axis: Fast homing...");
  unsigned long startTime = millis();
  stepperX_.setSpeed(-fastSpeed);
  bool confirmed = false;
  unsigned long debounceStart = 0;
  while (true) {
    if (digitalRead(GantryConfig::LIMIT_PIN_X) == LOW) {
      if (!confirmed) {
        // Stop on the first electrical edge.  Debounce while stationary so
        // the legacy 50 ms confirmation does not add fast-homing overtravel.
        stepperX_.setSpeed(0);
        debounceStart = millis();
        confirmed = true;
      } else if (millis() - debounceStart >= GantryConfig::DEBOUNCE_DELAY_MS) {
        break;
      }
    } else {
      if (confirmed) {
        // The edge was switch bounce; resume the approach at the configured
        // legacy speed and wait for the next edge.
        stepperX_.setSpeed(-fastSpeed);
      }
      confirmed = false;
    }

    if (millis() - startTime > GantryConfig::MAX_HOMING_TIME_MS) {
      errorStop("X-axis (fast)");
    }
    if (!confirmed) {
      stepperX_.runSpeed();
    }
  }
  stepperX_.setSpeed(0);

  const long bumpSteps =
      GantryConfig::BUMP_DISTANCE_MM * GantryConfig::STEPS_PER_MM_X;
  Serial.println("X-axis: Bump retraction...");
  // Retraction has no timeout or continuous endstop/serial checks.
  stepperX_.move(bumpSteps);
  while (stepperX_.distanceToGo() != 0) {
    stepperX_.run();
  }

  Serial.println("X-axis: Slow homing...");
  startTime = millis();
  stepperX_.setSpeed(-slowSpeed);
  confirmed = false;
  debounceStart = 0;
  while (true) {
    if (digitalRead(GantryConfig::LIMIT_PIN_X) == LOW) {
      if (!confirmed) {
        stepperX_.setSpeed(0);
        debounceStart = millis();
        confirmed = true;
      } else if (millis() - debounceStart >= GantryConfig::DEBOUNCE_DELAY_MS) {
        break;
      }
    } else {
      if (confirmed) {
        stepperX_.setSpeed(-slowSpeed);
      }
      confirmed = false;
    }

    if (millis() - startTime > GantryConfig::MAX_HOMING_TIME_MS) {
      errorStop("X-axis (slow)");
    }
    if (!confirmed) {
      stepperX_.runSpeed();
    }
  }
  stepperX_.setSpeed(0);
  delay(GantryConfig::HOMING_SETTLE_DELAY_MS);
  stepperX_.setCurrentPosition(0);
  Serial.println("X-axis homed.");
}

void GantryMotion::bumpHomeDualY() {
  Serial.println("Y-axes: Fast homing...");
  const float fastSpeed = GantryConfig::HOMING_SPEED_MM_PER_SEC *
                          GantryConfig::STEPS_PER_MM_Y;
  const float slowSpeed = GantryConfig::SLOW_HOMING_SPEED_MM_PER_SEC *
                          GantryConfig::STEPS_PER_MM_Y;

  stepperY1_.setSpeed(-fastSpeed);
  stepperY2_.setSpeed(-fastSpeed);

  unsigned long startTime = millis();
  bool y1Confirmed = false;
  bool y2Confirmed = false;
  unsigned long y1DebounceStart = 0;
  unsigned long y2DebounceStart = 0;

  while (true) {
    const int stateY1 = digitalRead(GantryConfig::LIMIT_PIN_Y1);
    const int stateY2 = digitalRead(GantryConfig::LIMIT_PIN_Y2);
    if (stateY1 == LOW) {
      if (!y1Confirmed) {
        stepperY1_.setSpeed(0);
        y1DebounceStart = millis();
        y1Confirmed = true;
      }
    } else {
      if (y1Confirmed) {
        stepperY1_.setSpeed(-fastSpeed);
      }
      y1Confirmed = false;
    }
    if (stateY2 == LOW) {
      if (!y2Confirmed) {
        stepperY2_.setSpeed(0);
        y2DebounceStart = millis();
        y2Confirmed = true;
      }
    } else {
      if (y2Confirmed) {
        stepperY2_.setSpeed(-fastSpeed);
      }
      y2Confirmed = false;
    }

    if (y1Confirmed && y2Confirmed &&
        (millis() - y1DebounceStart >= GantryConfig::DEBOUNCE_DELAY_MS) &&
        (millis() - y2DebounceStart >= GantryConfig::DEBOUNCE_DELAY_MS)) {
      break;
    }
    if (millis() - startTime > GantryConfig::MAX_HOMING_TIME_MS) {
      errorStop("Dual Y-axes (fast)");
    }
    if (!y1Confirmed) {
      stepperY1_.runSpeed();
    }
    if (!y2Confirmed) {
      stepperY2_.runSpeed();
    }
  }
  stepperY1_.setSpeed(0);
  stepperY2_.setSpeed(0);

  const long bumpSteps =
      GantryConfig::BUMP_DISTANCE_MM * GantryConfig::STEPS_PER_MM_Y;
  Serial.println("Y-axes: Bump retraction...");
  stepperY1_.move(bumpSteps);
  stepperY2_.move(bumpSteps);
  while (stepperY1_.distanceToGo() != 0 || stepperY2_.distanceToGo() != 0) {
    stepperY1_.run();
    stepperY2_.run();
  }

  Serial.println("Y-axes: Slow homing...");
  startTime = millis();
  stepperY1_.setSpeed(-slowSpeed);
  stepperY2_.setSpeed(-slowSpeed);
  y1Confirmed = false;
  y2Confirmed = false;
  y1DebounceStart = 0;
  y2DebounceStart = 0;
  while (true) {
    const int stateY1 = digitalRead(GantryConfig::LIMIT_PIN_Y1);
    const int stateY2 = digitalRead(GantryConfig::LIMIT_PIN_Y2);
    if (stateY1 == LOW) {
      if (!y1Confirmed) {
        stepperY1_.setSpeed(0);
        y1DebounceStart = millis();
        y1Confirmed = true;
      }
    } else {
      if (y1Confirmed) {
        stepperY1_.setSpeed(-slowSpeed);
      }
      y1Confirmed = false;
    }
    if (stateY2 == LOW) {
      if (!y2Confirmed) {
        stepperY2_.setSpeed(0);
        y2DebounceStart = millis();
        y2Confirmed = true;
      }
    } else {
      if (y2Confirmed) {
        stepperY2_.setSpeed(-slowSpeed);
      }
      y2Confirmed = false;
    }

    if (y1Confirmed && y2Confirmed &&
        (millis() - y1DebounceStart >= GantryConfig::DEBOUNCE_DELAY_MS) &&
        (millis() - y2DebounceStart >= GantryConfig::DEBOUNCE_DELAY_MS)) {
      break;
    }
    if (millis() - startTime > GantryConfig::MAX_HOMING_TIME_MS) {
      errorStop("Dual Y-axes (slow)");
    }
    if (!y1Confirmed) {
      stepperY1_.runSpeed();
    }
    if (!y2Confirmed) {
      stepperY2_.runSpeed();
    }
  }
  stepperY1_.setSpeed(0);
  stepperY2_.setSpeed(0);
  delay(GantryConfig::HOMING_SETTLE_DELAY_MS);
  stepperY1_.setCurrentPosition(0);
  stepperY2_.setCurrentPosition(0);
  Serial.println("Y-axes homed.");
}

void GantryMotion::homeAllAxes() {
  Serial.println("Starting homing procedure...");
  Serial.println("Homing X-axis...");
  bumpHomeX();
  Serial.println("Homing Y-axes...");
  bumpHomeDualY();
  Serial.println("Homing complete.");
}

void GantryMotion::setCurrentPositionsToZero() {
  stepperX_.setCurrentPosition(0);
  stepperY1_.setCurrentPosition(0);
  stepperY2_.setCurrentPosition(0);
}

// One-based caller coordinates are trusted here. Software clamps constrain
// targets after lookup; no external position feedback verifies POS arrival.
void GantryMotion::goToGridPosition(int col, int row) {
  long targetX = GantryConfig::X_POSITIONS_STEPS[row - 1][col - 1];
  long targetY = GantryConfig::Y_POSITIONS_STEPS[row - 1];

  if (targetX < GantryConfig::MIN_X_STEPS) {
    targetX = GantryConfig::MIN_X_STEPS;
  }
  if (targetX > GantryConfig::MAX_X_STEPS) {
    targetX = GantryConfig::MAX_X_STEPS;
  }
  if (targetY < GantryConfig::MIN_Y_STEPS) {
    targetY = GantryConfig::MIN_Y_STEPS;
  }
  if (targetY > GantryConfig::MAX_Y_STEPS) {
    targetY = GantryConfig::MAX_Y_STEPS;
  }

  Serial.print("START ");
  Serial.print(col);
  Serial.print(" ");
  Serial.println(row);

  stepperX_.moveTo(targetX);
  stepperY1_.moveTo(targetY);
  stepperY2_.moveTo(targetY);
  // run() services all channels cooperatively; normal movement does not
  // poll endstops or incoming stop commands inside this blocking loop.
  while (stepperX_.distanceToGo() != 0 || stepperY1_.distanceToGo() != 0 ||
         stepperY2_.distanceToGo() != 0) {
    stepperX_.run();
    stepperY1_.run();
    stepperY2_.run();
  }

  Serial.print("POS ");
  Serial.print(col);
  Serial.print(" ");
  Serial.println(row);

  delay(GantryConfig::MOTION_SETTLE_DELAY_MS);
}

void GantryMotion::moveXRelativeSteps(int steps,
                                      float intervalMm,
                                      bool rightDirection) {
  long stepDistance = intervalMm * GantryConfig::STEPS_PER_MM_X;
  if (!rightDirection) {
    stepDistance = -stepDistance;
  }

  for (int i = 0; i < steps; ++i) {
    long newTarget = stepperX_.currentPosition() + stepDistance;
    if (newTarget < GantryConfig::MIN_X_STEPS) {
      newTarget = GantryConfig::MIN_X_STEPS;
    }
    if (newTarget > GantryConfig::MAX_X_STEPS) {
      newTarget = GantryConfig::MAX_X_STEPS;
    }
    stepperX_.moveTo(newTarget);
    while (stepperX_.distanceToGo() != 0) {
      stepperX_.run();
    }
    delay(GantryConfig::MOTION_SETTLE_DELAY_MS);
  }
}

// Float-to-long truncation preserves the legacy conversion; both Y targets
// are based on Y1 currentPosition(), not independent measured positions.
void GantryMotion::moveYBy(float deltaMm) {
  const long deltaSteps = deltaMm * GantryConfig::STEPS_PER_MM_Y;
  long newTarget = stepperY1_.currentPosition() + deltaSteps;

  if (newTarget < GantryConfig::MIN_Y_STEPS) {
    newTarget = GantryConfig::MIN_Y_STEPS;
  }
  if (newTarget > GantryConfig::MAX_Y_STEPS) {
    newTarget = GantryConfig::MAX_Y_STEPS;
  }

  stepperY1_.moveTo(newTarget);
  stepperY2_.moveTo(newTarget);
  while (stepperY1_.distanceToGo() != 0 || stepperY2_.distanceToGo() != 0) {
    stepperY1_.run();
    stepperY2_.run();
  }
  delay(GantryConfig::MOTION_SETTLE_DELAY_MS);
}
