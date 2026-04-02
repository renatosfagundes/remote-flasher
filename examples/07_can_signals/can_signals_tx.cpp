// Example 07: CAN signal encoding with sequence counter (TX)
//
// Demonstrates the pattern used in automotive CAN (J1939):
//   1. Read a physical value (here simulated by POT1)
//   2. Apply scale conversion:  raw_value = physical_value / resolution
//   3. Pack into specific byte positions in the CAN frame
//   4. Add a sequence counter (byte 0) for stale detection
//   5. Send periodically
//
// Signal definition:
//   Message ID:  0x100 (standard frame)
//   Byte 0:      Sequence counter (0-255, wraps)
//   Bytes 1-2:   Temperature (resolution = 0.1 °C, offset = -40)
//                 raw = (temp_celsius + 40) / 0.1
//                 range: -40 to 215 °C
//   Bytes 3-4:   Pressure (resolution = 0.5 kPa)
//                 raw = pressure_kpa / 0.5
//                 range: 0 to 500 kPa
//
// Copy Board.h, VirtualIO.h, VirtualIO.cpp to this folder before building.

#include "tpl_os.h"
#include "Arduino.h"
#include "Board.h"
#include "VirtualIO.h"
#include <mcp_can.h>

#define MSG_ID     0x100
#define TEMP_RES   0.1     // °C per bit
#define TEMP_OFF   -40.0   // offset
#define PRESS_RES  0.5     // kPa per bit

MCP_CAN CAN1(CAN1_CS);
static byte seqCounter = 0;

void setup() {
    Serial.begin(115200);
    vioInit();
    while (CAN1.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
        delay(200);
    }
    CAN1.setMode(MCP_NORMAL);
    Serial.println("Ex07 TX: CAN signals with encoding");
    Serial.println("POT1=Temperature (-40~215C), POT2=Pressure (0~500kPa)");
}

TASK(SendSignal) {
    vioUpdate();

    // Map pots to physical values
    float temperature = (vAnalogRead(VPOT1) / 1023.0) * 255.0 + TEMP_OFF;  // -40 to 215
    float pressure    = (vAnalogRead(VPOT2) / 1023.0) * 500.0;              // 0 to 500

    // Encode: physical -> raw using resolution and offset
    unsigned int rawTemp  = (unsigned int)((temperature - TEMP_OFF) / TEMP_RES);
    unsigned int rawPress = (unsigned int)(pressure / PRESS_RES);

    // Pack into frame
    byte data[8] = {0};
    data[0] = seqCounter++;       // sequence counter
    data[1] = (rawTemp >> 8);     // temperature high byte
    data[2] = rawTemp & 0xFF;     // temperature low byte
    data[3] = (rawPress >> 8);    // pressure high byte
    data[4] = rawPress & 0xFF;    // pressure low byte

    CAN1.sendMsgBuf(MSG_ID, CAN_STDID, 5, data);

    Serial.print("TX: T=");
    Serial.print(temperature, 1);
    Serial.print("C P=");
    Serial.print(pressure, 1);
    Serial.print("kPa seq=");
    Serial.println(seqCounter - 1);

    TerminateTask();
}
