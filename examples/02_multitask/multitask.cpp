// Example 02: Multiple tasks — different priorities and periods
// Task1: 500ms, priority 5 (lowest)
// Task2: 750ms, priority 10
// Task3: 1200ms, priority 15 (highest) — preempts the others
#include "tpl_os.h"
#include "Arduino.h"

static unsigned long count1 = 0, count2 = 0, count3 = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("Example 02: Multitask started.");
    Serial.println("T1=500ms/p5, T2=750ms/p10, T3=1200ms/p15");
}

TASK(Task1) {
    count1++;
    Serial.print("[T1] count=");
    Serial.println(count1);
    TerminateTask();
}

TASK(Task2) {
    count2++;
    Serial.print("[T2] count=");
    Serial.println(count2);
    TerminateTask();
}

TASK(Task3) {
    count3++;
    Serial.print("[T3] count=");
    Serial.print(count3);
    Serial.print(" | T1=");
    Serial.print(count1);
    Serial.print(" T2=");
    Serial.print(count2);
    Serial.print(" T3=");
    Serial.println(count3);
    TerminateTask();
}
