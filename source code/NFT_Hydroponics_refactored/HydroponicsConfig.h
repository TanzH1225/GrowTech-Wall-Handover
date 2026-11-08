#ifndef GROWTECH_HYDROPONICS_CONFIG_H
#define GROWTECH_HYDROPONICS_CONFIG_H

#include <Arduino.h>

namespace HydroponicsConfig {

// Pin assignments are copied from the authoritative timestamped firmware.
// The NO/NC descriptions are legacy source evidence; installed wiring and
// electrical behavior still require physical validation.
const uint8_t PIN_ACID_PUMP = 2;       // D2: Acid pump (NO), HIGH = on
const uint8_t PIN_FERTB_PUMP = 3;      // D3: Fertilizer B pump (NO), HIGH = on
const uint8_t PIN_FERTA_PUMP = 4;      // D4: Fertilizer A pump (NO), HIGH = on
const uint8_t PIN_WATER_PUMP = 5;      // D5: Main water pump (NC), LOW = on
const uint8_t PIN_LIGHT_RELAY = 9;     // D9: Lighting relay (NC), LOW = on
const uint8_t PIN_PESTICIDE_PUMP = 10; // D10: Pesticide pump (NO), HIGH = on

const uint8_t PIN_WATER_LEVEL = A0;
const uint8_t PIN_EC_SENSOR = A1;
const uint8_t PIN_PH_SENSOR = A2;

const unsigned long SERIAL_BAUD = 9600UL;
// Dosing uses a source assumption of 1000 ms per requested mL. Delivered
// volume, calibration, and installed output polarity are physically unverified.
const unsigned long DEFAULT_DOSE_TIME_MS = 5000UL;
const unsigned long SENSOR_PRINT_INTERVAL_MS = 1000UL;
const unsigned long EC_DOSE_INTERVAL_MS = 10UL * 60UL * 1000UL;
const unsigned long PH_DOSE_INTERVAL_MS = 10UL * 60UL * 1000UL;

const uint8_t DEFAULT_LIGHT_ON_HOUR = 7;
const uint8_t DEFAULT_LIGHT_OFF_HOUR = 19;
const uint8_t STARTUP_LIGHT_BLINK_COUNT = 2;
const unsigned long STARTUP_LIGHT_BLINK_MS = 200UL;

// EC calibration constants.
const int EC_RAW_A = 64;
const float EC_VAL_A = 84.0F;
const int EC_RAW_B = 439;
const float EC_VAL_B = 12880.0F;

// pH calibration and sampling constants.
// readPh() discards both extremes, keeps 60 readings, and assumes a
// 5000 mV reference with ADC denominator 1024; retain the actual branch slopes.
const int PH_SAMPLE_COUNT = 100;
const int PH_DISCARD_COUNT = 20;
const int PH_MV_4 = 2773;
const int PH_MV_6_86 = 2275;
const int PH_MV_9_18 = 1889;
const unsigned long PH_SAMPLE_DELAY_MS = 1UL;

// Water-level polynomial coefficients.
const float WATER_COEF_A = 2.30841033e-5F;
const float WATER_COEF_B = -1.37886629e-2F;
const float WATER_COEF_C = 2.74150783e+0F;
const float WATER_COEF_D = -9.29694804e+1F;

}  // namespace HydroponicsConfig

#endif
