# Trampoline RTOS Examples

Copy any example folder into `C:\ESA\trampoline\opt\devel\`, add `Board.h` and the required library files, then build:

```
goil --target=avr/arduino/nano --templates=../../../goil/templates/ <name>.oil
python build.py
```

## Libraries

| Library | Files to copy | Purpose |
|---------|---------------|---------|
| VirtualIO | `VirtualIO.h`, `VirtualIO.cpp` | Virtual buttons, potentiometers, LEDs via GUI |
| DashboardSignals | `DashboardSignals.h`, `DashboardSignals.cpp` | Named signals for HMI Dashboard and Plotter |

Both live in `arduino_lib/`. Copy the required `.h` and `.cpp` files into your example folder and add the `.cpp` to `APP_SRC` in your `.oil` file.

## Examples

| # | Example | Concepts | Libraries | Files |
|---|---------|----------|-----------|-------|
| 01 | Blink | Task, Alarm, `TerminateTask()` | — | blink.oil, blink.cpp |
| 02 | Multitask | Multiple tasks, priorities, preemption | — | multitask.oil, multitask.cpp |
| 03 | Dynamic Alarm | `SetRelAlarm()`, `CancelAlarm()`, runtime period change | — | alarm_dynamic.oil, alarm_dynamic.cpp |
| 04 | Producer-Consumer | `RESOURCE`, `GetResource()`, `ReleaseResource()` | — | prodcons.oil, prodcons.cpp |
| 05 | CAN Basic | MCP2515 TX + RX, `sendMsgBuf()`, `readMsgBuf()` | — | can_tx.oil/cpp, can_rx.oil/cpp |
| 06 | VirtualIO Demo | Buttons, potentiometers, LEDs via Remote Flasher GUI | VirtualIO | virtualio_demo.oil/cpp |
| 07 | CAN Signals | Signal encoding/decoding, resolution, offset, stale detection | — | can_signals_tx.oil/cpp, can_signals_rx.oil/cpp |
| 08 | Board I/O | Physical pins via Board.h | — | board_io.oil, board_io.cpp + Board.h |
| 09 | Dashboard Basic | Send speed + RPM to HMI Dashboard | DashboardSignals | dashboard_basic.oil/cpp |
| 10 | Dashboard Gauges | All gauges: speed, RPM, temp, fuel, battery, gear, odometer | DashboardSignals | dashboard_gauges.oil/cpp |
| 11 | Dashboard Warnings | Warning lights, status indicators, turn signals | DashboardSignals | dashboard_warnings.oil/cpp |
| 12 | Dashboard Doors | Interactive doors via VirtualIO + Dashboard | VirtualIO, DashboardSignals | dashboard_doors.oil/cpp |
| 13 | Dashboard Full | Multi-task vehicle simulation (3 tasks, different rates) | DashboardSignals | dashboard_full.oil/cpp |
| 14 | Odo / Avg Speed Test | Focused verification of `distance` + `avgSpeed` signals (step plateaus, EMA lag) | DashboardSignals | odo_avgspeed_test.oil/cpp |
| 15 | Plotter Waveforms | Sine/triangle/square/sawtooth on custom names — generic plotter demo | DashboardSignals | plotter_waveforms.oil/cpp |
| 16 | Plotter Step Response | Square input + 3 EMAs at different τ — designed for the measurement cursors | DashboardSignals | plotter_step_response.oil/cpp |

## Dashboard Signal Format

The `DashboardSignals` library sends named key:value pairs over serial,
prefixed with `$` so the app can distinguish signal messages from ordinary
`Serial.print` output (mirrors how VirtualIO uses `!`):

```
$speed:50.0,rpm:7200,coolantTemp:85.5,gear:8,checkEngine:0
```

Anything without the `$` prefix is treated as normal log output and won't
show up in the Dashboard or Plotter — so you can freely mix `Serial.println("hello")`
with `dashSend(...)` / `dashFlush()` calls.

### How it works

1. Flash the firmware and open a serial connection in the Serial tab
2. Enable **"Feed Dashboard"** to route signals to the HMI gauges
3. Enable **"Feed Plotter"** (independently) to graph them over time
4. Optionally enable **"Filter Signals"** to hide the raw `$...` lines from the terminal log

### Recognized signal names

| Category | Signal names |
|----------|-------------|
| **Gauges** | `speed`, `rpm`, `coolantTemp`, `fuelLevel`, `battery`, `power`, `rangeKm` |
| **Gears** | `gear` (P=7, R=-1, N=0, D=8), `manualGear` (N=0, R=-1, 1-6) |
| **Odometer** | `distance`, `avgSpeed` |
| **Doors** | `doorFL`, `doorFR`, `doorRL`, `doorRR`, `trunk`, `hood` |
| **Warnings** | `checkEngine`, `oilPressure`, `batteryWarn`, `brakeWarn`, `absWarn`, `airbagWarn` |
| **Status** | `parkingLights`, `lowBeam`, `highBeam`, `fogLights`, `seatbeltUnbuckled` |
| **Signals** | `turnLeft`, `turnRight` |
| **Extra** | `cruiseActive`, `ecoMode`, `evCharging`, `serviceDue`, `tirePressure`, `doorOpen`, `tractionControl` |

Any signal name **not** in this list still appears in the Plotter — useful for custom application data like `throttle`, `brakeForce`, `steeringAngle`, etc.

### API Reference

```c
#include "DashboardSignals.h"

dashInit();                              // call once in setup()
dashSend("speed", 50.0);                // buffer a float (1 decimal)
dashSendPrec("coolantTemp", 85.5, 2);   // buffer a float (2 decimals)
dashSendInt("gear", 8);                 // buffer an integer
dashSendBool("checkEngine", true);      // buffer a boolean (sent as 1/0)
dashFlush();                            // send all buffered signals as one line
```

Call `dashFlush()` once per task cycle — it sends all buffered signals as a single comma-separated line and resets the buffer.
