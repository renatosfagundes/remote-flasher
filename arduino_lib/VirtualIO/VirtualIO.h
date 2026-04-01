/*
 * VirtualIO.h — Virtual I/O for Remote Firmware Flasher
 *
 * Bidirectional virtual hardware:
 *   Inputs  (GUI -> Arduino): buttons and potentiometers
 *   Outputs (Arduino -> GUI): LEDs
 *
 * Protocol (GUI -> Arduino):
 *   !B1:1   — Virtual button 1 pressed
 *   !B1:0   — Virtual button 1 released
 *   !P1:512 — Virtual potentiometer 1 set to 512 (range 0-1023)
 *
 * Protocol (Arduino -> GUI):
 *   !L1:1   — Virtual LED 1 on
 *   !L1:0   — Virtual LED 1 off
 *   !L1:128 — Virtual LED 1 brightness (0-255)
 *
 * Usage in Trampoline RTOS:
 *   #include "VirtualIO.h"
 *
 *   void setup() {
 *     Serial.begin(115200);
 *     vioInit();
 *   }
 *
 *   TASK(MyTask) {
 *     vioUpdate();
 *     if (vRead(VBTN1)) {
 *       vLedWrite(VLED1, 255);   // turn on LED 1 in the GUI
 *     } else {
 *       vLedWrite(VLED1, 0);     // turn off LED 1
 *     }
 *     int val = vAnalogRead(VPOT1);
 *     vLedWrite(VLED2, val / 4); // LED 2 brightness from POT1
 *   }
 */

#ifndef VIRTUAL_IO_H
#define VIRTUAL_IO_H

#include <Arduino.h>

// Virtual pin identifiers — Inputs
#define VBTN1  0
#define VBTN2  1
#define VBTN3  2
#define VBTN4  3
#define VPOT1  0
#define VPOT2  1

// Virtual pin identifiers — Outputs
#define VLED1  0
#define VLED2  1
#define VLED3  2
#define VLED4  3

// Counts
#define VIO_NUM_BUTTONS 4
#define VIO_NUM_POTS    2
#define VIO_NUM_LEDS    4

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Initialize the Virtual I/O system.
 * Call once in setup() after Serial.begin().
 */
void vioInit(void);

/*
 * Parse any pending serial commands.
 * Call at the beginning of tasks that use virtual inputs.
 * Lightweight — returns immediately if no data is available.
 */
void vioUpdate(void);

/*
 * Read a virtual button state.
 *   btn: VBTN1..VBTN4
 *   Returns: 1 if pressed, 0 if released
 */
uint8_t vRead(uint8_t btn);

/*
 * Read a virtual potentiometer value.
 *   pot: VPOT1 or VPOT2
 *   Returns: 0-1023
 */
int vAnalogRead(uint8_t pot);

/*
 * Set a virtual LED brightness (sent to GUI).
 *   led: VLED1..VLED4
 *   brightness: 0 (off) to 255 (full)
 *
 * The GUI updates the corresponding LED indicator in real time.
 * Only sends a serial command when the value actually changes.
 */
void vLedWrite(uint8_t led, uint8_t brightness);

#ifdef __cplusplus
}
#endif

#endif /* VIRTUAL_IO_H */
