// Analog triggers become digital Switch buttons at explicit travel thresholds.
// A narrow release band avoids chatter without inheriting GameController's
// device-dependent isPressed hysteresis (which may release only at zero).
#pragma once
#include <math.h>

static inline int pad_trigger_pressed(int down, float value, float press, float release) {
    return isfinite(value) && (down ? value > release : value >= press);
}
