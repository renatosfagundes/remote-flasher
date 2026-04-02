// Example 07: CAN signal decoding with stale detection (RX)
//
// Receives the CAN frame from can_signals_tx, decodes:
//   Byte 0:    Sequence counter — if unchanged, buffer is stale
//   Bytes 1-2: Temperature raw -> physical = raw * 0.1 + (-40)
//   Bytes 3-4: Pressure raw    -> physical = raw * 0.5
//
// Shows decoded values on serial and Virtual LEDs.
// Detects connection loss via sequence counter timeout.

#include "tpl_os.h"
#include "Arduino.h"
#include "Board.h"
#include "VirtualIO.h"
#include <mcp_can.h>

#define MSG_ID     0x100
#define TEMP_RES   0.1
#define TEMP_OFF   -40.0
#define PRESS_RES  0.5
#define STALE_TIMEOUT 20  // 20 cycles * 100ms = 2 seconds

MCP_CAN CAN1(CAN1_CS);

static volatile float temperature = 0;
static volatile float pressure = 0;
static volatile bool dataReceived = false;
static volatile byte lastSeq = 0xFF;
static volatile int staleCount = STALE_TIMEOUT;

void setup() {
    Serial.begin(115200);
    vioInit();
    pinMode(CAN_INT, INPUT);
    while (CAN1.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
        delay(200);
    }
    CAN1.setMode(MCP_NORMAL);
    Serial.println("Ex07 RX: CAN signal decoding");
}

TASK(RecvSignal) {
    vioUpdate();
    bool gotNew = false;

    while (!digitalRead(CAN_INT)) {
        unsigned char dlc = 0;
        unsigned char data[8];
        long unsigned int id;
        CAN1.readMsgBuf(&id, &dlc, data);

        if ((id & 0x7FF) == MSG_ID && dlc >= 5) {
            byte seq = data[0];
            if (seq != lastSeq) {  // new message (sequence changed)
                lastSeq = seq;
                staleCount = 0;
                gotNew = true;

                // Decode: raw -> physical using resolution and offset
                unsigned int rawTemp  = ((unsigned int)data[1] << 8) | data[2];
                unsigned int rawPress = ((unsigned int)data[3] << 8) | data[4];
                temperature = rawTemp * TEMP_RES + TEMP_OFF;
                pressure    = rawPress * PRESS_RES;
                dataReceived = true;
            }
        }
    }

    if (staleCount < STALE_TIMEOUT) staleCount++;

    // Virtual LEDs
    if (staleCount >= STALE_TIMEOUT) {
        // Connection lost
        vLedWrite(VLED1, 0);
        vLedWrite(VLED2, 0);
        vLedWrite(VLED3, 0);
        vLedWrite(VLED4, (staleCount % 10 < 5) ? 80 : 0);  // blink L4
    } else {
        // L1: temperature (blue=cold, red=hot, mapped -40~215 to 0~255)
        vLedWrite(VLED1, min(255, (int)((temperature + 40) * 1.0)));
        // L2: pressure (0~500 mapped to 0~255)
        vLedWrite(VLED2, min(255, (int)(pressure * 0.51)));
        // L3: green = active
        vLedWrite(VLED3, gotNew ? 255 : 0);
        vLedWrite(VLED4, 0);
    }

    TerminateTask();
}

TASK(PrintValues) {
    if (staleCount >= STALE_TIMEOUT) {
        Serial.println("Waiting for data...");
    } else {
        Serial.print("T=");
        Serial.print(temperature, 1);
        Serial.print("C, P=");
        Serial.print(pressure, 1);
        Serial.println(" kPa");
    }
    TerminateTask();
}
