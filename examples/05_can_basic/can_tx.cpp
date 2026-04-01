// Example 05: Basic CAN TX — sends a counter every 500ms
// Flash on ECU1 (e.g. COM25). Pair with can_rx on ECU2 (COM26).
#include "tpl_os.h"
#include "Arduino.h"
#include "Board.h"
#include <mcp_can.h>

#define MSG_ID 0x100
MCP_CAN CAN1(CAN1_CS);
static unsigned long counter = 0;

void setup() {
    Serial.begin(115200);
    while (CAN1.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) != CAN_OK) {
        delay(200);
    }
    CAN1.setMode(MCP_NORMAL);
    Serial.println("Example 05: CAN TX started. ID=0x100");
}

TASK(SendFrame) {
    counter++;
    byte data[8] = {0};
    data[0] = (counter >> 24) & 0xFF;
    data[1] = (counter >> 16) & 0xFF;
    data[2] = (counter >> 8) & 0xFF;
    data[3] = counter & 0xFF;

    byte ret = CAN1.sendMsgBuf(MSG_ID, CAN_STDID, 4, data);
    Serial.print("TX #");
    Serial.print(counter);
    Serial.println(ret == CAN_OK ? " OK" : " ERR");
    TerminateTask();
}
