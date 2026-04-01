// Example 04: Producer-Consumer with OSEK Resource
// Producer adds to buffer every 500ms, Consumer removes every 600ms.
// Buffer size = 10. GetResource/ReleaseResource protect shared access.
#include "tpl_os.h"
#include "Arduino.h"

#define BUFFER_SIZE 10

static volatile int buffer = 0;  // current buffer count (0 to BUFFER_SIZE)

void setup() {
    Serial.begin(115200);
    Serial.println("Example 04: Producer-Consumer started.");
    Serial.println("Producer=500ms, Consumer=600ms, Buffer=10");
}

TASK(Producer) {
    GetResource(bufferRes);

    if (buffer < BUFFER_SIZE) {
        buffer++;
        Serial.print("[PROD] Produced. Buffer=");
        Serial.println(buffer);
    } else {
        Serial.print("[PROD] Buffer FULL! Buffer=");
        Serial.println(buffer);
    }

    ReleaseResource(bufferRes);
    TerminateTask();
}

TASK(Consumer) {
    GetResource(bufferRes);

    if (buffer > 0) {
        buffer--;
        Serial.print("[CONS] Consumed. Buffer=");
        Serial.println(buffer);
    } else {
        Serial.print("[CONS] Buffer EMPTY! Buffer=");
        Serial.println(buffer);
    }

    ReleaseResource(bufferRes);
    TerminateTask();
}
