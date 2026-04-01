// Example 03: Dynamic alarm period
// Period increases from 1s to 5s every 5 executions, then decreases back.
// Demonstrates SetRelAlarm() and CancelAlarm() API.
#include "tpl_os.h"
#include "Arduino.h"

static unsigned long totalExec = 0;
static unsigned long consecExec = 0;
static int currentPeriod = 1000;  // ms
static bool increasing = true;

void setup() {
    Serial.begin(115200);
    Serial.println("Example 03: Dynamic Alarm started.");
}

TASK(DynamicTask) {
    totalExec++;
    consecExec++;

    Serial.print("Total=");
    Serial.print(totalExec);
    Serial.print(" Consec=");
    Serial.print(consecExec);
    Serial.print(" Period=");
    Serial.print(currentPeriod);
    Serial.println("ms");

    // Every 5 consecutive executions, change the period
    if (consecExec >= 5) {
        consecExec = 0;

        if (increasing) {
            currentPeriod += 1000;
            if (currentPeriod >= 5000) increasing = false;
        } else {
            currentPeriod -= 1000;
            if (currentPeriod <= 1000) increasing = true;
        }

        // Cancel current alarm and set new period
        CancelAlarm(dynAlarm);
        SetRelAlarm(dynAlarm, currentPeriod, currentPeriod);

        Serial.print(">> Period changed to ");
        Serial.print(currentPeriod);
        Serial.println("ms");
    }

    TerminateTask();
}
