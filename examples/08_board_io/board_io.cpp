// Example 08: Board I/O — physical buttons, potentiometers, and LEDs
//
// Pin definitions come from Board.h (ANEB v1.1 evaluation board).
// This example shows how to read and write physical pins for ECU1.
// Adapt the ECU number (ECU1, ECU2, ECU3, ECU4) for your board.
//
// ECU1 pins used:
//   Inputs:  ECU1_DIN1..DIN4 (pushbuttons), ECU1_AIN1..AIN4 (potentiometers)
//   Outputs: ECU1_DOUT1, ECU1_DOUT2 (LEDs), ECU1_BUZZER
//
// Behavior:
//   DIN1 pressed -> DOUT1 on
//   DIN2 pressed -> DOUT2 on
//   AIN1 value   -> printed to serial
//   DIN3 pressed -> BUZZER on

#include "tpl_os.h"
#include "Arduino.h"
#include "Board.h"

void setup() {
    Serial.begin(115200);

    // Configure digital inputs (pushbuttons)
    pinMode(ECU1_DIN1, INPUT);
    pinMode(ECU1_DIN2, INPUT);
    pinMode(ECU1_DIN3, INPUT);
    pinMode(ECU1_DIN4, INPUT);

    // Configure digital outputs (LEDs + buzzer)
    pinMode(ECU1_DOUT1, OUTPUT);
    pinMode(ECU1_DOUT2, OUTPUT);
    pinMode(ECU1_BUZZER, OUTPUT);

    // Analog inputs don't need pinMode

    Serial.println("Example 08: Board I/O (ECU1)");
    Serial.println("DIN1->LED1, DIN2->LED2, DIN3->BUZZ, AIN1->serial");
}

TASK(ReadIO) {
    // Read digital inputs (pushbuttons)
    bool btn1 = digitalRead(ECU1_DIN1);
    bool btn2 = digitalRead(ECU1_DIN2);
    bool btn3 = digitalRead(ECU1_DIN3);
    bool btn4 = digitalRead(ECU1_DIN4);

    // Read analog input (potentiometer, 0-1023)
    int pot1 = analogRead(ECU1_AIN1);

    // Control outputs based on inputs
    digitalWrite(ECU1_DOUT1, btn1 ? HIGH : LOW);
    digitalWrite(ECU1_DOUT2, btn2 ? HIGH : LOW);
    digitalWrite(ECU1_BUZZER, btn3 ? HIGH : LOW);

    // Print state
    Serial.print("DIN: ");
    Serial.print(btn1); Serial.print(btn2);
    Serial.print(btn3); Serial.print(btn4);
    Serial.print("  AIN1=");
    Serial.print(pot1);
    Serial.print("  OUT: D1=");
    Serial.print(btn1);
    Serial.print(" D2=");
    Serial.print(btn2);
    Serial.print(" BUZ=");
    Serial.println(btn3);

    TerminateTask();
}
