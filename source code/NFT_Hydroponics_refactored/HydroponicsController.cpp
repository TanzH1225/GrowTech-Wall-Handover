#include "HydroponicsController.h"

#include <Wire.h>

#include "HydroponicsConfig.h"

using namespace HydroponicsConfig;

HydroponicsController::HydroponicsController()
    : doseTimeMs_(DEFAULT_DOSE_TIME_MS),
      lightOnHour_(DEFAULT_LIGHT_ON_HOUR),
      lightOffHour_(DEFAULT_LIGHT_OFF_HOUR),
      acidActive_(false),
      acidManualDose_(false),
      fertActive_(false),
      fertManualDose_(false),
      pesticideActive_(false),
      acidStartTime_(0),
      acidManualDuration_(0),
      fertStartTime_(0),
      fertManualDuration_(0),
      pesticideStartTime_(0),
      lightState_(false),
      manualOverride_(false),
      ecAutoEnabled_(false),
      phAutoEnabled_(false),
      ecTarget_(0.0F),
      phTarget_(0.0F),
      ecLastDoseTime_(0),
      phLastDoseTime_(0),
      ecSlope_(1.0F),
      ecIntercept_(0.0F),
      phK1Slope_(0.0F),
      phK2Slope_(0.0F),
      lastStatusTime_(0) {}

void HydroponicsController::begin() {
  Serial.begin(SERIAL_BAUD);
  Wire.begin();

  configurePins();
  setInitialOutputs();

  if (!rtc_.begin()) {
    Serial.println(F("RTC missing!"));
    while (1) {
      // Preserve the legacy permanent halt when the RTC is unavailable.
    }
  }
  // Lost-power recovery uses build time, not Pi time or current upload time.
  if (rtc_.lostPower()) {
    rtc_.adjust(DateTime(__DATE__, __TIME__));
  }

  blinkLightAtStartup();
  initializeCalibrations();
}

void HydroponicsController::configurePins() {
  pinMode(PIN_ACID_PUMP, OUTPUT);
  pinMode(PIN_FERTB_PUMP, OUTPUT);
  pinMode(PIN_FERTA_PUMP, OUTPUT);
  pinMode(PIN_PESTICIDE_PUMP, OUTPUT);
  pinMode(PIN_LIGHT_RELAY, OUTPUT);
  pinMode(PIN_WATER_PUMP, OUTPUT);
  pinMode(PIN_WATER_LEVEL, INPUT);
  pinMode(PIN_EC_SENSOR, INPUT);
  pinMode(PIN_PH_SENSOR, INPUT);
}

void HydroponicsController::setInitialOutputs() {
  digitalWrite(PIN_ACID_PUMP, LOW);
  digitalWrite(PIN_FERTB_PUMP, LOW);
  digitalWrite(PIN_FERTA_PUMP, LOW);
  digitalWrite(PIN_PESTICIDE_PUMP, LOW);
  digitalWrite(PIN_LIGHT_RELAY, HIGH);
  digitalWrite(PIN_WATER_PUMP, HIGH);
}

void HydroponicsController::blinkLightAtStartup() {
  for (uint8_t i = 0; i < STARTUP_LIGHT_BLINK_COUNT; ++i) {
    digitalWrite(PIN_LIGHT_RELAY, LOW);
    delay(STARTUP_LIGHT_BLINK_MS);
    digitalWrite(PIN_LIGHT_RELAY, HIGH);
    delay(STARTUP_LIGHT_BLINK_MS);
  }
}

void HydroponicsController::initializeCalibrations() {
  ecSlope_ = (EC_VAL_B - EC_VAL_A) / float(EC_RAW_B - EC_RAW_A);
  ecIntercept_ = EC_VAL_A - ecSlope_ * EC_RAW_A;
  phK1Slope_ = float(686 - 400) / abs(PH_MV_4 - PH_MV_6_86);
  phK2Slope_ = float(918 - 686) / abs(PH_MV_6_86 - PH_MV_9_18);
}

void HydroponicsController::update() {
  const DateTime now = rtc_.now();
  // One timestamp is reused throughout this iteration. pH sampling and a
  // partial serial line can delay later writes beyond this snapshot.
  const unsigned long nowMs = millis();

  // Preserve the legacy loop ordering: shutoffs, lighting, EC, pH, status,
  // then at most one serial command.
  updateTimedShutoffs(nowMs);
  updateLightingState(now);

  const float currentEc = calibrateEc(analogRead(PIN_EC_SENSOR));
  updateEcAutoDose(currentEc, nowMs);

  const float currentPh = readPh();
  updatePhAutoDose(currentPh, nowMs);

  publishStatus(currentEc, currentPh, nowMs);
  processOneSerialCommand(nowMs);
}

// These are cooperative deadline checks, not interrupts. Blocking sampling
// or serial reads delay the next chance to turn an active output off.
void HydroponicsController::updateTimedShutoffs(unsigned long nowMs) {
  if (acidActive_ &&
      nowMs - acidStartTime_ >=
          (acidManualDose_ ? acidManualDuration_ : doseTimeMs_)) {
    digitalWrite(PIN_ACID_PUMP, LOW);
    acidActive_ = false;
    acidManualDose_ = false;
  }

  if (fertActive_ &&
      nowMs - fertStartTime_ >=
          (fertManualDose_ ? fertManualDuration_ : doseTimeMs_)) {
    digitalWrite(PIN_FERTA_PUMP, LOW);
    digitalWrite(PIN_FERTB_PUMP, LOW);
    fertActive_ = false;
    fertManualDose_ = false;
  }

  if (pesticideActive_ &&
      nowMs - pesticideStartTime_ >= doseTimeMs_) {
    digitalWrite(PIN_PESTICIDE_PUMP, LOW);
    pesticideActive_ = false;
  }
}

void HydroponicsController::updateLightingState(const DateTime &now) {
  if (manualOverride_) {
    return;
  }

  // Same-day half-open interval only; overnight/equal-hour schedules do not
  // wrap across midnight. Manual override bypasses this entire comparison.
  const bool on =
      now.hour() >= lightOnHour_ && now.hour() < lightOffHour_;
  if (on != lightState_) {
    lightState_ = on;
    digitalWrite(PIN_LIGHT_RELAY, on ? LOW : HIGH);
  }
}

void HydroponicsController::updateEcAutoDose(float currentEc,
                                              unsigned long nowMs) {
  if (ecAutoEnabled_ && !fertActive_ && currentEc < ecTarget_ &&
      (ecLastDoseTime_ == 0 ||
       nowMs - ecLastDoseTime_ >= EC_DOSE_INTERVAL_MS)) {
    digitalWrite(PIN_FERTA_PUMP, HIGH);
    digitalWrite(PIN_FERTB_PUMP, HIGH);
    fertActive_ = true;
    fertStartTime_ = nowMs;
    ecLastDoseTime_ = nowMs;
  }
}

void HydroponicsController::updatePhAutoDose(float currentPh,
                                              unsigned long nowMs) {
  if (phAutoEnabled_ && !acidActive_ && currentPh > phTarget_ &&
      (phLastDoseTime_ == 0 ||
       nowMs - phLastDoseTime_ >= PH_DOSE_INTERVAL_MS)) {
    digitalWrite(PIN_ACID_PUMP, HIGH);
    acidActive_ = true;
    acidStartTime_ = nowMs;
    phLastDoseTime_ = nowMs;
  }
}

// Periodic state report, not a correlated command ACK or evidence of flow.
// update() publishes before processing its next command, so a requested change
// generally appears in a later record. millis is uptime, not RTC wall time.
void HydroponicsController::publishStatus(float currentEc, float currentPh,
                                           unsigned long nowMs) {
  if (nowMs - lastStatusTime_ < SENSOR_PRINT_INTERVAL_MS) {
    return;
  }
  lastStatusTime_ = nowMs;

  const float waterPercent =
      calibrateWaterPercent(analogRead(PIN_WATER_LEVEL));
  Serial.print("STAT,");
  Serial.print(nowMs);
  Serial.print(',');
  Serial.print(waterPercent, 1);
  Serial.print(',');
  Serial.print(currentEc, 1);
  Serial.print(',');
  Serial.print(currentPh, 2);
  Serial.print(',');
  Serial.print(lightState_ ? '1' : '0');
  Serial.print(',');
  Serial.print(digitalRead(PIN_WATER_PUMP) == LOW ? '1' : '0');
  Serial.print(',');
  Serial.print(acidActive_ ? '1' : '0');
  Serial.print(',');
  Serial.print(fertActive_ ? '1' : '0');
  Serial.print(',');
  Serial.print(pesticideActive_ ? '1' : '0');
  Serial.println();
}

void HydroponicsController::processOneSerialCommand(unsigned long nowMs) {
  if (!Serial.available()) {
    return;
  }

  // No custom Stream timeout is configured; incomplete newline framing can
  // block this loop according to the selected Arduino core default.
  String command = Serial.readStringUntil('\n');
  command.trim();
  processCommand(command, nowMs);
}

void HydroponicsController::processCommand(const String &command,
                                            unsigned long nowMs) {
  const int separator = command.indexOf(':');
  String key = separator > 0 ? command.substring(0, separator) : command;
  String value = separator > 0 ? command.substring(separator + 1) : "";
  key.toUpperCase();
  value.toUpperCase();

  if (key == "WATER_PUMP") {
    digitalWrite(PIN_WATER_PUMP, value == "ON" ? LOW : HIGH);
  } else if (key == "LIGHT") {
    const bool on = value == "ON";
    manualOverride_ = true;
    lightState_ = on;
    digitalWrite(PIN_LIGHT_RELAY, on ? LOW : HIGH);
  } else if (key == "DOSE") {
    processDoseCommand(value, nowMs);
  } else if (key == "TARGET_EC") {
    const float target = value.toFloat();
    ecAutoEnabled_ = target > 0;
    if (target > 0) {
      ecTarget_ = target;
    }
  } else if (key == "TARGET_PH") {
    const float target = value.toFloat();
    phAutoEnabled_ = target > 0;
    if (target > 0) {
      phTarget_ = target;
    }
  } else if (key == "LIGHT_ON_HOUR") {
    const int hour = value.toInt();
    if (hour >= 0 && hour < 24) {
      lightOnHour_ = hour;
      manualOverride_ = false;
    }
  } else if (key == "LIGHT_OFF_HOUR") {
    const int hour = value.toInt();
    if (hour >= 0 && hour < 24) {
      lightOffHour_ = hour;
      manualOverride_ = false;
    }
  } else if (key == "DOSE_TIME") {
    // Preserve the legacy 1 mL -> 1 second assumption. Range limits,
    // plausibility checks, interlocks, and acknowledgements are deferred
    // behavior changes requiring separate physical validation.
    const float millilitres = value.toFloat();
    if (millilitres >= 0) {
      doseTimeMs_ = static_cast<unsigned long>(millilitres * 1000);
    }
  }
  // Unknown commands and malformed values remain silently ignored or use the
  // legacy Arduino String conversion behavior; no new protocol is introduced.
}

void HydroponicsController::processDoseCommand(const String &value,
                                                unsigned long nowMs) {
  const int separator = value.indexOf(':');
  const String type =
      separator > 0 ? value.substring(0, separator) : value;
  const float millilitres =
      separator > 0 ? value.substring(separator + 1).toFloat() : -1;
  const unsigned long duration =
      millilitres > 0
          ? static_cast<unsigned long>(millilitres * 1000)
          : doseTimeMs_;

  // An already active channel ignores a new request. Manual starts do not
  // refresh auto-dose cooldowns, and other chemical channels can overlap.
  if (type == "ACID" && !acidActive_) {
    digitalWrite(PIN_ACID_PUMP, HIGH);
    acidActive_ = true;
    acidStartTime_ = nowMs;
    acidManualDose_ = millilitres > 0;
    acidManualDuration_ = duration;
  } else if (type == "FERT" && !fertActive_) {
    digitalWrite(PIN_FERTA_PUMP, HIGH);
    digitalWrite(PIN_FERTB_PUMP, HIGH);
    fertActive_ = true;
    fertStartTime_ = nowMs;
    fertManualDose_ = millilitres > 0;
    fertManualDuration_ = duration;
  } else if (type == "PEST" && !pesticideActive_) {
    // Preserve legacy behavior: the parsed pesticide mL value is ignored and
    // the current global doseTimeMs_ controls the run duration.
    digitalWrite(PIN_PESTICIDE_PUMP, HIGH);
    pesticideActive_ = true;
    pesticideStartTime_ = nowMs;
  }
}

float HydroponicsController::calibrateEc(int raw) const {
  const float ec = raw * ecSlope_ + ecIntercept_;
  return ec < 0 ? 0 : ec;
}

float HydroponicsController::readPh() {
  static int samples[PH_SAMPLE_COUNT];
  uint32_t sum = 0;

  for (int i = 0; i < PH_SAMPLE_COUNT; ++i) {
    samples[i] = analogRead(PIN_PH_SENSOR);
    delay(PH_SAMPLE_DELAY_MS);
  }

  // Preserve the legacy descending O(n^2) sort and trimmed sample window.
  for (int i = 0; i < PH_SAMPLE_COUNT; ++i) {
    for (int k = i + 1; k < PH_SAMPLE_COUNT; ++k) {
      if (samples[i] < samples[k]) {
        const int temporary = samples[i];
        samples[i] = samples[k];
        samples[k] = temporary;
      }
    }
  }

  for (int i = PH_DISCARD_COUNT;
       i < PH_SAMPLE_COUNT - PH_DISCARD_COUNT; ++i) {
    sum += samples[i];
  }

  const float millivolts =
      sum / float(PH_SAMPLE_COUNT - 2 * PH_DISCARD_COUNT) * 5000.0F /
      1024.0F;
  // Preserve actual legacy pairing: K1 below the 6.86 voltage and K2 above.
  // The named endpoint constants do not establish calibration correctness.
  float ph =
      millivolts < PH_MV_6_86
          ? (PH_MV_6_86 - millivolts) * phK1Slope_ + 686.0F
          : 686.0F - (millivolts - PH_MV_6_86) * phK2Slope_;
  ph = constrain(ph, 0, 1400);
  return ph / 100.0F;
}

float HydroponicsController::calibrateWaterPercent(int raw) const {
  float percent = WATER_COEF_A * raw * raw * raw +
                  WATER_COEF_B * raw * raw + WATER_COEF_C * raw +
                  WATER_COEF_D;
  if (percent < 0) {
    percent = 0;
  }
  if (percent > 100) {
    percent = 100;
  }
  return percent;
}
