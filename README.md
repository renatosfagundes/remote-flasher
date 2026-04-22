# Remote Firmware Flasher

A PySide6 desktop application for remotely flashing Arduino boards over VPN + SSH. Built for the UFPE/CIn Residencia Tecnologica lab, where students connect to lab PCs via SSTP VPN and flash ATmega328p boards without being physically present.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Features

- **VPN Connection** — Connect to the lab VPN (SSTP) directly from the app, with auto-detection of existing connections, auto-profile creation, and optional credential saving. Disconnect prompt on exit.
- **Firmware Flashing** — Upload `.hex` files via SCP and flash using `avrdude` over SSH. Real-time streaming output (PTY-based), baud-rate fallback (57600 → 115200), correct exit-code reporting, and pre-flight checks (VPN status + COM port conflict with serial panels).
- **Board Reset** — Parameterized `reset.ps1` PowerShell script (one file, any port) triggers board reset via AT commands on the MCU control port.
- **Port Distribution Sync** — One-click sync of per-PC board/port mappings from `c:\dev\ports.json` on the primary lab PC. Cached locally so the next launch starts with the latest distribution without re-syncing.
- **CAN Network Configuration** — Visual bus topology, per-board CAN1/CAN2 selection via AT commands, quick presets, board detection (AT BI/FV/BV), sequential reliable switching.
- **Multi-Serial Terminal** — Up to 4 simultaneous serial connections with spatial layout (side-by-side, 2+1, 2x2 grid), bidirectional send, autoscroll toggle, and port exclusion.
- **Virtual I/O** — 4 buttons, 4 LEDs, and 2 potentiometers per serial panel. Buttons and pots send commands to the Arduino; LEDs are controlled by the firmware with brightness scaling. Includes Arduino library (`VirtualIO.h`).
- **HMI Dashboard** — QML-based automotive dashboard with three modes (Electric / Combustion Auto / Combustion Manual). Live speedometer, tachometer, fuel/battery/temperature gauges, gear selector, door status, warning lights, turn signals, and 7-segment odometer. Signals auto-routed from serial when **Feed Dashboard** is enabled on any panel.
- **Real-Time Plotter** — pyqtgraph-based scrolling plotter at 30 fps with auto-discovery of named signals. Measurement cursor pair with Δt/min/max/mean/std readout, one-shot Auto-Y fit, live stats panel, sample-rate indicator, clickable legend, per-signal color/scale/offset, CSV export.
- **DashboardSignals library** — Arduino helper (`DashboardSignals.h/cpp`) for buffering named key:value signals and flushing one CSV line per task cycle. Any name goes to the Plotter; recognized names also drive the HMI Dashboard.
- **SSH Terminal + SFTP Upload** — Run commands and upload files/folders to the remote PC with progress tracking.
- **Live Camera** — View the lab camera feed (collapsible side panel, auto-resizes with serial panel count). Only PCs with a configured `camera_url` appear in the dropdown.
- **Environment Setup** — One-click installation of Arduino CLI, AVR Toolchain, Trampoline RTOS, goil, MCP_CAN. Python detection with clear messaging.
- **IDE Integration Guides** — Built-in guides for Notepad++ and VSCode with ready-to-use configurations.
- **Multi-PC Support** — Pre-configured for multiple lab PCs, each with 4 boards and CAN selectors.

## Installation

### Option 1: Standalone executable (recommended)

Download `RemoteFlasher.exe` from the [Releases](https://github.com/renatosfagundes/remote-flasher/releases) page and run it. No Python needed.

You will still need `secrets.py` — see [Configuring credentials](#configuring-credentials) below.

### Option 2: From source

```bash
git clone https://github.com/renatosfagundes/remote-flasher.git
cd remote-flasher
pip install -r requirements.txt
cp secrets.example.py secrets.py  # fill in lab credentials
python src/main.py
```

## Configuring credentials

The file `secrets.py` contains SSH hosts, usernames, and passwords for the lab PCs. It is **not included in the repository** for security.

**To obtain `secrets.py` with the correct credentials, contact Davi or Renato.**

If you are setting up a new lab, copy `secrets.example.py` to `secrets.py` and fill in your values:

```python
SSH_HOSTS = {
    "PC 217": {
        "host": "192.168.1.100",
        "user": "your_ssh_user",
        "password": "your_ssh_password",
        "camera_url": "http://192.168.1.100:8080/video_feed",
    },
}
```

## Environment Setup

The **Setup** tab automates the installation of all development tools needed for the course:

| Component | Description |
|---|---|
| Arduino CLI | Compile and upload Arduino sketches |
| AVR Toolchain | GCC cross-compiler for ATmega328p |
| Trampoline RTOS | OSEK/AUTOSAR real-time OS |
| goil | OIL compiler for Trampoline |
| MCP_CAN | CAN bus library for MCP2515 modules |

Everything is installed to `C:\ESA`. Click **"Run Full Setup"** and follow the progress log.

A standalone `setup_environment.py` script is also available for use outside the GUI:

```bash
python setup_environment.py          # full install
python setup_environment.py --check  # verify what's installed
```

## Usage

### 1. Connect to VPN

Go to the **VPN** tab, enter your CIn credentials, and click **Connect**. Check **Remember me** to save credentials locally.

### 2. Flash firmware

1. Go to the **Flash** tab
2. Select the target **PC**, **Board**, and **ECU port**
3. Browse for your `.hex` file
4. Click **Upload + Reset + Flash** to do everything in one step

### 3. Configure CAN network

Go to the **CAN** tab. Select the PC, choose CAN 1 or CAN 2 for each board, and click **Apply**. Use presets for common configurations. Click **Detect Boards** to verify board connectivity.

### 4. Monitor serial output

Go to the **Serial** tab. Click **"+ Add Serial"** for up to 4 simultaneous connections with adaptive layout:
- **1 panel**: full area
- **2 panels**: side by side
- **3 panels**: 2 top + 1 bottom
- **4 panels**: 2x2 grid

Each panel supports sending commands, has an autoscroll toggle, and connected ports are excluded from other panels.

**Virtual I/O:** Each serial panel includes virtual buttons (B1-B4), LEDs (L1-L4), and potentiometers (POT1-POT2). Use these to interact with your firmware remotely — buttons and pots send commands to the Arduino, LEDs are controlled by the firmware via `vLedWrite()`. Click **"Upload serialterm.py"** once before connecting to enable bidirectional communication.

The `arduino_lib/VirtualIO/` folder contains the Arduino library (`VirtualIO.h`, `VirtualIO.cpp`) to include in your Trampoline projects.

### 5. Live Dashboard + Plotter

Enable **Feed Dashboard** on any serial panel to route incoming signals.

- **Dashboard tab**: automotive HMI. Switch between Electric, Combustion Auto and Combustion Manual modes from the dropdown. Gauges, warning lights, gear selector, door status and odometer update from recognized signal names (`speed`, `rpm`, `coolantTemp`, `fuelLevel`, `battery`, `distance`, `avgSpeed`, `gear`, `checkEngine`, …).
- **Plotter tab**: every named signal (recognized or custom) is auto-added. Toolbar controls:
  - **Window**: visible time window (5–120 s)
  - **Pause / Resume**: freeze the view without dropping samples
  - **Export CSV**: dump the full history to a file
  - **Cursors**: draggable cursor pair, pinned to the scrolling window. The stats panel switches to Δt/min/max/mean/std between the cursors.
  - **Auto-Y**: one-shot Y-axis fit to the visible data
  - **Reset View**: resume X scrolling + re-fit Y
  - **Stats**: toggle a right-side panel with live min/max/mean/std per visible signal
  - **Hz indicator**: effective sample rate (samples/sec over the last 2 s)

Firmware integration uses the `DashboardSignals` library from `arduino_lib/DashboardSignals/` — see examples 09–14.

> **⚠ Serial transmit rate vs. camera feed.** On lab PCs where the FTDI adapters and the BRIO webcam share a USB host controller, heavy serial output can starve the camera's MSMF pipeline and drop it into `ERROR_GEN_FAILURE`. Keep `dashFlush()` calls to **≤ 5 Hz** (one flush per ~200 ms) when using the Dashboard/Plotter with the camera live. All shipped `examples/09_dashboard_*` through `examples/16_plotter_*` have been set to 5 Hz for this reason — if you fork one of them, keep the cycle time at 200 ms or slower. Longer-term fix: move the BRIO cable to a USB port on a different root controller.

### 6. SSH Terminal + File Upload

Run commands on the remote PC and upload files or entire folders via SFTP with a progress bar.

### 7. IDE Integration

The **Setup** tab includes guides for integrating the toolchain with **Notepad++** (NppExec scripts, macros) and **VSCode** (IntelliSense, build tasks, settings).

## Examples

The `examples/` folder contains ready-to-compile Trampoline RTOS projects covering the core course concepts plus the HMI Dashboard and Plotter workflow:

| # | Example | Concepts | Library |
|---|---------|----------|---------|
| 01 | blink | Task, Alarm, `TerminateTask()` | — |
| 02 | multitask | Multiple tasks, priorities, preemption | — |
| 03 | alarm_dynamic | `SetRelAlarm()`, `CancelAlarm()`, runtime period change | — |
| 04 | resource_prodcons | `RESOURCE`, `GetResource()`, `ReleaseResource()`, producer-consumer | — |
| 05 | can_basic | MCP2515 TX + RX, `sendMsgBuf()`, `readMsgBuf()` | — |
| 06 | virtualio | Buttons, pots, LEDs via Remote Flasher GUI | VirtualIO |
| 07 | can_signals | CAN with signal packing, scale conversion, sequence counter | — |
| 08 | board_io | Digital read/write with `Board.h` pins | — |
| 09 | dashboard_basic | Send speed + RPM to the HMI Dashboard | DashboardSignals |
| 10 | dashboard_gauges | All gauges: speed, RPM, temp, fuel, battery, gear, odometer | DashboardSignals |
| 11 | dashboard_warnings | Warning lights, status indicators, turn signals | DashboardSignals |
| 12 | dashboard_doors | Interactive doors via Virtual I/O + Dashboard | VirtualIO, DashboardSignals |
| 13 | dashboard_full | Multi-task vehicle simulation (3 tasks at different rates) | DashboardSignals |
| 14 | odo_avgspeed_test | Focused verification of the `distance` and `avgSpeed` signals | DashboardSignals |
| 15 | plotter_waveforms | Sine / triangle / square / sawtooth on custom signal names — generic plotter demo | DashboardSignals |
| 16 | plotter_step_response | Square input + 3 EMAs at different τ — designed for the measurement cursors | DashboardSignals |

Copy any example to `C:\ESA\trampoline\opt\devel\`, add `Board.h` + the library files listed, then build with `goil` + `python build.py`. See `examples/README.md` for the full workflow.

## Project structure

```
remote_flasher/
  src/
    main.py                 # Entry point
    main_window.py          # MainWindow, CameraPanel
    lab_config.py           # Board / COM-port / remote-path configuration
    dashboard_backend.py    # Bridges serial signals → HMI Dashboard properties
    port_lock.py            # Lab-wide COM port locking (heartbeat + expiry)
    workers.py              # Background threads (SSH, SCP, SFTP, Serial, Camera)
    serialterm.py           # Bidirectional serial script (runs on remote PC)
    widgets.py              # LogWidget, StatusIndicator
    _version.py             # __version__ (bumped by .bumpversion.toml)
    tabs/
      vpn_tab.py            # VPN connection + Health Check
      flash_tab.py          # Firmware upload + flash (baud-fallback helper)
      can_tab.py            # CAN network configuration + topology
      serial_tab.py         # Multi-serial terminal (up to 4)
      hmi_tab.py            # Automotive HMI Dashboard (QML, 3 modes)
      plotter_tab.py        # Real-time plotter (cursors, stats, Auto-Y)
      ssh_tab.py            # SSH commands + SFTP upload
      setup_tab.py          # Environment setup + IDE guides
    plotter/
      plotter_backend.py    # Parse named/CSV signal lines → ring buffers
      plotter_widget.py     # pyqtgraph scrolling plot + cursors + hover
      signal_list_widget.py # Side panel: color/scale/offset/visibility
      ring_buffer.py        # Fixed-capacity numpy ring buffer
    qml/hmi/                # QML dashboard (Gauge, MiniGauge, GearSelector,
                            # DoorStatus, WarningLights, Electric/CombustionAuto/
                            # CombustionManual modes + shared assets)
  arduino_lib/
    VirtualIO/              # VirtualIO.h / .cpp — buttons, pots, LEDs
    DashboardSignals/       # DashboardSignals.h / .cpp — named-signal helper
  examples/                 # 14 Trampoline RTOS examples (see table above)
  assets/icon.ico
  docs/
    manual.tex              # User manual in pt-BR (compile with tectonic)
    manual.pdf              # Compiled manual
    images/                 # Screenshots for the manual
  setup_environment.py      # Standalone environment setup script
  secrets.example.py        # Template for credentials
  secrets.py                # Your credentials (gitignored)
  requirements.txt
  build_exe.bat
  RemoteFlasher.spec        # PyInstaller build spec
```

## Building the executable

```bash
pip install pyinstaller
build_exe.bat
```

Output: `dist/RemoteFlasher.exe` (~52MB, all dependencies included).

## Documentation

A full user manual in Portuguese (pt-BR) is available at `docs/manual.pdf`. To recompile from source:

```bash
tectonic docs/manual.tex
```

The manual includes:
- Complete usage guide for all tabs (with screenshots)
- Environment setup walkthrough
- Notepad++ and VSCode integration with ready-to-use configurations
- OIL file reference, CAN reference, Board.h pin reference
- Virtual I/O protocol and Arduino library reference
- Practical examples: LED with RTOS alarm, CAN communication with Virtual I/O
- Project creation guide and troubleshooting section

## Dependencies

| Package  | Purpose                    |
|----------|----------------------------|
| PySide6  | Qt6 GUI framework          |
| paramiko | SSH/SFTP connections       |
| requests | HTTP camera feed retrieval |

## Security notes

- SSH credentials are stored in `secrets.py` (gitignored, never committed)
- VPN credentials are optionally saved in `%APPDATA%\RemoteFlasher\settings.json` (base64-obfuscated)
- SSH host keys are auto-accepted on first connection (lab environment)

## License

Developed for academic use at UFPE/CIn as part of the Real-Time Operating Systems course (Residencia Tecnologica).
