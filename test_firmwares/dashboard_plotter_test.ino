/*
 * dashboard_plotter_test.ino
 *
 * Test firmware for Remote Flasher — exercises ALL 35 dashboard channels
 * plus generates interesting waveforms for the serial plotter.
 *
 * Channel map (CSV, comma-separated):
 *   0  rpm           — sine wave 1000-7000
 *   1  speed         — sine wave 0-200
 *   2  coolantTemp   — slow ramp 60-110
 *   3  fuelLevel     — slow decay 100→0 (resets)
 *   4  gear (auto)   — cycles P(7) R(-1) N(0) D(8)
 *   5  battery       — triangle wave 20-100
 *   6  power         — sine wave -50 to +150 (regen to power)
 *   7  rangeKm       — tracks battery * 5
 *   8  doorFL        — toggle every 15s
 *   9  doorFR        — toggle every 20s
 *  10  doorRL        — toggle every 25s
 *  11  doorRR        — toggle every 30s
 *  12  trunk         — toggle every 35s
 *  13  hood          — toggle every 40s
 *  14  checkEngine   — toggle every 8s
 *  15  oilPressure   — toggle every 10s
 *  16  batteryWarn   — on when battery < 30
 *  17  brakeWarn     — toggle every 12s
 *  18  absWarn       — toggle every 9s
 *  19  airbagWarn    — toggle every 14s
 *  20  parkingLights — toggle every 6s
 *  21  lowBeam       — toggle every 7s
 *  22  highBeam      — toggle every 11s
 *  23  fogLights     — toggle every 13s
 *  24  seatbelt      — toggle every 16s
 *  25  turnLeft      — blink 1.5Hz for 6s, then off 6s
 *  26  turnRight     — blink 1.5Hz for 6s (alternates with left)
 *  27  cruiseActive  — on when speed > 80
 *  28  serviceDue    — toggle every 20s
 *  29  tirePressure  — toggle every 22s
 *  30  doorOpen      — toggle every 18s
 *  31  tractionCtrl  — toggle every 15s
 *  32  ecoMode       — on when rpm < 3000
 *  33  evCharging    — on when speed == 0 and battery < 80
 *  34  manualGear    — cycles N(0) 1 2 3 4 5 6 R(-1)
 *
 * Output: 115200 baud, ~20 Hz (50ms interval)
 */

#define INTERVAL_MS 50
#define NUM_CHANNELS 35

float channels[NUM_CHANNELS];
unsigned long lastSend = 0;
unsigned long startTime;

// Gear sequences
const int autoGears[] = {7, -1, 0, 8, 8, 8, 8, 8};  // mostly D
const int autoGearCount = 8;
const int manualGears[] = {0, 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1, 0, -1};
const int manualGearCount = 14;

void setup() {
  Serial.begin(115200);
  startTime = millis();
  memset(channels, 0, sizeof(channels));
}

// Simple toggle: returns 1.0 if on, 0.0 if off
float toggleEvery(float t, float period) {
  return fmod(t, period * 2.0) < period ? 1.0 : 0.0;
}

// Blink pattern for turn signals: blink at ~1.5Hz during on-phase
float turnSignal(float t, float blinkHz, float onDuration, float offset) {
  float cycle = fmod(t + offset, onDuration * 2.0);
  if (cycle > onDuration) return 0.0;  // off phase
  return (sin(t * blinkHz * 2.0 * PI) > 0) ? 1.0 : 0.0;
}

void loop() {
  unsigned long now = millis();
  if (now - lastSend < INTERVAL_MS) return;
  lastSend = now;

  float t = (now - startTime) / 1000.0;  // seconds since start

  // === Analog gauges (channels 0-7) ===

  // RPM: sine 1000-7000, period ~8s
  channels[0] = 4000.0 + 3000.0 * sin(t * 0.8);

  // Speed: sine 0-200, period ~12s (phase offset from RPM)
  channels[1] = 100.0 + 100.0 * sin(t * 0.5 + 1.0);

  // Coolant temp: slow ramp 60-110, period ~30s
  channels[2] = 85.0 + 25.0 * sin(t * 0.2);

  // Fuel level: slow decay from 100 to 10, resets every 60s
  channels[3] = 100.0 - 90.0 * (fmod(t, 60.0) / 60.0);

  // Auto gear: cycle through P/R/N/D every 3s
  channels[4] = autoGears[(int)(t / 3.0) % autoGearCount];

  // Battery: triangle wave 20-100, period ~20s
  float batPhase = fmod(t / 20.0, 1.0);
  channels[5] = (batPhase < 0.5)
    ? 20.0 + 160.0 * batPhase      // 20→100
    : 180.0 - 160.0 * batPhase;    // 100→20

  // Power: sine -50 to +150 (regen to full power)
  channels[6] = 50.0 + 100.0 * sin(t * 0.6);

  // Range: battery * 5
  channels[7] = channels[5] * 5.0;

  // === Doors (channels 8-13) ===
  channels[8]  = toggleEvery(t, 15.0);  // doorFL
  channels[9]  = toggleEvery(t, 20.0);  // doorFR
  channels[10] = toggleEvery(t, 25.0);  // doorRL
  channels[11] = toggleEvery(t, 30.0);  // doorRR
  channels[12] = toggleEvery(t, 35.0);  // trunk
  channels[13] = toggleEvery(t, 40.0);  // hood

  // === Warning lights (channels 14-19) ===
  channels[14] = toggleEvery(t, 8.0);   // checkEngine
  channels[15] = toggleEvery(t, 10.0);  // oilPressure
  channels[16] = (channels[5] < 30.0) ? 1.0 : 0.0;  // batteryWarn when low
  channels[17] = toggleEvery(t, 12.0);  // brakeWarn
  channels[18] = toggleEvery(t, 9.0);   // absWarn
  channels[19] = toggleEvery(t, 14.0);  // airbagWarn

  // === Status lights (channels 20-24) ===
  channels[20] = toggleEvery(t, 6.0);   // parkingLights
  channels[21] = toggleEvery(t, 7.0);   // lowBeam
  channels[22] = toggleEvery(t, 11.0);  // highBeam
  channels[23] = toggleEvery(t, 13.0);  // fogLights
  channels[24] = toggleEvery(t, 16.0);  // seatbeltUnbuckled

  // === Turn signals (channels 25-26) — alternating blink ===
  channels[25] = turnSignal(t, 3.0, 6.0, 0.0);   // turnLeft
  channels[26] = turnSignal(t, 3.0, 6.0, 6.0);   // turnRight (offset = on when left is off)

  // === Extra status (channels 27-33) ===
  channels[27] = (channels[1] > 80.0) ? 1.0 : 0.0;  // cruiseActive when speed > 80
  channels[28] = toggleEvery(t, 20.0);  // serviceDue
  channels[29] = toggleEvery(t, 22.0);  // tirePressure
  channels[30] = toggleEvery(t, 18.0);  // doorOpen
  channels[31] = toggleEvery(t, 15.0);  // tractionControl
  channels[32] = (channels[0] < 3000.0) ? 1.0 : 0.0;  // ecoMode when low RPM
  channels[33] = (channels[1] < 5.0 && channels[5] < 80.0) ? 1.0 : 0.0;  // evCharging

  // === Manual gear (channel 34) ===
  channels[34] = manualGears[(int)(t / 2.0) % manualGearCount];

  // === Output CSV line ===
  for (int i = 0; i < NUM_CHANNELS; i++) {
    if (i > 0) Serial.print(',');
    // Integers for gear and bool channels, floats for analog
    if (i == 4 || i == 34) {
      Serial.print((int)channels[i]);
    } else if (i >= 8 && i <= 33) {
      Serial.print((int)channels[i]);
    } else {
      Serial.print(channels[i], 1);
    }
  }
  Serial.println();
}
