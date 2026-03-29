# Remote Firmware Flasher

A PySide6 desktop application for remotely flashing Arduino boards over VPN + SSH. Built for the UFPE/CIn Embedded Systems lab, where students connect to lab PCs via SSTP VPN and flash ATmega328p boards without being physically present.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Features

- **VPN Connection** — Connect to the lab VPN (SSTP) directly from the app, with optional credential saving
- **Firmware Flashing** — Upload `.hex` files via SCP and flash using `avrdude` over SSH
- **Board Reset** — Trigger board reset via PowerShell scripts on the remote PC
- **Serial Terminal** — Monitor serial output from the boards in real-time over SSH
- **SSH Terminal** — Run arbitrary commands on the remote lab PCs
- **Live Camera** — View the lab camera feed to see boards reacting to your commands (collapsible side panel)
- **Multi-PC Support** — Pre-configured for 4 lab PCs (172.20.36.217–221), each with 4 boards
- **First-Run Setup** — New users are prompted to enter their name and remote folder on first launch

## Screenshots

The application has a tabbed interface with VPN, Flash, Serial, SSH Terminal, and Reset tabs, with an optional camera panel on the right side.

## Prerequisites

### Option 1: Run from source

- Python 3.9+
- Windows 10/11
- VPN connection configured (SSTP to `vpn.cin.ufpe.br`)

### Option 2: Run the standalone executable

- Windows 10/11
- No Python installation needed

## Installation

### From source

```bash
git clone https://github.com/renatosfagundes/remote-flasher.git
cd remote-flasher
pip install -r requirements.txt
python main.py
```

### Standalone executable

Download `RemoteFlasher.exe` from the [Releases](https://github.com/renatosfagundes/remote-flasher/releases) page and run it. No installation required.

## First Run

On first launch, a setup dialog asks for:
- **Your name** — used to create your folder on the remote PC
- **Remote folder** — auto-filled as `c:\2026\<your_name>`

Settings are saved to `%APPDATA%\RemoteFlasher\settings.json` and persist across sessions.

## Usage

### 1. Connect to VPN

Go to the **VPN** tab, enter your credentials, and click **Connect**. Check **Remember me** to save credentials locally (stored in AppData, base64-obfuscated).

### 2. Flash firmware

1. Go to the **Flash** tab
2. Select the target **PC** and **Board**
3. Choose the **ECU port** (COM port on the remote PC)
4. Browse for your `.hex` file
5. Click **Flash** — the app will:
   - Upload the hex file via SCP
   - Reset the board
   - Flash using avrdude
   - Report success/failure

### 3. Monitor serial output

Go to the **Serial** tab, select the COM port, and click **Connect** to see real-time serial output from the board.

### 4. SSH Terminal

The **SSH Terminal** tab lets you run arbitrary commands on the remote PC for debugging or file management.

### 5. Reset boards

The **Reset** tab sends reset signals to specific boards using PowerShell scripts on the remote PC.

## Configuration

### Lab hardware (`lab_config.py`)

The lab configuration (PCs, boards, COM ports, camera URLs) is defined in `lab_config.py`. Edit this file to match your lab setup:

```python
COMPUTERS = {
    "PC 217 (172.20.36.217)": {
        "host": "172.20.36.217",
        "user": "residencia",
        "password": "...",
        "camera_url": "http://172.20.36.217:8080/video_feed",
        "flash_method": "avrdude",
        "boards": {
            "Placa 01": {
                "ecu_ports": ["COM25", "COM26", "COM27", "COM28"],
                "reset_port": "COM57",
                "reset_script": "reset_placa_01.ps1",
            },
            # ...
        },
    },
}
```

### User settings (`%APPDATA%\RemoteFlasher\settings.json`)

Per-user settings (VPN credentials, remote folder) are stored in AppData and never committed to the repository.

## Building the executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build (or run build_exe.bat)
pyinstaller --onefile --windowed --name "RemoteFlasher" --icon "icon.ico" --add-data "icon.ico;." --add-data "lab_config.py;." --add-data "serialterm.py;." --hidden-import paramiko --hidden-import requests main.py
```

The output is at `dist/RemoteFlasher.exe` (~52MB, includes all dependencies).

## Project structure

```
remote_flasher/
  main.py           # Application entry point and all GUI code
  lab_config.py     # Lab hardware configuration (PCs, boards, ports)
  serialterm.py     # Serial terminal helper script (runs on remote PC)
  icon.ico          # Application icon
  requirements.txt  # Python dependencies
  build_exe.bat     # Script to build standalone .exe
  .gitignore        # Excludes credentials, build artifacts, caches
```

## Dependencies

| Package  | Purpose                     |
|----------|-----------------------------|
| PySide6  | Qt6 GUI framework           |
| paramiko | SSH/SCP connections         |
| requests | HTTP camera feed retrieval  |

## Security notes

- VPN and SSH credentials are stored locally in `%APPDATA%\RemoteFlasher\settings.json`
- Passwords are base64-encoded (obfuscated, not encrypted) — this prevents accidental plain-text exposure but is not secure storage
- The `.gitignore` excludes all credential/settings files from version control
- SSH host keys are auto-accepted on first connection (lab environment)

## License

This project was developed for academic use at UFPE/CIn as part of the Real-Time Operating Systems course.
