// Example 15: Plotter Waveforms
//
// Generic plotter demo — streams four common waveforms on *custom*
// signal names (sine, triangle, square, sawtooth) so they appear in
// the Plotter tab without touching the HMI Dashboard.
//
// What this teaches:
//   - Named signal format with DashboardSignals — any name not in the
//     dashboard property list goes to the Plotter only.
//   - Auto-discovery: new channels show up in the side panel + legend
//     the moment the firmware sends them.
//   - Per-signal color / scale / offset from the signal-list panel
//     (useful for separating overlapping amplitudes).
//
// Periods were chosen pairwise-coprime so the waveforms never all
// line up — makes the plot visually interesting when zoomed out.

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"
#include <math.h>

static const float DT_SEC = 0.05f;  // 20 Hz — matches gaugeAlarm CYCLETIME

static const float T_SINE     = 2.0f;
static const float T_TRIANGLE = 3.0f;
static const float T_SQUARE   = 5.0f;
static const float T_SAWTOOTH = 4.0f;

static float tSec = 0;

static float triangle_wave(float phase) {
    // phase in [0,1): 0 → +1 → -1 → 0 over one period.
    if (phase < 0.25f) return 4.0f * phase;
    if (phase < 0.75f) return 2.0f - 4.0f * phase;
    return -4.0f + 4.0f * phase;
}

static float square_wave(float phase) {
    return phase < 0.5f ? 1.0f : -1.0f;
}

static float sawtooth_wave(float phase) {
    // Rising ramp from -1 to +1, snaps back at phase = 1.
    return 2.0f * phase - 1.0f;
}

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Plotter Waveforms] sine + triangle + square + sawtooth");
}

TASK(SendWaves) {
    tSec += DT_SEC;

    dashSendPrec("sine",     sinf(2.0f * (float)M_PI * tSec / T_SINE),        3);
    dashSendPrec("triangle", triangle_wave(fmodf(tSec, T_TRIANGLE) / T_TRIANGLE), 3);
    dashSendPrec("square",   square_wave(fmodf(tSec, T_SQUARE) / T_SQUARE),   3);
    dashSendPrec("sawtooth", sawtooth_wave(fmodf(tSec, T_SAWTOOTH) / T_SAWTOOTH), 3);

    dashFlush();
    TerminateTask();
}
