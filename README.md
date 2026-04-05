# Remote Firmware Flasher

A PySide6 desktop application for remotely flashing Arduino boards over VPN + SSH. Built for the UFPE/CIn Residencia Tecnologica lab, where students connect to lab PCs via SSTP VPN and flash ATmega328p boards without being physically present.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Features

- **VPN Connection** — Connect to the lab VPN (SSTP) directly from the app, with auto-detection of existing connections, auto-profile creation, and optional credential saving. Disconnect prompt on exit.
- **Firmware Flashing** — Upload `.hex` files via SCP and flash using `avrdude` over SSH. Streaming output, 30s timeout, and COM port conflict detection with serial panels.
- **Board Reset** — Trigger board reset via AT commands on the MCU control port
- **CAN Network Configuration** — Visual bus topology, per-board CAN1/CAN2 selection via AT commands, quick presets, board detection (AT BI/FV/BV), sequential reliable switching
- **Multi-Serial Terminal** — Up to 4 simultaneous serial connections with spatial layout (side-by-side, 2+1, 2x2 grid), bidirectional send, autoscroll toggle, and port exclusion
- **Virtual I/O** — 4 buttons, 4 LEDs, and 2 potentiometers per serial panel. Buttons and pots send commands to the Arduino; LEDs are controlled by the firmware with brightness scaling. Includes Arduino library (`VirtualIO.h`)
- **SSH Terminal + SFTP Upload** — Run commands and upload files/folders to the remote PC with progress tracking
- **Live Camera** — View the lab camera feed (collapsible side panel, auto-resizes with serial panel count)
- **Environment Setup** — One-click installation of Arduino CLI, AVR Toolchain, Trampoline RTOS, goil, MCP_CAN. Python detection with clear messaging.
- **IDE Integration Guides** — Built-in guides for Notepad++ and VSCode with ready-to-use configurations
- **Multi-PC Support** — Pre-configured for multiple lab PCs, each with 4 boards and CAN selectors

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

### 5. SSH Terminal + File Upload

Run commands on the remote PC and upload files or entire folders via SFTP with a progress bar.

### 6. IDE Integration

The **Setup** tab includes guides for integrating the toolchain with **Notepad++** (NppExec scripts, macros) and **VSCode** (IntelliSense, build tasks, settings).

## Examples

The `examples/` folder contains ready-to-compile Trampoline RTOS projects covering the core course concepts:

| # | Example | Concepts |
|---|---------|----------|
| 01 | blink | Task, Alarm, `TerminateTask()` |
| 02 | multitask | Multiple tasks, priorities, preemption |
| 03 | alarm_dynamic | `SetRelAlarm()`, `CancelAlarm()`, runtime period change |
| 04 | prodcons | `RESOURCE`, `GetResource()`, `ReleaseResource()`, producer-consumer |
| 05 | can_basic | MCP2515 TX + RX, `sendMsgBuf()`, `readMsgBuf()` |
| 06 | virtualio_demo | VirtualIO buttons, pots, LEDs |
| 07 | can_signals | CAN with signal packing, scale conversion, sequence counter |
| 08 | digital_io | Digital read/write with Board.h pins |

Copy any example to `C:\ESA\trampoline\opt\devel\`, add `Board.h`, then build with `goil` + `python build.py`.

## Project structure

```
remote_flasher/
  src/
    main.py             # Entry point
    settings.py         # Persistence (load/save settings)
    workers.py          # Background threads (SSH, SCP, SFTP, Serial, Camera)
    widgets.py          # LogWidget, StatusIndicator
    main_window.py      # MainWindow, CameraPanel
    lab_config.py       # Board/COM port configuration
    serialterm.py       # Bidirectional serial script (runs on remote PC)
    tabs/
      __init__.py       # Re-exports all tabs
      vpn_tab.py        # VPN connection
      flash_tab.py      # Firmware upload + flash
      can_tab.py        # CAN network configuration + topology
      serial_tab.py     # Multi-serial terminal (up to 4)
      ssh_tab.py        # SSH commands + SFTP upload
      setup_tab.py      # Environment setup + IDE guides
  arduino_lib/
    VirtualIO/
      VirtualIO.h       # Virtual I/O Arduino library (header)
      VirtualIO.cpp     # Virtual I/O Arduino library (implementation)
  examples/
    01_blink/           # Task + Alarm basics
    02_multitask/       # Multiple tasks and priorities
    03_alarm_dynamic/   # Runtime alarm period changes
    04_resource_prodcons/ # Shared resources, producer-consumer
    05_can_basic/       # CAN TX + RX
    06_virtualio_demo/  # Virtual I/O buttons, pots, LEDs
    07_can_signals/     # CAN signal packing + sequence counter
    08_digital_io/      # Digital read/write with Board.h
  assets/icon.ico
  docs/
    manual.tex          # User manual in pt-BR (compile with tectonic)
    manual.pdf          # Compiled manual
    images/             # Screenshots for the manual
  setup_environment.py  # Standalone environment setup script
  secrets.example.py    # Template for credentials
  secrets.py            # Your credentials (gitignored)
  requirements.txt
  build_exe.bat
  RemoteFlasher.spec    # PyInstaller build spec
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
