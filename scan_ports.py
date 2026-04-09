"""
Scan COM port mapping for ANEB boards.
Run on the lab PC (locally or via SSH).

Two modes:
  --flash-py (default): uses flash.py which handles reset+flash with precise timing.
  --no-flash-py:        uses raw avrdude + separate AT RT reset (for PCs without flash.py).

Usage:
    python scan_ports.py --hex firmware.hex
    python scan_ports.py --hex firmware.hex --boards 1
    python scan_ports.py --hex firmware.hex --boards 1,4
    python scan_ports.py --hex firmware.hex --no-flash-py   # raw avrdude mode
"""
import argparse
import serial
import subprocess
import shutil
import time
import sys
import os

# Default paths
_DEFAULT_FLASH_PY = r"c:\2026\flash.py"
_DEFAULT_CONF = r"c:\2026\dsf3\avrdude.conf"

RESET_PORTS = {
    "Placa 01": "COM31",
    "Placa 02": "COM32",
    "Placa 03": "COM33",
    "Placa 04": "COM34",
}

ECU_CANDIDATES = [
    "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "COM10",
    "COM11", "COM12", "COM13", "COM14", "COM15", "COM16", "COM17", "COM18",
]


# ---------------------------------------------------------------------------
# flash.py mode — reset + flash with precise timing (PC 220)
# ---------------------------------------------------------------------------

def try_flash_py(flash_py, reset_port, ecu_port, hex_file, delay=0.4, timeout_sec=15):
    """Use flash.py which handles reset+flash internally with precise timing."""
    cmd = [
        "python", "-u", flash_py,
        "--reset_port", reset_port,
        "--flash_port", ecu_port,
        "--hex", hex_file,
        "--delay", str(delay),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout_sec)
        output = (result.stdout.decode("cp850", errors="replace") +
                  result.stderr.decode("cp850", errors="replace"))
        return _classify_output(output)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/f", "/im", "avrdude.exe"],
                       capture_output=True)
        return "TIMEOUT"
    except Exception as e:
        return f"error: {e}"


# ---------------------------------------------------------------------------
# Raw avrdude mode — separate reset + avrdude (PCs with reset scripts)
# ---------------------------------------------------------------------------

def reset_board(reset_port):
    """Send AT RT to reset a board."""
    try:
        s = serial.Serial(reset_port, 19200, timeout=1)
        time.sleep(0.2)
        s.write(b"AT RT\r\n")
        time.sleep(0.2)
        s.close()
        return True
    except Exception as e:
        print(f"  Reset {reset_port} failed: {e}")
        return False


def try_flash_avrdude(avrdude, conf, ecu_port, hex_file, timeout_sec=10):
    """Try to flash a port directly with avrdude (after external reset)."""
    cmd = [
        avrdude, "-C", conf,
        "-p", "atmega328p", "-c", "arduino",
        "-b", "57600", "-P", ecu_port,
        "-U", f"flash:w:{hex_file}:i",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout_sec)
        output = result.stderr.decode("cp850", errors="replace")
        return _classify_output(output)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/f", "/im", "avrdude.exe"],
                       capture_output=True)
        return "TIMEOUT"
    except Exception as e:
        return f"error: {e}"


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

def _classify_output(output):
    """Classify avrdude output into a short result string."""
    low = output.lower()
    if "verified" in low:
        return "SUCCESS"
    if "not in sync" in low:
        return "no-sync"
    if "denied" in low or "access" in low:
        return "port-busy"
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    return lines[-1][:60] if lines else "unknown"


def main():
    parser = argparse.ArgumentParser(description="Scan COM port mapping for ANEB boards")
    parser.add_argument("--hex", required=True, help="Path to test .hex firmware file")
    parser.add_argument("--flash-py", default=_DEFAULT_FLASH_PY,
                        help=f"Path to flash.py (default: {_DEFAULT_FLASH_PY})")
    parser.add_argument("--no-flash-py", action="store_true",
                        help="Use raw avrdude + AT RT reset instead of flash.py")
    parser.add_argument("--avrdude", default=None,
                        help="Path to avrdude.exe (default: search PATH)")
    parser.add_argument("--conf", default=_DEFAULT_CONF,
                        help=f"Path to avrdude.conf (default: {_DEFAULT_CONF})")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Delay between reset and flash in seconds (default: 0.4)")
    parser.add_argument("--boards", default=None,
                        help="Comma-separated board numbers to scan (e.g. 1,4). Default: all")
    parser.add_argument("--timeout", type=int, default=15,
                        help="Timeout per flash attempt in seconds (default: 15)")
    args = parser.parse_args()

    use_flash_py = not args.no_flash_py

    # Validate paths
    if use_flash_py:
        if not os.path.isfile(args.flash_py):
            print(f"flash.py not found at {args.flash_py}")
            print("  Pass --flash-py <path> or use --no-flash-py for raw avrdude mode.")
            sys.exit(1)
    else:
        avrdude = args.avrdude or shutil.which("avrdude") or shutil.which("avrdude.exe")
        if not avrdude or not os.path.isfile(avrdude):
            print("avrdude not found. Install it or pass --avrdude <path>.")
            sys.exit(1)
        if not os.path.isfile(args.conf):
            print(f"avrdude.conf not found at {args.conf}")
            sys.exit(1)

    if not os.path.isfile(args.hex):
        print(f"Hex file not found at {args.hex}")
        sys.exit(1)

    # Filter boards
    if args.boards:
        board_nums = [int(x.strip()) for x in args.boards.split(",")]
        boards_to_scan = {f"Placa 0{n}": RESET_PORTS[f"Placa 0{n}"]
                          for n in board_nums if f"Placa 0{n}" in RESET_PORTS}
    else:
        boards_to_scan = dict(RESET_PORTS)

    mode_str = f"flash.py ({args.flash_py})" if use_flash_py else f"avrdude ({avrdude})"
    print("=" * 60)
    print("  ANEB Board Port Scanner")
    print("=" * 60)
    print(f"  mode:    {mode_str}")
    print(f"  hex:     {args.hex}")
    print(f"  boards:  {', '.join(boards_to_scan.keys())}")
    print(f"  delay:   {args.delay}s")
    print(f"  timeout: {args.timeout}s per port")
    print("=" * 60)
    print()

    results = {}

    for board_name, reset_port in boards_to_scan.items():
        print(f"=== {board_name} (reset: {reset_port}) ===")
        results[board_name] = []

        for ecu in ECU_CANDIDATES:
            sys.stdout.write(f"  {ecu}: ")
            sys.stdout.flush()

            if use_flash_py:
                # flash.py handles reset internally with precise timing
                result = try_flash_py(
                    args.flash_py, reset_port, ecu, args.hex,
                    delay=args.delay, timeout_sec=args.timeout,
                )
            else:
                # Manual reset then avrdude
                if not reset_board(reset_port):
                    print(f"  Skipping {board_name} -- reset port not available")
                    break
                time.sleep(args.delay)
                result = try_flash_avrdude(
                    avrdude, args.conf, ecu, args.hex,
                    timeout_sec=args.timeout,
                )

            print(result)
            if result == "SUCCESS":
                results[board_name].append(ecu)

        print()

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for board_name, ports in results.items():
        reset_port = boards_to_scan[board_name]
        if ports:
            print(f"  {board_name} (reset {reset_port}): ECUs = {', '.join(ports)}")
        else:
            print(f"  {board_name} (reset {reset_port}): no ECUs found")

    print()
    print("Copy this into lab_config.py for PC 220:")
    print()
    for board_name, ports in results.items():
        reset_port = boards_to_scan[board_name]
        ports_str = str(ports) if ports else "[]"
        print(f'    "{board_name}": {{')
        print(f'        "ecu_ports": {ports_str},')
        print(f'        "reset_port": "{reset_port}",')
        print(f'        "reset_script": None,')
        print(f'        "can_selector_port": "{reset_port}",')
        print(f'    }},')


if __name__ == "__main__":
    main()
