"""
Lab hardware configuration — computers, boards, COM ports.
Sensitive data (IPs, credentials) are imported from secrets.py at the project root.
Copy secrets.example.py to secrets.py and fill in your lab's values.
"""
import sys
import os

# Add project root to path so we can import secrets.py from there
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from secrets import SSH_HOSTS, VPN_ADDRESS
except ImportError:
    print(
        "ERROR: secrets.py not found.\n"
        "Copy secrets.example.py to secrets.py and fill in your lab's credentials.\n"
    )
    sys.exit(1)

# Base directory on the remote PCs where serialterm.py and flash.py live.
REMOTE_BASE_DIR = r"c:\2026"

# Directory with reset scripts and avrdude.conf
REMOTE_SCRIPTS_DIR = r"c:\2026\dsf3"

# Default user folder on the remote PCs (overridden by first-run setup)
REMOTE_USER_DIR = r"c:\2026"


def _pc(key, flash_method, boards):
    """Build a COMPUTERS entry by merging secrets with board config."""
    info = SSH_HOSTS[key]
    return {
        "host": info["host"],
        "user": info["user"],
        "password": info["password"],
        "camera_url": info.get("camera_url", ""),
        "flash_method": flash_method,
        "boards": boards,
    }


# Each computer in the lab with its boards and COM port mappings
COMPUTERS = {
    f"PC 217 ({SSH_HOSTS['PC 217']['host']})": _pc("PC 217", "avrdude", {
        "Placa 01": {
            "ecu_ports": ["COM25", "COM26", "COM27", "COM28"],
            "reset_port": "COM57",
            "reset_script": "reset_placa_01.ps1",
        },
        "Placa 02": {
            "ecu_ports": ["COM13", "COM14", "COM15", "COM16"],
            "reset_port": "COM58",
            "reset_script": "reset_placa_02.ps1",
        },
        "Placa 03": {
            "ecu_ports": ["COM33", "COM34", "COM35", "COM36"],
            "reset_port": "COM59",
            "reset_script": "reset_placa_03.ps1",
        },
        "Placa 04": {
            "ecu_ports": ["COM53", "COM54", "COM55", "COM56"],
            "reset_port": "COM60",
            "reset_script": "reset_placa_04.ps1",
        },
    }),
    f"PC 218 ({SSH_HOSTS['PC 218']['host']})": _pc("PC 218", "avrdude", {
        "Placa 01": {
            "ecu_ports": ["COM13", "COM14", "COM15", "COM16"],
            "reset_port": None,
            "reset_script": None,
        },
        "Placa 02": {
            "ecu_ports": ["COM17", "COM18", "COM19", "COM20"],
            "reset_port": None,
            "reset_script": None,
        },
        "Placa 03": {
            "ecu_ports": ["COM21", "COM22", "COM23", "COM24"],
            "reset_port": None,
            "reset_script": None,
        },
        "Placa 04": {
            "ecu_ports": ["COM25", "COM26", "COM27", "COM28"],
            "reset_port": None,
            "reset_script": None,
        },
    }),
    f"PC 220 ({SSH_HOSTS['PC 220']['host']})": _pc("PC 220", "flash.py", {
        "Placa 01": {
            "ecu_ports": ["COM35", "COM36", "COM37", "COM38"],
            "reset_port": "COM31",
            "reset_script": None,
        },
        "Placa 02": {
            "ecu_ports": ["COM15", "COM16", "COM17", "COM18"],
            "reset_port": "COM32",
            "reset_script": None,
        },
        "Placa 03": {
            "ecu_ports": ["COM11", "COM12", "COM13", "COM14"],
            "reset_port": "COM33",
            "reset_script": None,
        },
        "Placa 04": {
            "ecu_ports": ["COM7", "COM8", "COM9", "COM10"],
            "reset_port": "COM34",
            "reset_script": None,
        },
    }),
    f"PC 221 ({SSH_HOSTS['PC 221']['host']})": _pc("PC 221", "avrdude", {
        "Placa 01": {
            "ecu_ports": ["COM54", "COM55", "COM56", "COM57"],
            "reset_port": None,
            "reset_script": None,
        },
        "Placa 02": {
            "ecu_ports": ["COM50", "COM51", "COM52", "COM53"],
            "reset_port": None,
            "reset_script": None,
        },
        "Placa 03": {
            "ecu_ports": ["COM42", "COM43", "COM44", "COM45"],
            "reset_port": None,
            "reset_script": None,
        },
        "Placa 04": {
            "ecu_ports": ["COM46", "COM47", "COM48", "COM49"],
            "reset_port": None,
            "reset_script": None,
        },
    }),
}

# Default avrdude parameters
AVRDUDE_DEFAULTS = {
    "programmer": "arduino",
    "mcu": "atmega328p",
    "baudrate": "57600",
    "config_file": "avrdude.conf",
}

# Default serial terminal settings
SERIAL_DEFAULTS = {
    "baudrate": "115200",
}
