// Example 12: Dashboard Doors — Door status + hood/trunk with VirtualIO control
//
// Combines DashboardSignals with VirtualIO: use the virtual buttons
// to open/close doors, and see them on the dashboard's DoorStatus widget.
//
//   BTN1 -> Toggle front-left door
//   BTN2 -> Toggle front-right door
//   BTN3 -> Toggle hood
//   BTN4 -> Toggle trunk
//   POT1 -> Speed (0-200, shown on dashboard speed gauge)
//   POT2 -> RPM (0-8000, shown on dashboard RPM gauge)
//
// This demonstrates how VirtualIO and DashboardSignals work together —
// buttons provide interactive input, dashboard shows the result.

#include "tpl_os.h"
#include "Arduino.h"
#include "VirtualIO.h"
#include "DashboardSignals.h"

static bool doorFL = false, doorFR = false;
static bool hoodOpen = false, trunkOpen = false;
static bool prevB1 = false, prevB2 = false, prevB3 = false, prevB4 = false;

void setup() {
    Serial.begin(115200);
    vioInit();
    dashInit();
    Serial.println("[Dashboard Doors] BTN1-4=doors/hood/trunk, POT1=speed, POT2=rpm");
}

TASK(UpdateIO) {
    vioUpdate();

    // Toggle doors on button press (edge detection)
    bool b1 = vRead(VBTN1);
    bool b2 = vRead(VBTN2);
    bool b3 = vRead(VBTN3);
    bool b4 = vRead(VBTN4);

    if (b1 && !prevB1) doorFL = !doorFL;
    if (b2 && !prevB2) doorFR = !doorFR;
    if (b3 && !prevB3) hoodOpen = !hoodOpen;
    if (b4 && !prevB4) trunkOpen = !trunkOpen;

    prevB1 = b1; prevB2 = b2; prevB3 = b3; prevB4 = b4;

    // LEDs reflect door state
    vLedWrite(VLED1, doorFL ? 255 : 0);
    vLedWrite(VLED2, doorFR ? 255 : 0);
    vLedWrite(VLED3, hoodOpen ? 255 : 0);
    vLedWrite(VLED4, trunkOpen ? 255 : 0);

    // Speed and RPM from potentiometers
    float speed = vAnalogRead(VPOT1) * 200.0 / 1023.0;
    float rpm   = vAnalogRead(VPOT2) * 8000.0 / 1023.0;

    // Send everything to dashboard
    dashSend("speed", speed);
    dashSend("rpm", rpm);
    dashSendBool("doorFL", doorFL);
    dashSendBool("doorFR", doorFR);
    dashSendBool("doorRL", false);
    dashSendBool("doorRR", false);
    dashSendBool("hood", hoodOpen);
    dashSendBool("trunk", trunkOpen);

    // Door warning on if any door is open
    dashSendBool("doorOpen", doorFL || doorFR || hoodOpen || trunkOpen);

    dashFlush();
    TerminateTask();
}
