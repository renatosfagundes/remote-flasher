// Example 13: Dashboard Full — Multi-task vehicle simulation
//
// Complete vehicle simulation using 3 RTOS tasks at different rates:
//   - EngineTask (20 Hz): speed, RPM, coolant, fuel, power, battery
//   - IndicatorTask (5 Hz): warnings, status lights, turn signals
//   - DoorTask (2 Hz): door states, hood, trunk
//
// This shows the recommended architecture for a complex dashboard
// application: separate tasks for different subsystems, all feeding
// into a single dashFlush() per task cycle.
//
// Custom signals (not dashboard properties) are included to
// demonstrate the plotter's auto-discovery:
//   - "throttle": simulated throttle position (0-100%)
//   - "brakeForce": simulated brake pressure (0-100%)
//   - "steeringAngle": simulated steering (-45 to +45 degrees)

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"

// Shared state (protected by RESOURCE in a real application)
static float g_speed = 0, g_rpm = 0, g_battery = 71;
static float g_throttle = 0;
static float t_engine = 0, t_ind = 0, t_door = 0;

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Dashboard Full] Multi-task vehicle simulation");
}

// === Engine task: fast (20 Hz) — gauges and analog values ===
TASK(EngineTask) {
    t_engine += 0.2;  // 200 ms per tick (5 Hz) — matches engineAlarm CYCLETIME

    // Simulate driving: throttle varies, speed follows
    g_throttle = 50.0 + 40.0 * sin(t_engine * 0.3);
    g_speed = g_speed * 0.95 + (g_throttle * 2.0) * 0.05;
    g_rpm = 800 + g_speed * 30.0 + 500.0 * sin(t_engine * 2.0);
    float coolant = 85.0 + 15.0 * sin(t_engine * 0.1);
    float fuel = 100.0 - 90.0 * (fmod(t_engine, 120.0) / 120.0);
    float power = g_throttle * 1.5 - 20.0;

    // Battery: slow triangle wave
    float bp = fmod(t_engine / 30.0, 1.0);
    g_battery = (bp < 0.5) ? 30 + 140 * bp : 170 - 140 * bp;

    dashSend("speed", g_speed);
    dashSend("rpm", g_rpm);
    dashSend("coolantTemp", coolant);
    dashSend("fuelLevel", fuel);
    dashSend("battery", g_battery);
    dashSend("power", power);
    dashSendPrec("rangeKm", g_battery * 4.5, 0);
    dashSendInt("gear", 8);  // D

    // Custom plotter-only signals
    dashSend("throttle", g_throttle);
    dashSend("brakeForce", max(0.0f, 50.0f - g_throttle));
    dashSend("steeringAngle", 30.0 * sin(t_engine * 0.15));

    dashFlush();
    TerminateTask();
}

// === Indicator task: medium (5 Hz) — warnings and status lights ===
TASK(IndicatorTask) {
    t_ind += 0.2;

    // Turn signals: alternate left/right every 6 seconds with blink
    float turnCycle = fmod(t_ind, 24.0);
    bool leftPhase = turnCycle < 6.0;
    bool rightPhase = turnCycle >= 12.0 && turnCycle < 18.0;
    bool blinkOn = sin(t_ind * 3.0 * 2.0 * PI) > 0;

    dashSendBool("turnLeft",  leftPhase && blinkOn);
    dashSendBool("turnRight", rightPhase && blinkOn);

    // Warnings: context-dependent
    dashSendBool("checkEngine",  fmod(t_ind, 40.0) < 5.0);  // occasional fault
    dashSendBool("batteryWarn",  g_battery < 35.0);
    dashSendBool("brakeWarn",    false);
    dashSendBool("absWarn",      g_speed > 150.0);
    dashSendBool("oilPressure",  fmod(t_ind, 50.0) < 3.0);
    dashSendBool("airbagWarn",   false);

    // Status lights
    dashSendBool("parkingLights", true);
    dashSendBool("lowBeam",       true);
    dashSendBool("highBeam",      g_speed > 100.0);
    dashSendBool("fogLights",     false);
    dashSendBool("seatbeltUnbuckled", fmod(t_ind, 30.0) < 10.0);
    dashSendBool("cruiseActive",  g_speed > 80.0 && g_speed < 130.0);
    dashSendBool("ecoMode",       g_rpm < 3000.0);

    dashFlush();
    TerminateTask();
}

// === Door task: slow (2 Hz) — doors, hood, trunk ===
TASK(DoorTask) {
    t_door += 0.5;

    // Simulate: doors occasionally open when speed is 0
    bool stopped = g_speed < 2.0;

    dashSendBool("doorFL", stopped && fmod(t_door, 20.0) < 5.0);
    dashSendBool("doorFR", stopped && fmod(t_door, 25.0) < 3.0);
    dashSendBool("doorRL", false);
    dashSendBool("doorRR", false);
    dashSendBool("hood",   stopped && fmod(t_door, 40.0) < 4.0);
    dashSendBool("trunk",  stopped && fmod(t_door, 30.0) < 3.0);

    dashFlush();
    TerminateTask();
}
