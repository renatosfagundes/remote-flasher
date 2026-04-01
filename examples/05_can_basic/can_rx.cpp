// Example 05: Basic CAN RX — receives and prints CAN messages
// Flash on ECU2 (e.g. COM26). Pair with can_tx on ECU1 (COM25).
#include "tpl_os.h"
#include "Arduino.h"
#include "Board.h"
#include <mcp_can.h>

MCP_CAN CAN1(CAN1_CS);

void setup() {
    Serial.begin(115200);
    pinMode(CAN_INT, INPUT);
    while (CAN1.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
        delay(200);
    }
    CAN1.setMode(MCP_NORMAL);
    Serial.println("Example 05: CAN RX started. Waiting...");
    Serial.println("ID\tDLC\tData");
}

TASK(RecvFrame) {
    if (!digitalRead(CAN_INT)) {
        unsigned char dlc = 0;
        unsigned char data[8];
        long unsigned int id;

        CAN1.readMsgBuf(&id, &dlc, data);

        // Print ID
        Serial.print("0x");
        Serial.print(id & 0x1FFFFFFF, HEX);
        Serial.print("\t[");
        Serial.print(dlc);
        Serial.print("]\t");

        // Print data bytes
        for (byte i = 0; i < dlc; i++) {
            if (data[i] < 0x10) Serial.print("0");
            Serial.print(data[i], HEX);
            Serial.print(" ");
        }
        Serial.println();
    }
    TerminateTask();
}
