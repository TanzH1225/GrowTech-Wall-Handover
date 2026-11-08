#include "GantryConfig.h"

namespace GantryConfig {

// Preserve row-specific legacy measurements, including row 3 differences.
// Calibration provenance and physical alignment are not established by this table.
const long X_POSITIONS_STEPS[MAX_ROWS][MAX_COLUMNS] = {
    {900, 5980, 11100, 16100, 21220, 26520},
    {900, 5980, 11100, 16100, 21220, 26520},
    {900, 6280, 11300, 16100, 21520, 26520},
    {900, 5980, 11100, 16100, 21220, 26520},
};

const long Y_POSITIONS_STEPS[MAX_ROWS] = {
    0,
    6800,
    13600,
    18934,
};

}  // namespace GantryConfig
