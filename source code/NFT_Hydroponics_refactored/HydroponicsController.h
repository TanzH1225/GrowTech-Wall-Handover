#ifndef GROWTECH_HYDROPONICS_CONTROLLER_H
#define GROWTECH_HYDROPONICS_CONTROLLER_H

#include <Arduino.h>
#include <RTClib.h>

class HydroponicsController {
 public:
  HydroponicsController();

  void begin();
  void update();

 private:
  RTC_DS3231 rtc_;

  // All state is RAM-owned by the single update() path; reset restores
  // defaults. Positive manual ACID/FERT doses capture their own duration;
  // auto/fallback/pesticide shutoffs read the current global duration.
  unsigned long doseTimeMs_;
  uint8_t lightOnHour_;
  uint8_t lightOffHour_;

  bool acidActive_;
  bool acidManualDose_;
  bool fertActive_;
  bool fertManualDose_;
  bool pesticideActive_;

  unsigned long acidStartTime_;
  unsigned long acidManualDuration_;
  unsigned long fertStartTime_;
  unsigned long fertManualDuration_;
  unsigned long pesticideStartTime_;

  // Manual LIGHT persists until a valid schedule-hour command or reset.
  bool lightState_;
  bool manualOverride_;

  bool ecAutoEnabled_;
  bool phAutoEnabled_;
  float ecTarget_;
  float phTarget_;
  unsigned long ecLastDoseTime_;
  unsigned long phLastDoseTime_;

  float ecSlope_;
  float ecIntercept_;
  float phK1Slope_;
  float phK2Slope_;
  unsigned long lastStatusTime_;

  void configurePins();
  void setInitialOutputs();
  void blinkLightAtStartup();
  void initializeCalibrations();

  void updateTimedShutoffs(unsigned long nowMs);
  void updateLightingState(const DateTime &now);
  void updateEcAutoDose(float currentEc, unsigned long nowMs);
  void updatePhAutoDose(float currentPh, unsigned long nowMs);
  void publishStatus(float currentEc, float currentPh, unsigned long nowMs);
  void processOneSerialCommand(unsigned long nowMs);
  void processCommand(const String &command, unsigned long nowMs);
  void processDoseCommand(const String &value, unsigned long nowMs);

  float calibrateEc(int raw) const;
  float readPh();
  float calibrateWaterPercent(int raw) const;
};

#endif
