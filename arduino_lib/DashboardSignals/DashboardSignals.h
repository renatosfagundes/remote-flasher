/*
 * DashboardSignals.h — Named signal interface for Remote Flasher Dashboard & Plotter
 *
 * Sends named key:value pairs over Serial that the Remote Flasher app
 * auto-discovers and routes:
 *   - All signals appear in the Plotter tab for real-time graphing
 *   - Signals with recognized names automatically update the HMI Dashboard
 *
 * Serial format (one line per flush) — prefixed with '$' to mark the line
 * as a signal message (mirrors VIO's '!' convention):
 *   $speed:50.0,rpm:7200,coolantTemp:85.5,gear:8
 *
 * Lines without the '$' prefix are treated as normal Serial.print output
 * and don't show up in the Dashboard or Plotter.
 *
 * Dashboard-recognized signal names (case-insensitive matching):
 *
 *   Gauges:       speed, rpm, coolantTemp, fuelLevel, battery, power, rangeKm
 *   Gears:        gear (P=7,R=-1,N=0,D=8), manualGear (N=0,R=-1,1-6)
 *   Odometer:     distance, avgSpeed
 *   Doors:        doorFL, doorFR, doorRL, doorRR, trunk, hood
 *   Warnings:     checkEngine, oilPressure, batteryWarn, brakeWarn,
 *                 absWarn, airbagWarn
 *   Status:       parkingLights, lowBeam, highBeam, fogLights,
 *                 seatbeltUnbuckled, turnLeft, turnRight,
 *                 cruiseActive, ecoMode, evCharging
 *   Extra:        serviceDue, tirePressure, doorOpen, tractionControl
 *
 * Any other signal name will appear in the Plotter but won't affect the
 * Dashboard gauges — great for custom application-specific data.
 *
 * Usage with Trampoline RTOS:
 *
 *   #include "DashboardSignals.h"
 *
 *   void setup() {
 *     Serial.begin(115200);
 *     dashInit();
 *   }
 *
 *   TASK(SendData) {
 *     // Buffer signals, then flush once per cycle:
 *     dashSend("speed", vehicleSpeed);
 *     dashSend("rpm", engineRPM);
 *     dashSendInt("gear", currentGear);
 *     dashSendBool("checkEngine", engineFault);
 *     dashFlush();
 *     TerminateTask();
 *   }
 *
 * IMPORTANT:
 *   - Call dashFlush() once per task cycle (not per signal)
 *   - The flush sends one CSV line with all buffered signals
 *   - Max 32 signals per flush (increase DASH_MAX_SIGNALS if needed)
 *   - Don't call Serial.print() for data lines between dashSend/dashFlush
 *     (VirtualIO commands with ! prefix are fine — they're filtered out)
 */

#ifndef DASHBOARD_SIGNALS_H
#define DASHBOARD_SIGNALS_H

#include <Arduino.h>

// Maximum number of signals per flush line.
// Sized to fit example 13 (IndicatorTask sends 15 signals per flush)
// inside the ATmega328p's 2 KB RAM alongside a 256-byte EngineTask
// stack + kernel + Arduino Serial buffers. Bump cautiously and
// watch the .bss size in `avr-size` output — each extra slot costs
// DASH_MAX_NAME_LEN + ~10 bytes.
#define DASH_MAX_SIGNALS 16

// Maximum signal name length (including NUL terminator). Longest
// name currently in use is 17 chars ("seatbeltUnbuckled"), so 18
// fits exactly — any longer name would be truncated by strncpy in
// _addEntry and break Plotter/Dashboard routing by name.
#define DASH_MAX_NAME_LEN 18

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Initialize the dashboard signals system.
 * Call once in setup() after Serial.begin().
 */
void dashInit(void);

/*
 * Buffer a float signal for the next flush.
 *   name:     signal name (e.g., "speed", "rpm", "myCustomValue")
 *   value:    float value
 *   decimals: decimal places (default 1)
 */
void dashSend(const char* name, float value);
void dashSendPrec(const char* name, float value, uint8_t decimals);

/*
 * Buffer an integer signal for the next flush.
 *   name:  signal name
 *   value: integer value
 */
void dashSendInt(const char* name, int value);

/*
 * Buffer a boolean signal for the next flush.
 *   name:  signal name (e.g., "checkEngine", "turnLeft")
 *   value: true/false (sent as 1/0)
 */
void dashSendBool(const char* name, bool value);

/*
 * Send all buffered signals as a single CSV line and reset the buffer.
 * Call once at the end of each task cycle.
 *
 * Output example: speed:50.0,rpm:7200,gear:8,checkEngine:0
 */
void dashFlush(void);

/*
 * Get the number of signals currently buffered (since last flush).
 * Useful for debugging.
 */
uint8_t dashBufferCount(void);

#ifdef __cplusplus
}
#endif

#endif /* DASHBOARD_SIGNALS_H */
