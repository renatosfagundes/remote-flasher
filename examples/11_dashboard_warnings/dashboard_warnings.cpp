// Example 11: Dashboard Warnings — Warning lights, status indicators, turn signals
//
// Demonstrates all boolean indicators on the dashboard:
//   - Warning icons: engine, oil, battery, brake, ABS, airbag
//   - Status lights: parking, low beam, high beam, fog, seatbelt
//   - Turn signals: left/right blinking
//   - Extra: cruise, eco, charging, service, tire pressure, traction
//
// Each warning toggles at a different rate so you can see them
// independently. Turn signals alternate left/right with realistic
// 1.5 Hz blink.

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"

static float t = 0;

// Toggle: on for `period` seconds, off for `period` seconds
bool toggle(float t, float period) {
    return fmod(t, period * 2.0) < period;
}

// Turn signal blink: on-phase with 1.5 Hz blink
bool blink(float t, float onDur, float offset) {
    float cycle = fmod(t + offset, onDur * 2.0);
    if (cycle > onDur) return false;
    return sin(t * 3.0 * 2.0 * PI) > 0;
}

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Dashboard Warnings] All warning indicators demo");
}

TASK(SendWarnings) {
    t += 0.05;

    // Send a base speed so the dashboard doesn't look empty
    dashSend("speed", 60.0 + 30.0 * sin(t * 0.3));
    dashSend("rpm", 2500.0 + 1000.0 * sin(t * 0.4));

    // === Warning lights (each at a different toggle rate) ===
    dashSendBool("checkEngine",  toggle(t, 5.0));
    dashSendBool("oilPressure",  toggle(t, 7.0));
    dashSendBool("batteryWarn",  toggle(t, 9.0));
    dashSendBool("brakeWarn",    toggle(t, 6.0));
    dashSendBool("absWarn",      toggle(t, 8.0));
    dashSendBool("airbagWarn",   toggle(t, 11.0));

    // === Status lights ===
    dashSendBool("parkingLights",     toggle(t, 4.0));
    dashSendBool("lowBeam",           toggle(t, 5.5));
    dashSendBool("highBeam",          toggle(t, 8.5));
    dashSendBool("fogLights",         toggle(t, 10.0));
    dashSendBool("seatbeltUnbuckled", toggle(t, 12.0));

    // === Turn signals (alternate left/right, 6s each) ===
    dashSendBool("turnLeft",  blink(t, 6.0, 0.0));
    dashSendBool("turnRight", blink(t, 6.0, 6.0));

    // === Extra indicators ===
    dashSendBool("cruiseActive",    toggle(t, 7.5));
    dashSendBool("ecoMode",         toggle(t, 13.0));
    dashSendBool("evCharging",      toggle(t, 15.0));
    dashSendBool("serviceDue",      toggle(t, 16.0));
    dashSendBool("tirePressure",    toggle(t, 14.0));
    dashSendBool("tractionControl", toggle(t, 9.5));

    dashFlush();
    TerminateTask();
}
