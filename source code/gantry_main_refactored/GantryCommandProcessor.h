#ifndef GANTRY_COMMAND_PROCESSOR_H
#define GANTRY_COMMAND_PROCESSOR_H

#include <Arduino.h>

#include "GantryMotion.h"

class GantryCommandProcessor {
 public:
  explicit GantryCommandProcessor(GantryMotion& motion);

  void checkTimeoutAndDisable();
  void processSerialCommand();

 private:
  GantryMotion& motion_;
  // Snake traversal bookkeeping, not measured motor position. Relative moves
  // and firmware patrol do not update these two fields.
  int currentCol_;
  int currentRow_;
  unsigned long lastCommandTime_;
  bool motorsEnabled_;

  void patrolGrid();
  void goNextGridPosition();
};

#endif  // GANTRY_COMMAND_PROCESSOR_H
