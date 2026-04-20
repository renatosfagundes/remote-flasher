// Example 14: Odometer & Average Speed Test
//
// Focused firmware for verifying the `distance` and `avgSpeed` signals
// on the Remote Flasher HMI.
//
//   - `distance` drives the 7-seg odometer strip on every speed gauge
//     (Combustion Auto/Manual + Electric modes).
//   - `avgSpeed` drives the "Avg" readout in the Electric mode info column.
//
// Speed is held in step plateaus (not a sinewave) so:
//   - avgSpeed visibly LAGS the current speed (EMA smoothing),
//     proving the HMI is plotting avgSpeed and not a copy of speed.
//   - distance accumulates at a constant rate on each plateau — easy to
//     eyeball against the expected km/h × elapsed-time.
//
// `TIME_SCALE` > 1 compresses simulated time so the odometer ticks over
// fast enough to see during a short test run. Set to 1.0 for realistic.
//
// Wire-up: flash, open Serial @ 115200, enable "Feed Dashboard".

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"

// Task period — must match gaugeAlarm CYCLETIME in the .oil file.
static const float DT_SEC = 0.05f;  // 20 Hz

// Speed plateau sequence (km/h). Each value is held for PLATEAU_SECS.
static const float SPEED_PLATEAUS[] = { 0, 60, 120, 60, 0, 90, 150, 90 };
static const int   PLATEAU_COUNT    = sizeof(SPEED_PLATEAUS) / sizeof(float);
static const float PLATEAU_SECS     = 5.0f;

// EMA smoothing for avgSpeed. τ ≈ DT_SEC / ALPHA ≈ 2.5 s at alpha=0.02.
static const float AVG_ALPHA = 0.02f;

// Simulated time compression so the odometer ticks visibly.
// 1.0  = realistic (≈30 s of real time per km at 120 km/h)
// 10.0 = brisk test pace (≈3 s of real time per km at 120 km/h)
static const float TIME_SCALE = 10.0f;

static float tSec   = 0;     // real elapsed seconds
static float avgSpd = 0;     // EMA of speed
static float distKm = 12450.0f;  // start non-zero to exercise all 6 digits

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Odo/AvgSpd Test] distance + avgSpeed");
}

TASK(SendGauges) {
    tSec += DT_SEC;

    int idx = ((int)(tSec / PLATEAU_SECS)) % PLATEAU_COUNT;
    float speed = SPEED_PLATEAUS[idx];

    avgSpd = avgSpd * (1.0f - AVG_ALPHA) + speed * AVG_ALPHA;

    // km travelled this tick = speed[km/h] × dt[s] / 3600, scaled.
    distKm += speed * DT_SEC * TIME_SCALE / 3600.0f;

    dashSend("speed", speed);
    dashSend("avgSpeed", avgSpd);
    dashSendPrec("distance", distKm, 0);

    dashFlush();
    TerminateTask();
}
