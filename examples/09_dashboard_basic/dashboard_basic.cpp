// Example 09: Dashboard Basic — Send speed and RPM to the dashboard
//
// Simplest dashboard example: two signals that drive the speed gauge
// and RPM gauge in the HMI Dashboard tab.
//
// What you'll see:
//   - Speed gauge oscillates 0-200 km/h
//   - RPM gauge oscillates 1000-7000
//   - Both signals appear in the Plotter tab as real-time graphs
//
// Setup: Flash this firmware, open Serial, check "Feed Dashboard",
//        then switch to the Dashboard or Plotter tab.

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"

static float t = 0;

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Dashboard Basic] Speed + RPM demo");
}

TASK(SendDashboard) {
    t += 0.05;

    float speed = 100.0 + 100.0 * sin(t * 0.5);
    float rpm   = 4000.0 + 3000.0 * sin(t * 0.8);

    dashSend("speed", speed);
    dashSend("rpm", rpm);
    dashFlush();

    TerminateTask();
}
