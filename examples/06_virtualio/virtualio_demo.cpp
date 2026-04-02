// Example 06: VirtualIO demo
// Shows how to use all Virtual I/O features from the Remote Flasher GUI:
//   - Read buttons:  vRead(VBTN1) .. vRead(VBTN4)
//   - Read pots:     vAnalogRead(VPOT1), vAnalogRead(VPOT2)
//   - Control LEDs:  vLedWrite(VLED1, brightness) .. vLedWrite(VLED4, brightness)
//
// Behavior:
//   BTN1 -> LED1 (on/off)
//   BTN2 -> LED2 (on/off)
//   POT1 -> LED3 (brightness 0-255)
//   POT2 -> LED4 (brightness 0-255)
//   BTN3 -> prints "Hello!" to serial
//   BTN4 -> resets all LEDs

#include "tpl_os.h"
#include "Arduino.h"
#include "VirtualIO.h"

void setup() {
    Serial.begin(115200);
    vioInit();
    Serial.println("Example 06: VirtualIO demo");
    Serial.println("BTN1/2=LEDs, POT1/2=brightness, BTN3=msg, BTN4=reset");
}

TASK(ReadInputs) {
    vioUpdate();

    // Buttons -> LEDs (on/off)
    vLedWrite(VLED1, vRead(VBTN1) ? 255 : 0);
    vLedWrite(VLED2, vRead(VBTN2) ? 255 : 0);

    // Pots -> LEDs (brightness)
    vLedWrite(VLED3, vAnalogRead(VPOT1) / 4);  // 0-1023 -> 0-255
    vLedWrite(VLED4, vAnalogRead(VPOT2) / 4);

    // BTN3: print a message
    if (vRead(VBTN3)) {
        Serial.println("Hello from VirtualIO!");
    }

    // BTN4: reset all LEDs
    if (vRead(VBTN4)) {
        vLedWrite(VLED1, 0);
        vLedWrite(VLED2, 0);
        vLedWrite(VLED3, 0);
        vLedWrite(VLED4, 0);
    }

    // Print current state
    Serial.print("B1="); Serial.print(vRead(VBTN1));
    Serial.print(" B2="); Serial.print(vRead(VBTN2));
    Serial.print(" P1="); Serial.print(vAnalogRead(VPOT1));
    Serial.print(" P2="); Serial.println(vAnalogRead(VPOT2));

    TerminateTask();
}
