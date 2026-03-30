# Remote Firmware Flasher

A PySide6 desktop application for remotely flashing Arduino boards over VPN + SSH. Built for the UFPE/CIn Residencia Tecnologica lab, where students connect to lab PCs via SSTP VPN and flash ATmega328p boards without being physically present.

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
- **Multi-PC Support** — Pre-configured for multiple lab PCs, each with 4 boards
- **First-Run Setup** — New users are prompted to enter their name and remote folder on first launch
- **Auto-create remote folder** — Your folder on the lab PC is created automatically on first use

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

## First Run

On first launch, a setup dialog asks for:
- **Your name** — used to create your folder on the remote PC
- **Remote folder** — auto-filled as `c:\2026\<your_name>`

Settings are saved to `%APPDATA%\RemoteFlasher\settings.json` and persist across sessions. Use the "Clear All Settings" link in the VPN tab to reset.

## Usage

### 1. Connect to VPN

Go to the **VPN** tab, enter your CIn credentials, and click **Connect**. Check **Remember me** to save credentials locally.

### 2. Flash firmware

1. Go to the **Flash** tab
2. Select the target **PC** and **Board**
3. Choose the **ECU port** (COM port on the remote PC)
4. Browse for your `.hex` file
5. Click **Flash** — the app will upload via SCP, reset, flash with avrdude, and report the result

### 3. Monitor serial output

Go to the **Serial** tab, select the COM port, and click **Connect** to see real-time serial output.

### 4. SSH Terminal

Run arbitrary commands on the remote PC for debugging or file management.

### 5. Reset boards

Send reset signals to specific boards using PowerShell scripts on the remote PC.

## Project structure

```
remote-flasher/
  src/
    main.py             # Application entry point and GUI
    lab_config.py       # Board/COM port configuration (imports secrets)
    serialterm.py       # Serial terminal script (runs on remote PC)
  assets/
    icon.ico            # Application icon
  docs/
    manual.tex          # User manual in pt-BR (compile with tectonic)
  secrets.example.py    # Template for credentials
  secrets.py            # Your credentials (gitignored)
  requirements.txt      # Python dependencies
  build_exe.bat         # Build standalone .exe with PyInstaller
  README.md
  .gitignore
```

## Building the executable

```bash
pip install pyinstaller
build_exe.bat
```

Output: `dist/RemoteFlasher.exe` (~52MB, all dependencies included).

## Documentation

A full user manual in Portuguese (pt-BR) is available at `docs/manual.tex`. Compile with:

```bash
tectonic docs/manual.tex
```

## Dependencies

| Package  | Purpose                    |
|----------|----------------------------|
| PySide6  | Qt6 GUI framework          |
| paramiko | SSH/SCP connections        |
| requests | HTTP camera feed retrieval |

## Security notes

- SSH credentials are stored in `secrets.py` (gitignored, never committed)
- VPN credentials are optionally saved in `%APPDATA%\RemoteFlasher\settings.json` (base64-obfuscated)
- SSH host keys are auto-accepted on first connection (lab environment)

## License

Developed for academic use at UFPE/CIn as part of the Real-Time Operating Systems course (Residencia Tecnologica).
