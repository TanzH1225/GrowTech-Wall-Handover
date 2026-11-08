#ifndef GANTRY_CONFIG_H
#define GANTRY_CONFIG_H

#include <Arduino.h>

// Source-verified legacy configuration. These values intentionally remain
// centralized and unchanged so that the parallel refactor can be compared
// directly with gantry_main/ before any physical validation is attempted.
namespace GantryConfig {

constexpr uint8_t X_STEP_PIN = 2;
constexpr uint8_t X_DIR_PIN = 3;
constexpr uint8_t Y1_STEP_PIN = 4;
constexpr uint8_t Y1_DIR_PIN = 5;
constexpr uint8_t Y2_STEP_PIN = 6;
constexpr uint8_t Y2_DIR_PIN = 7;

constexpr uint8_t LIMIT_PIN_X = 8;
constexpr uint8_t LIMIT_PIN_Y1 = 9;
constexpr uint8_t LIMIT_PIN_Y2 = 10;

constexpr uint8_t ENABLE_PIN_X = A0;
constexpr uint8_t ENABLE_PIN_Y1 = A1;
constexpr uint8_t ENABLE_PIN_Y2 = A2;

constexpr unsigned long SERIAL_BAUD = 9600;
constexpr unsigned long STARTUP_DELAY_MS = 2000;

// Conversion factors produce step counts; acceleration below is already in
// steps/s^2. Configured mm/s is not a measured physical travel speed.
constexpr float STEPS_PER_MM_X = 40.0F;
constexpr float STEPS_PER_MM_Y = 26.667F;
constexpr float MOVE_SPEED_MM_PER_SEC = 300.0F;
constexpr float ACCELERATION_STEPS_PER_SEC2 = 5000.0F;
constexpr float HOMING_SPEED_MM_PER_SEC = 75.0F;
constexpr float BUMP_DISTANCE_MM = 10.0F;
constexpr float SLOW_HOMING_SPEED_MM_PER_SEC = 10.0F;

constexpr unsigned long MAX_HOMING_TIME_MS = 15000;
constexpr unsigned long DEBOUNCE_DELAY_MS = 50;
constexpr unsigned long INACTIVITY_TIMEOUT_MS = 60000;
constexpr unsigned long MOTION_SETTLE_DELAY_MS = 200;
constexpr unsigned long HOMING_SETTLE_DELAY_MS = 100;

constexpr uint8_t MAX_COLUMNS = 6;
constexpr uint8_t MAX_ROWS = 4;

// External coordinates are one-based; motion indexes [row - 1][col - 1].
// These targets are steps from homed zero, not uniform-spacing millimetres.
extern const long X_POSITIONS_STEPS[MAX_ROWS][MAX_COLUMNS];
extern const long Y_POSITIONS_STEPS[MAX_ROWS];

constexpr long MIN_X_STEPS = 0;
// Preserve the legacy bounds formulas, including the Y-axis use of 40 rather
// than STEPS_PER_MM_Y. Changing those bounds is a deferred motion-policy change.
constexpr long MAX_X_STEPS = static_cast<long>(((6 - 1) * 130.0F + 55.0F) * 40.0F);
constexpr long MIN_Y_STEPS = 0;
constexpr long MAX_Y_STEPS = static_cast<long>(((4 - 1) * 240.0F) * 40.0F);

constexpr float RELATIVE_X_MM = 10.0F;
constexpr float RELATIVE_Y_MM = 10.0F;

}  // namespace GantryConfig

#endif  // GANTRY_CONFIG_H
