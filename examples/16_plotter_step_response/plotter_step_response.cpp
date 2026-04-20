// Example 16: Plotter Step Response
//
// Tailored demo for the Plotter's measurement cursors. Drives a
// square-wave `input` signal and three first-order low-pass outputs
// (`ema_fast`, `ema_med`, `ema_slow`) with deliberately different
// time constants so the step response of each is visually distinct.
//
// What to measure with the cursors:
//   - Place the left cursor on the rising edge of `input`.
//   - Place the right cursor where an EMA reaches ~63 % of the step
//     height (0.63 ≈ 1 - 1/e).
//   - The Stats panel's Δt equals that EMA's time constant τ.
//   - Also useful: min / max / mean of each trace between cursors,
//     e.g. to compute settling bands.
//
// EMA recurrence: y[n] = y[n-1] * (1 - α) + x[n] * α
// Choosing α fixes τ via: τ = -T / ln(1 - α), with T = DT_SEC.

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"
#include <math.h>

static const float DT_SEC = 0.05f;  // 20 Hz — matches stepAlarm CYCLETIME

// Square wave: 3 s low, 3 s high, 0 → 1 amplitude.
static const float STEP_PERIOD_SEC = 6.0f;

// EMA coefficients chosen so the effective τ sits far apart on the
// plot. Values and their resulting τ at DT_SEC = 0.05 s:
//   α = 0.22 → τ ≈ 0.20 s
//   α = 0.10 → τ ≈ 0.47 s
//   α = 0.03 → τ ≈ 1.64 s
static const float ALPHA_FAST = 0.22f;
static const float ALPHA_MED  = 0.10f;
static const float ALPHA_SLOW = 0.03f;

static float tSec = 0;
static float yFast = 0, yMed = 0, ySlow = 0;

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Plotter Step] input + ema_fast/med/slow");
}

TASK(SendStep) {
    tSec += DT_SEC;

    // Square-wave input: high for the first half of each period.
    float phase = fmodf(tSec, STEP_PERIOD_SEC) / STEP_PERIOD_SEC;
    float input = (phase < 0.5f) ? 1.0f : 0.0f;

    yFast = yFast * (1.0f - ALPHA_FAST) + input * ALPHA_FAST;
    yMed  = yMed  * (1.0f - ALPHA_MED ) + input * ALPHA_MED;
    ySlow = ySlow * (1.0f - ALPHA_SLOW) + input * ALPHA_SLOW;

    dashSendPrec("input",    input, 2);
    dashSendPrec("ema_fast", yFast, 3);
    dashSendPrec("ema_med",  yMed,  3);
    dashSendPrec("ema_slow", ySlow, 3);

    dashFlush();
    TerminateTask();
}
