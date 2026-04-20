# TODO

Known open items.

## Serial + flash reliability (open, high priority)

A long v2.3 debugging session uncovered several failure modes in the
serial + flash paths that are still not fully resolved. The v2.3 branch
reverts all *extra* remote-PC interactions back to master semantics
(see **Conversation summary** below) — start here next time.

### To reproduce / verify

1. **Single-panel serial stability.** Open one serial panel on a known-good
   board. Stream data for 5 min. Close. Expected: no orphan `serialterm.py`
   on the remote, no `sshd-session.exe` left over. Run on the remote after
   close:
   ```powershell
   Get-CimInstance Win32_Process |
       Where { $_.CommandLine -match 'serialterm|sshd-session' } |
       Select ProcessId, Name, CommandLine
   ```
   If anything lingers, the local `SerialWorker.stop()` shutdown sequence
   (Ctrl-C → shutdown_write → channel.close) isn't reaching the remote
   python. Re-check with the `try/finally` around `client.close()` now in
   `workers.py`.

2. **Multi-panel serial.** Open panel 1 (e.g. COM29), confirm streaming,
   then open panel 2. Expected: both stream independently. Current
   observed behavior (v2.3): panel 1 sometimes goes silent when panel 2
   opens, especially when both ports are on the **same FT4232H chip**
   (e.g. COM29 + COM30 share a chip on PC 217). Three remaining hypotheses:
   - **FTDI same-chip contention**: opening channel 2 re-initializes the
     chip and the first channel briefly loses its read buffer. Test: open
     panel 2 on a port from a **different** chip (COM17/33/etc.) and see
     if the stall disappears. If yes, it's a hardware-driver quirk — add
     a UI warning or a chip-grouping hint in the port dropdown.
   - **`SerialTab._rebuild_layout` widget reparenting**: every `+ Add Serial`
     reparents existing panels. Qt signal delivery should survive this
     but it's the biggest structural departure from master (master was
     single-panel only). Test with two app instances instead.
   - **Remote CPU/USB stress**: an additional sshd-session + python
     launch in close succession can starve the FTDI driver's capture
     loop. Less likely now that port_lock / heartbeat / reap-PowerShell
     are gone, but still possible on slower PCs.

3. **Flash still fails often.** Even after restoring the flash path to
   master-exact logic (single `AT RT` reset, raw avrdude at 57600, no
   retries), flashes still hang or fail `not in sync: resp=0x00` on PCs
   whose FTDI drivers got wedged during testing. If this happens in a
   clean state post-reboot, the remaining variables are hardware-side —
   check for stuck `avrdude.exe` orphans, stale COM handles, or a reset-
   helper Prolific that went into an empty-response state (`AT BI`
   returns nothing).

### Diagnostic helpers that already exist

- `scan_ports.py` with `--reset-ports "Placa 01=COMxx,..."` to remap
  boards after a USB re-enumeration. Parallel mode (default) runs all
  16 avrdudes per reset pulse.
- `setup_serialterm_janitor.ps1` — scheduled task that reaps orphan
  serialterm.py / avrdude.exe every 5 min on the remote. Includes
  PID-recycle detection (critical — Windows doesn't reparent orphans).
- Diagnose what's holding a COM port:
  ```powershell
  Get-CimInstance Win32_Process |
      Where { $_.CommandLine -match 'COM29' } |
      Select ProcessId, Name, CommandLine | Format-List
  ```
- Recover a wedged FTDI driver without reboot (requires admin):
  ```powershell
  $id = (Get-PnpDevice -Class Ports | Where FriendlyName -Like '*COM29*').InstanceId
  pnputil /restart-device "$id"
  ```
  If that fails with HRESULT `0x80041001`, the handle is kernel-pinned —
  reboot or physical USB unplug is the only recovery.

### The `AT RT` vs. `AT RU`/`AT RD` saga

Lab has **multiple reset-helper firmware revisions** running simultaneously:
older units accept single-shot `AT RT`, newer ones accept the two-step
`AT RU` → `AT RD` pulse. Current code (matches master) sends only
`AT RT`. If a newer-firmware board stops flashing, the fix is to send
both sequences back-to-back in `reset_board()`:
```python
ser.write(b"AT RT\n")
ser.write(b"AT RU\n")
time.sleep(0.2)
ser.write(b"AT RD\n")
```
Any gap between `AT RT` and `AT RU` (even 50 ms) breaks older firmware
because the RT pulse fires first and RU then lands mid-bootloader.

## Conversation summary (v2.2 → v2.3 debugging session)

This branch started by adding a *lot* of new functionality (HMI
dashboard, plotter with cursors, DashboardSignals library, port locks,
SSH watchdog, camera autostart, scheduled janitor). During field
testing with multiple users + concurrent serial/flash, several bugs
cascaded. The timeline:

1. **port_lock SFTP churn** (now removed) kept a shared paramiko client
   per host indefinitely + polled every 60 s + per-panel heartbeat every
   60 s. Triple-digit sshd-session spawns per session on busy days.
2. **Camera autostart + watchdog** — `camera1.py` running on the remote
   has an internal capture watchdog that exits on USB stalls. The
   scheduled task restarts it within ~1 min. Under SFTP/SSH stress from
   port_lock, the watchdog tripped frequently, correlating with "camera
   dropped when I opened serial". The autostart setup is now deleted
   from the repo per user request — disable it on live lab PCs by:
   ```powershell
   Stop-ScheduledTask -TaskName 'Camera MJPEG Server'
   Unregister-ScheduledTask -TaskName 'Camera MJPEG Server' -Confirm:$false
   ```
3. **Janitor PID-recycle blind spot**: Windows doesn't reparent orphans
   to init (unlike Linux) — the orphan keeps its dead parent's PID, and
   Windows may later recycle that PID to an unrelated process. The old
   `Get-Process -Id $ParentProcessId` saw that recycled process and
   thought the orphan was alive. Fix: compare `CreationDate`s — parent
   younger than child = recycled PID = orphan. Shipped in
   `setup_serialterm_janitor.ps1`.
4. **Reap process-name filter was too narrow**: `Name='python.exe'`
   missed `python3.11.exe` (Microsoft Store Python install on PC 217).
   Fix: drop the Name filter, match on cmdline only. Shipped in the
   janitor; the inline reap in serialterm.py was removed entirely per
   "no new remote connections" directive.
5. **Pyserial close race** — `_overlapped_read.hEvent` is `None` if
   `ser.close()` runs while another thread is mid-`readline()`. Kills
   Python ungracefully, leaks the COM handle, next open fails with
   "Acesso negado". Fix: `_stop` event + `ser.cancel_read()` + reader
   join *before* `ser.close()`. Shipped in `serialterm.py` (local-only,
   no new remote activity).
6. **SerialWorker client leak** — `self._client.close()` was only on the
   happy path; any recv-loop exception jumped to `except` and skipped
   it, leaving sshd-session processes piling up. Fix: `try/finally`
   around the teardown. Shipped in `workers.py`.
7. **PnP `/remove-device` is destructive** — during the PC 217 recovery
   attempts, `pnputil /remove-device` was used and permanently removed
   a device node that wouldn't rescan. One FTDI / one Prolific went
   missing. Lesson: use `/restart-device` or `Restart-PnpDevice` for
   transient wedges; only `/remove-device` if you're ready for a
   physical replug or reboot.
8. **COM renumbering after reboot**: FTDI's COMDB usually persists
   assignments across reboots, but a removed device node gets a fresh
   number on re-enumeration. After reboot, re-run `scan_ports.py` and
   update `c:\dev\ports.json`.

### What got kept from this branch (as of commit)

- HMI dashboard + plotter tabs (complete, new in v2.3)
- DashboardSignals library (AVR RAM tightened: 16 slots × 18-char names
  to fit alongside 256-byte EngineTask stack in example 13)
- Plotter features: Cursors, Auto-Y, Reset-View, Stats panel, sample-rate
  indicator, clickable legend, Timestamp checkbox in serial
- scan_ports.py: USB-VID-based auto-discovery, parallel-mode scanning,
  live per-port progress, line-buffered stdout for SSH
- `setup_serialterm_janitor.ps1` (PID-recycle-aware, cmdline-based filter)
- `try/finally` client cleanup in SerialWorker (fixes sshd-session leak)
- Pyserial race fix in serialterm.py (local-only shutdown synchronization)

### What got removed / reverted to master

- `port_lock.py` (entire module, including LockAcquireWorker / LockReleaseWorker
  in workers.py and all call sites in flash_tab / serial_tab / main_window)
- `setup_camera_autostart.ps1` (per user request)
- Per-panel 60 s lock heartbeat timer
- SSH banner retry loop in SerialWorker
- SFTP size-check + upload of serialterm.py on every open
  (back to master's inline `if not exist … copy` in one SSH command)
- Serial panel "in use by …" port dropdown annotations
- Serialterm.py's PowerShell `Get-CimInstance` reap on PermissionError
- `[Serial HB]` diagnostic heartbeat (used during debugging, removed)

## Earlier items (pre-v2.3)

- **Dashboard tooltips don't appear.**
  `setToolTip` was set on `InfoCardWidget` / `StatusLightWidget` /
  `AnalogGaugeWidget` in `src/tabs/gauges_tab.py`, but hovering shows
  nothing. Hypotheses to check:
  - Child `QLabel`s fill the parent and capture hover without a tooltip
    of their own — Qt should bubble up, but some themes/stylesheet
    combos break that. Try propagating the tooltip to every child label.
  - `self.setStyleSheet("background: #0a0a18;")` on `GaugesTab` may be
    interfering with tooltip event delivery; verify by temporarily
    removing.
  - `AnalogGaugeWidget` paints with `QPainter` over the whole rect —
    confirm it doesn't call `setMouseTracking(False)` or override
    `event()` in a way that swallows `QEvent::ToolTip`.

- **Flash tab: a blank white horizontal strip appears below the button row.**
  Visible between the green "Upload + Reset + Flash" button and the log.
  Likely an unstyled container widget falling back to the Windows light
  theme. Find the offending widget and give it the app's dark background
  (`#1e1e1e` or the palette-based `_apply_dark_bg` helper from
  `widgets.py`).

## Nice to have

- Audit remaining interactive widgets without tooltips: serial panel
  "Send" button, VIO buttons (B1–B4, L1–L4, POT sliders), per-panel
  Clear Log, dashboard status column header cells.
- Dashboard source combo: dynamically refresh its list when serial
  panels are added/removed, so the user doesn't need to reopen the tab.
- ~~Plotter legend: make individual entries clickable to toggle curve
  visibility~~ ✓ Done in v2.3.
- Capture the remaining docs/images screenshots (dashboard modes x3,
  plotter overview/cursors/waveforms/stats/toolbar) — blocked this
  session by serial instability.
</content>
</invoke>