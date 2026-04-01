# Trampoline RTOS Examples

Copy any example folder into `C:\ESA\trampoline\opt\devel\`, add `Board.h` from the `_template`, then build:

```
goil --target=avr/arduino/nano --templates=../../../goil/templates/ <name>.oil
python build.py
```

| # | Example | Concepts | Files |
|---|---------|----------|-------|
| 01 | Blink | Task, Alarm, `TerminateTask()` | blink.oil, blink.cpp |
| 02 | Multitask | Multiple tasks, priorities, preemption | multitask.oil, multitask.cpp |
| 03 | Dynamic Alarm | `SetRelAlarm()`, `CancelAlarm()`, runtime period change | alarm_dynamic.oil, alarm_dynamic.cpp |
| 04 | Producer-Consumer | `RESOURCE`, `GetResource()`, `ReleaseResource()`, mutual exclusion | prodcons.oil, prodcons.cpp |
| 05 | CAN Basic | MCP2515, `sendMsgBuf()`, `readMsgBuf()`, two-board setup | can_tx.oil/cpp, can_rx.oil/cpp |
