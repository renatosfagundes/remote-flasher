/*
 * dashboard_plotter_test.ino
 *
 * Test firmware for Remote Flasher — sends named key:value pairs over serial
 * that are auto-routed to the dashboard and plotter.
 *
 * Format:  speed:50.0,rpm:7200,coolantTemp:85.5,gear:8,...
 *
 * Signal names match dashboard properties, so the HMI gauges update
 * automatically. The plotter shows all signals by name.
 *
 * Output: 115200 baud, ~20 Hz (50ms interval)
 */

#define INTERVAL_MS 50

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
}

float toggleEvery(float t, float period) {
  return fmod(t, period * 2.0) < period ? 1.0 : 0.0;
}

float turnSignal(float t, float blinkHz, float onDuration, float offset) {
  float cycle = fmod(t + offset, onDuration * 2.0);
  if (cycle > onDuration) return 0.0;
  return (sin(t * blinkHz * 2.0 * PI) > 0) ? 1.0 : 0.0;
}

void printSignal(const char* name, float value, int decimals = 1) {
  Serial.print(name);
  Serial.print(':');
  Serial.print(value, decimals);
}

void printSignalInt(const char* name, int value) {
  Serial.print(name);
  Serial.print(':');
  Serial.print(value);
}

void loop() {
  unsigned long now = millis();
  if (now - lastSend < INTERVAL_MS) return;
  lastSend = now;

  float t = (now - startTime) / 1000.0;

  // === Analog gauges ===
  float rpm   = 4000.0 + 3000.0 * sin(t * 0.8);
  float speed = 100.0 + 100.0 * sin(t * 0.5 + 1.0);
  float coolant = 85.0 + 25.0 * sin(t * 0.2);
  float fuel  = 100.0 - 90.0 * (fmod(t, 60.0) / 60.0);
  float batPhase = fmod(t / 20.0, 1.0);
  float battery = (batPhase < 0.5) ? 20.0 + 160.0 * batPhase : 180.0 - 160.0 * batPhase;
  float power = 50.0 + 100.0 * sin(t * 0.6);
  float rangeKm = battery * 5.0;
  int gear = autoGears[(int)(t / 3.0) % autoGearCount];
  int mGear = manualGears[(int)(t / 2.0) % manualGearCount];

  printSignal("speed", speed);        Serial.print(',');
  printSignal("rpm", rpm, 0);         Serial.print(',');
  printSignal("coolantTemp", coolant); Serial.print(',');
  printSignal("fuelLevel", fuel);      Serial.print(',');
  printSignal("battery", battery);     Serial.print(',');
  printSignal("power", power);         Serial.print(',');
  printSignal("rangeKm", rangeKm, 0); Serial.print(',');
  printSignalInt("gear", gear);        Serial.print(',');
  printSignalInt("manualGear", mGear); Serial.print(',');

  // === Doors ===
  printSignalInt("doorFL", (int)toggleEvery(t, 15.0)); Serial.print(',');
  printSignalInt("doorFR", (int)toggleEvery(t, 20.0)); Serial.print(',');
  printSignalInt("doorRL", (int)toggleEvery(t, 25.0)); Serial.print(',');
  printSignalInt("doorRR", (int)toggleEvery(t, 30.0)); Serial.print(',');
  printSignalInt("trunk",  (int)toggleEvery(t, 35.0)); Serial.print(',');
  printSignalInt("hood",   (int)toggleEvery(t, 40.0)); Serial.print(',');

  // === Warning lights ===
  printSignalInt("checkEngine",  (int)toggleEvery(t, 8.0));  Serial.print(',');
  printSignalInt("oilPressure",  (int)toggleEvery(t, 10.0)); Serial.print(',');
  printSignalInt("batteryWarn",  battery < 30.0 ? 1 : 0);    Serial.print(',');
  printSignalInt("brakeWarn",    (int)toggleEvery(t, 12.0));  Serial.print(',');
  printSignalInt("absWarn",      (int)toggleEvery(t, 9.0));   Serial.print(',');
  printSignalInt("airbagWarn",   (int)toggleEvery(t, 14.0));  Serial.print(',');

  // === Status lights ===
  printSignalInt("parkingLights", (int)toggleEvery(t, 6.0));  Serial.print(',');
  printSignalInt("lowBeam",       (int)toggleEvery(t, 7.0));  Serial.print(',');
  printSignalInt("highBeam",      (int)toggleEvery(t, 11.0)); Serial.print(',');
  printSignalInt("fogLights",     (int)toggleEvery(t, 13.0)); Serial.print(',');
  printSignalInt("seatbeltUnbuckled", (int)toggleEvery(t, 16.0)); Serial.print(',');

  // === Turn signals ===
  printSignalInt("turnLeft",  (int)turnSignal(t, 3.0, 6.0, 0.0)); Serial.print(',');
  printSignalInt("turnRight", (int)turnSignal(t, 3.0, 6.0, 6.0)); Serial.print(',');

  // === Extra status ===
  printSignalInt("cruiseActive",    speed > 80.0 ? 1 : 0);           Serial.print(',');
  printSignalInt("serviceDue",      (int)toggleEvery(t, 20.0));      Serial.print(',');
  printSignalInt("tirePressure",    (int)toggleEvery(t, 22.0));      Serial.print(',');
  printSignalInt("doorOpen",        (int)toggleEvery(t, 18.0));      Serial.print(',');
  printSignalInt("tractionControl", (int)toggleEvery(t, 15.0));      Serial.print(',');
  printSignalInt("ecoMode",         rpm < 3000.0 ? 1 : 0);          Serial.print(',');
  printSignalInt("evCharging",      (speed < 5.0 && battery < 80.0) ? 1 : 0);

  Serial.println();
}
