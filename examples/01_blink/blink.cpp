// Example 01: Blink — toggle LED with RTOS alarm
#include "tpl_os.h"
#include "Arduino.h"

static bool ledState = false;

void setup() {
    Serial.begin(115200);
    pinMode(LED_BUILTIN, OUTPUT);
    Serial.println("Example 01: Blink started.");
}

TASK(BlinkTask) {
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
    Serial.println(ledState ? "LED ON" : "LED OFF");
    TerminateTask();
}
