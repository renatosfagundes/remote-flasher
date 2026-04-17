/*
 * DashboardSignals.cpp — Named signal interface for Remote Flasher
 *
 * Buffers key:value pairs in a flat array and flushes them as one
 * comma-separated line on dashFlush(). Designed for low-memory AVR
 * targets (Arduino Nano, ATmega328P).
 */

#include "DashboardSignals.h"
#include <string.h>

// Signal entry — tagged union: float with decimals, int, or bool
typedef struct {
    char name[DASH_MAX_NAME_LEN];
    enum { DS_FLOAT, DS_INT, DS_BOOL } type;
    union {
        struct { float val; uint8_t dec; } f;
        int i;
        bool b;
    } data;
} DashEntry;

static DashEntry _buf[DASH_MAX_SIGNALS];
static uint8_t   _count = 0;

void dashInit(void) {
    _count = 0;
}

static void _addEntry(const char* name, DashEntry* entry) {
    if (_count >= DASH_MAX_SIGNALS) return;
    strncpy(_buf[_count].name, name, DASH_MAX_NAME_LEN - 1);
    _buf[_count].name[DASH_MAX_NAME_LEN - 1] = '\0';
    _buf[_count].type = entry->type;
    _buf[_count].data = entry->data;
    _count++;
}

void dashSend(const char* name, float value) {
    dashSendPrec(name, value, 1);
}

void dashSendPrec(const char* name, float value, uint8_t decimals) {
    DashEntry e;
    e.type = DS_FLOAT;
    e.data.f.val = value;
    e.data.f.dec = decimals;
    _addEntry(name, &e);
}

void dashSendInt(const char* name, int value) {
    DashEntry e;
    e.type = DS_INT;
    e.data.i = value;
    _addEntry(name, &e);
}

void dashSendBool(const char* name, bool value) {
    DashEntry e;
    e.type = DS_BOOL;
    e.data.b = value;
    _addEntry(name, &e);
}

void dashFlush(void) {
    if (_count == 0) return;

    for (uint8_t i = 0; i < _count; i++) {
        if (i > 0) Serial.print(',');
        Serial.print(_buf[i].name);
        Serial.print(':');
        switch (_buf[i].type) {
            case DS_FLOAT:
                Serial.print(_buf[i].data.f.val, _buf[i].data.f.dec);
                break;
            case DS_INT:
                Serial.print(_buf[i].data.i);
                break;
            case DS_BOOL:
                Serial.print(_buf[i].data.b ? 1 : 0);
                break;
        }
    }
    Serial.println();
    _count = 0;
}

uint8_t dashBufferCount(void) {
    return _count;
}
