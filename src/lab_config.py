"""
Lab hardware configuration — computers, boards, COM ports.
Sensitive data (IPs, credentials) are imported from secrets.py at the project root.
Copy secrets.example.py to secrets.py and fill in your lab's values.
"""
import re
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
    f"PC 217 ({SSH_HOSTS['PC 217']['host']})": _pc("PC 217", "flash.py", {
        "Placa 01": {
            "ecu_ports": ["COM25", "COM26", "COM27", "COM28"],
            "reset_port": "COM57",
            "reset_script": "reset.ps1",
            "can_selector_port": "COM57",
        },
        "Placa 02": {
            "ecu_ports": ["COM29", "COM30", "COM31", "COM32"],
            "reset_port": "COM63",
            "reset_script": "reset.ps1",
            "can_selector_port": "COM63",
        },
        "Placa 03": {
            "ecu_ports": ["COM33", "COM34", "COM35", "COM36"],
            "reset_port": "COM59",
            "reset_script": "reset.ps1",
            "can_selector_port": "COM59",
        },
        "Placa 04": {
            "ecu_ports": ["COM17", "COM18", "COM19", "COM20"],
            "reset_port": "COM60",
            "reset_script": "reset.ps1",
            "can_selector_port": "COM60",
        },
    }),
    f"PC 220 ({SSH_HOSTS['PC 220']['host']})": _pc("PC 220", "flash.py", {
        "Placa 01": {
            "ecu_ports": ["COM3", "COM4", "COM5", "COM6"],
            "reset_port": "COM31",
            "reset_script": None,
            "can_selector_port": "COM31",
        },
        "Placa 02": {
            "ecu_ports": ["COM15", "COM16", "COM17", "COM18"],
            "reset_port": "COM32",
            "reset_script": None,
            "can_selector_port": "COM32",
        },
        "Placa 03": {
            "ecu_ports": ["COM11", "COM12", "COM13", "COM14"],
            "reset_port": "COM33",
            "reset_script": None,
            "can_selector_port": "COM33",
        },
        "Placa 04": {
            "ecu_ports": ["COM7", "COM8", "COM9", "COM10"],
            "reset_port": "COM39",
            "reset_script": None,
            "can_selector_port": None,  # not responding
        },
    }),
}

# Default avrdude parameters.
# Baudrate 115200 matches Optiboot (current ECU bootloader) per
# JigaAppCmd.properties → ecu.new.baudrate=115200. The old value of 57600
# was for the legacy bootloader; using it with Optiboot produces silent
# sync failures (resp=0x00 on every attempt).
AVRDUDE_DEFAULTS = {
    "programmer": "arduino",
    "mcu": "atmega328p",
    "baudrate": "115200",
    "config_file": "avrdude.conf",
}

# Default serial terminal settings
SERIAL_DEFAULTS = {
    "baudrate": "115200",
}


# Apply cached port overrides (last values fetched from PC 217's ports.json).
# Kept at the bottom so COMPUTERS is fully built before we mutate it.
try:
    from ports_sync import load_cache, apply_overrides
    _cached = load_cache()
    if _cached:
        apply_overrides(COMPUTERS, _cached)
except Exception:
    # Never let cache load break the app — fall back to lab_config defaults.
    pass


# -------------------------------------------------------------------------
# aneb-sim simulator integration (optional, Windows-only).
#
# When the aneb-sim simulator is set up on the local machine
# (scripts\setup_com.bat run, com0com pairs created with friendly names),
# expose it as a 'Localhost (aneb-sim)' computer entry so the existing
# Flash / Serial / CAN tabs can target it just like a real lab PC.
#
# Discovery is via the Windows registry: HKLM\SYSTEM\CurrentControlSet\
# Enum\COM0COM\PORT\<CNCBn>\FriendlyName values like 'ECU1 (aneb-sim)'
# are mapped back to chip names.  Boards / ECU layout matches the
# aneb-sim hardware model (1 ANEB v1.1 board = 4 ECUs + 1 MCU + 1 CAN
# bus); when future aneb-sim builds expose multiple physical-board
# models the loop below extends naturally to additional Placa entries.
#
# flash_method='local' is a new mode handled by tabs/flash_tab.py and
# friends — they bypass SSH/SCP and run avrdude/pyserial directly.
# -------------------------------------------------------------------------

def _localhost_simulator():
    """Return a COMPUTERS-style entry for the aneb-sim simulator if it's
    installed on this machine, or None.

    Friendly-name parsing is strict: only ports tagged 'ECU<n> (aneb-sim)'
    or 'MCU (aneb-sim)' (the user-side ports — the bridge-side
    'ECU1 (aneb-sim bridge)' ports are deliberately ignored)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    chip_to_com: dict[str, str] = {}
    base = r"SYSTEM\CurrentControlSet\Enum\COM0COM\PORT"
    name_re = re.compile(r"^([A-Za-z]+\d*)\s+\(aneb-sim\)\s*$")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as port:
                        friendly, _ = winreg.QueryValueEx(port, "FriendlyName")
                        with winreg.OpenKey(port, "Device Parameters") as dp:
                            com, _ = winreg.QueryValueEx(dp, "PortName")
                except OSError:
                    continue
                m = name_re.match(friendly)
                if m:
                    chip_to_com[m.group(1).upper()] = com
    except OSError:
        return None

    ecu_ports = [chip_to_com.get(f"ECU{i}") for i in (1, 2, 3, 4)]
    if not all(ecu_ports):
        # Setup is incomplete (e.g. setup_com.bat hasn't been run yet,
        # or pyserial / com0com isn't installed).  Skip the entry —
        # better to omit it than expose a half-broken target.
        return None

    # The simulator's UART servers listen on TCP 8600..8604 for ECU1..ECU4
    # and MCU respectively.  Flashing goes through direct TCP (avrdude
    # supports `-P net:host:port`) instead of the COM port — opening the
    # TCP socket triggers reset-on-connect on the sim, which the com0com
    # path can't because the aneb-sim UI's bridge holds a persistent TCP
    # connection that masks new-client events.
    UART_BASE_TCP = 8600
    ecu_tcp_ports = [UART_BASE_TCP + i for i in range(4)]

    return {
        "host": "127.0.0.1",
        "user": "",
        "password": "",
        "camera_url": "",
        # New flash_method handled by flash_tab/serial_tab/can_tab —
        # runs avrdude / pyserial locally instead of via SSH.
        "flash_method": "local",
        "boards": {
            "Placa 01 (aneb-sim)": {
                "ecu_ports": ecu_ports,
                # Parallel list — ecu_tcp_ports[i] is the simulator's
                # TCP UART port for ecu_ports[i].  flash_tab uses this
                # to bypass com0com entirely during avrdude.
                "ecu_tcp_ports": ecu_tcp_ports,
                # No separate reset port on the sim — chip reset is
                # triggered by opening a fresh TCP socket to the chip's
                # UART server (see flash_tab._local_reset).  Leaving
                # this None keeps the preflight from locking the wrong
                # port: a hardcoded value here was previously aliasing
                # to ecu_ports[0] (COM11) and rejecting flashes of
                # ECU2/3/4 whenever a serial tab held COM11.
                "reset_port": None,
                "reset_script": None,
                # CAN bus selection is a no-op on the sim (only one
                # bus today).  Use the MCU port as a placeholder so
                # the AT-command flow in can_tab doesn't crash on
                # missing keys; the local branch in can_tab returns
                # immediately for flash_method=='local'.
                "can_selector_port": chip_to_com.get("MCU", ecu_ports[0]),
            }
        },
    }


_sim_pc = _localhost_simulator()
if _sim_pc:
    COMPUTERS["Localhost (aneb-sim)"] = _sim_pc
