# Trampoline RTOS Examples

Copy any example folder into `C:\ESA\trampoline\opt\devel\`, add `Board.h` (and `VirtualIO.h/cpp` if needed), then build:

```
goil --target=avr/arduino/nano --templates=../../../goil/templates/ <name>.oil
python build.py
```

| # | Example | Concepts | Files |
|---|---------|----------|-------|
| 01 | Blink | Task, Alarm, `TerminateTask()` | blink.oil, blink.cpp |
| 02 | Multitask | Multiple tasks, priorities, preemption | multitask.oil, multitask.cpp |
| 03 | Dynamic Alarm | `SetRelAlarm()`, `CancelAlarm()`, runtime period change | alarm_dynamic.oil, alarm_dynamic.cpp |
| 04 | Producer-Consumer | `RESOURCE`, `GetResource()`, `ReleaseResource()` | prodcons.oil, prodcons.cpp |
| 05 | CAN Basic | MCP2515 TX + RX, `sendMsgBuf()`, `readMsgBuf()` | can_tx.oil/cpp, can_rx.oil/cpp |
| 06 | VirtualIO Demo | Buttons, potentiometers, LEDs via Remote Flasher GUI | virtualio_demo.oil/cpp + VirtualIO.h/cpp |
| 07 | CAN Signals | Signal encoding/decoding, resolution, offset, sequence counter, stale detection | can_signals_tx.oil/cpp, can_signals_rx.oil/cpp |
| 08 | Board I/O | Physical pins via Board.h: digitalRead, analogRead, digitalWrite | board_io.oil, board_io.cpp + Board.h |
