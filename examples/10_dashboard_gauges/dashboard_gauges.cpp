// Example 10: Dashboard Gauges — All gauge signals + gear + odometer
//
// Exercises every gauge in the dashboard:
//   - Speed, RPM, coolant temperature, fuel level
//   - Battery percentage, power (kW), range
//   - Gear selector (P/R/N/D for auto, 1-6/R/N for manual)
//   - Distance (odometer) and average speed
//
// Each signal uses a different waveform so you can identify them
// in the Plotter: sine, triangle, ramp, etc.

#include "tpl_os.h"
#include "Arduino.h"
#include "DashboardSignals.h"

static float t = 0;
static float distance = 12450.0;

// Auto gear sequence: mostly D, occasionally others
const int autoGears[] = {8, 8, 8, 7, -1, 0, 8, 8};
const int autoGearCount = 8;

void setup() {
    Serial.begin(115200);
    dashInit();
    Serial.println("[Dashboard Gauges] All gauges demo");
}

TASK(SendGauges) {
    t += 0.05;

    // Speed: sine wave 0-200
    float speed = 100.0 + 100.0 * sin(t * 0.5);
    dashSend("speed", speed);

    // RPM: sine wave 1000-7000 (slightly faster than speed)
    dashSend("rpm", 4000.0 + 3000.0 * sin(t * 0.8));

    // Coolant temp: slow oscillation 70-110
    dashSend("coolantTemp", 90.0 + 20.0 * sin(t * 0.15));

    // Fuel: slow decay 100->10, resets
    dashSend("fuelLevel", 100.0 - 90.0 * (fmod(t, 60.0) / 60.0));

    // Battery: triangle wave 20-100
    float bp = fmod(t / 25.0, 1.0);
    float battery = (bp < 0.5) ? 20.0 + 160.0 * bp : 180.0 - 160.0 * bp;
    dashSend("battery", battery);

    // Power: sine -50 to +150 (regen to full power)
    dashSend("power", 50.0 + 100.0 * sin(t * 0.6));

    // Range: tracks battery
    dashSendPrec("rangeKm", battery * 5.0, 0);

    // Distance: slowly increases based on speed
    distance += max(0.0f, speed) / 3600.0;
    dashSendPrec("distance", distance, 0);

    // Average speed: EMA of current speed
    static float avgSpeed = 0;
    avgSpeed = avgSpeed * 0.99 + speed * 0.01;
    dashSend("avgSpeed", avgSpeed);

    // Gear: cycle through auto sequence every 4 seconds
    dashSendInt("gear", autoGears[(int)(t / 4.0) % autoGearCount]);

    dashFlush();
    TerminateTask();
}
