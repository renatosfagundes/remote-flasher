/*
 * VirtualIO.cpp — Bidirectional virtual I/O for Remote Firmware Flasher
 *
 * Memory usage: ~20 bytes (4 btn + 2 pot + 4 led + 4 led_prev + buffer)
 * CPU overhead: negligible — only parses when Serial.available() > 0
 *               only sends LED commands when value changes
 */

#include "VirtualIO.h"

// Internal state
static uint8_t _vio_buttons[VIO_NUM_BUTTONS];
static int     _vio_pots[VIO_NUM_POTS];
static uint8_t _vio_leds[VIO_NUM_LEDS];
static uint8_t _vio_leds_prev[VIO_NUM_LEDS];  // track previous to avoid redundant sends
static char    _vio_buf[16];
static uint8_t _vio_buf_pos = 0;
static bool    _vio_initialized = false;

void vioInit(void) {
    for (uint8_t i = 0; i < VIO_NUM_BUTTONS; i++)
        _vio_buttons[i] = 0;
    for (uint8_t i = 0; i < VIO_NUM_POTS; i++)
        _vio_pots[i] = 0;
    for (uint8_t i = 0; i < VIO_NUM_LEDS; i++) {
        _vio_leds[i] = 0;
        _vio_leds_prev[i] = 255;  // force first send
    }
    _vio_buf_pos = 0;
    _vio_initialized = true;
}

/*
 * Parse a complete command line.
 * Expected: "!B1:1", "!B1:0", "!P1:512"
 */
static void _vio_parse(const char *cmd) {
    if (cmd[0] != '!') return;

    char type = cmd[1];
    uint8_t idx = cmd[2] - '1';
    if (cmd[3] != ':') return;
    int value = atoi(&cmd[4]);

    if (type == 'B' && idx < VIO_NUM_BUTTONS) {
        _vio_buttons[idx] = (value != 0) ? 1 : 0;
    } else if (type == 'P' && idx < VIO_NUM_POTS) {
        if (value < 0) value = 0;
        if (value > 1023) value = 1023;
        _vio_pots[idx] = value;
    }
}

void vioUpdate(void) {
    if (!_vio_initialized) return;

    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (_vio_buf_pos > 0) {
                _vio_buf[_vio_buf_pos] = '\0';
                if (_vio_buf[0] == '!') {
                    _vio_parse(_vio_buf);
                }
                _vio_buf_pos = 0;
            }
        } else {
            if (_vio_buf_pos < sizeof(_vio_buf) - 1) {
                _vio_buf[_vio_buf_pos++] = c;
            }
        }
    }
}

uint8_t vRead(uint8_t btn) {
    if (btn >= VIO_NUM_BUTTONS) return 0;
    return _vio_buttons[btn];
}

int vAnalogRead(uint8_t pot) {
    if (pot >= VIO_NUM_POTS) return 0;
    return _vio_pots[pot];
}

void vLedWrite(uint8_t led, uint8_t brightness) {
    if (led >= VIO_NUM_LEDS) return;
    _vio_leds[led] = brightness;
    // Only send when value actually changed — avoids flooding serial
    if (_vio_leds[led] != _vio_leds_prev[led]) {
        _vio_leds_prev[led] = _vio_leds[led];
        Serial.print("!L");
        Serial.print(led + 1);
        Serial.print(":");
        Serial.println(brightness);
    }
}
