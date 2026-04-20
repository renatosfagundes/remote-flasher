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
from serial.tools import list_ports
import subprocess
import shutil
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force line-buffered stdout. Without this, Python buffers ~4 KB when
# stdout is piped (e.g. over SSH), so a 15-second parallel scan that
# prints only at the end looks stalled — the buffer only flushes after
# enough lines accumulate or the process exits. Reconfigure at import
# so every print() below arrives on the client in real time.
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass  # pre-3.7 — stdout will remain block-buffered over SSH

# Default paths
_DEFAULT_FLASH_PY = r"c:\2026\flash.py"
_DEFAULT_CONF = r"c:\2026\dsf3\avrdude.conf"

# USB VID/PIDs of the lab hardware — matched against `Get-PnpDevice`
# output on PC 217. FT4232H exposes 4 UARTs per chip (1 chip = 1 board).
_FTDI_ECU_VIDPID     = (0x0403, 0x6011)
_PROLIFIC_RESET_VIDPID = (0x0A05, 0x7211)

# Fallback hardcoded defaults (PC 220 mapping). Used only when
# auto-discovery finds nothing AND --reset-ports / --ecu-ports aren't
# passed on the command line.
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


def _discover_ecus():
    """All currently connected FTDI FT4232H channel ports, sorted."""
    ports = [p.device for p in list_ports.comports()
             if (p.vid, p.pid) == _FTDI_ECU_VIDPID]
    return sorted(ports, key=lambda s: int(s.replace("COM", "")))


def _discover_resets():
    """Prolific reset-helper ports, sorted. Numbered sequentially as
    Placa 01 / 02 / ... — run the reset-observation loop to confirm
    which physical board each one actually drives."""
    ports = sorted(
        (p.device for p in list_ports.comports()
         if (p.vid, p.pid) == _PROLIFIC_RESET_VIDPID),
        key=lambda s: int(s.replace("COM", "")),
    )
    return {f"Placa 0{i+1}": com for i, com in enumerate(ports)}


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
        # DON'T taskkill /im avrdude.exe here — parallel scans run many
        # avrdudes concurrently, so killing them all-by-name would abort
        # the sibling attempts that are still trying to sync. Let this
        # call's subprocess.run time out and kill only its own child.
        return "TIMEOUT"
    except Exception as e:
        return f"error: {e}"


def try_flash_parallel(avrdude, conf, ecu_ports, reset_port, hex_file,
                       delay=0.4, timeout_sec=8):
    """Pulse reset once, launch avrdude on ALL candidate ECUs in parallel.

    The reset helper on a board pulses all of its 4 ATmegas simultaneously,
    so the 4 bootloaders open at the same moment. Running 16 avrdudes in
    parallel lets the 4 reset ECUs sync inside that window while the other
    12 fall through 'not in sync' quickly — total time ≈ max(single attempt)
    instead of sum(all attempts).

    Prints per-port results as each future completes, so the caller sees
    live progress over SSH rather than a silent stall followed by a burst.

    Returns {ecu_port: result_string}.
    """
    results: dict[str, str] = {}

    def _flash(p):
        return p, try_flash_avrdude(avrdude, conf, p, hex_file, timeout_sec)

    print(f"  → launching {len(ecu_ports)} avrdudes in parallel...", flush=True)
    with ThreadPoolExecutor(max_workers=len(ecu_ports)) as ex:
        futures = [ex.submit(_flash, p) for p in ecu_ports]
        # Give the thread pool a beat to schedule all tasks, then pulse
        # reset. 150 ms is enough for 16 Popen() calls on Windows, so
        # stk500_getsync is already hitting the UART when the bootloader
        # wakes up — avoids losing the window on slow-to-start processes.
        time.sleep(0.15)
        print(f"  → pulsing reset on {reset_port}...", flush=True)
        reset_board(reset_port)
        time.sleep(delay)
        print(f"  → waiting for results (timeout {timeout_sec}s per port):", flush=True)
        for fut in as_completed(futures):
            port, result = fut.result()
            results[port] = result
            # Stream as soon as each avrdude finishes — parallel runs
            # finish out of port order, which is fine for progress.
            tag = "✓" if result == "SUCCESS" else " "
            print(f"  {tag} {port}: {result}", flush=True)
    return results


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
    parser.add_argument("--reset-ports", default=None,
                        help="Override reset ports (e.g. 'Placa 01=COM59,Placa 02=COM60'). "
                             "Skip to auto-discover via Prolific USB VID/PID.")
    parser.add_argument("--ecu-ports", default=None,
                        help="Override ECU candidate ports (comma-separated, e.g. "
                             "'COM17,COM18,...'). Skip to auto-discover via FTDI USB VID/PID.")
    parser.add_argument("--no-auto", action="store_true",
                        help="Disable USB-VID/PID auto-discovery; use the hardcoded "
                             "PC-220 defaults in the source.")
    parser.add_argument("--sequential", action="store_true",
                        help="Flash ECUs one at a time (slow; ~16× slower than default). "
                             "Default is parallel: one reset pulse, all 16 avrdudes at once — "
                             "the 4 actually reset by that helper succeed, the other 12 "
                             "fail fast with 'not in sync'.")
    args = parser.parse_args()

    # Resolve reset ports + ECU candidates.
    # Priority: explicit CLI > auto-discover (unless --no-auto) > hardcoded defaults.
    global RESET_PORTS, ECU_CANDIDATES
    if args.reset_ports:
        RESET_PORTS = dict(
            (k.strip(), v.strip())
            for k, v in (pair.split("=", 1) for pair in args.reset_ports.split(","))
        )
    elif not args.no_auto:
        discovered = _discover_resets()
        if discovered:
            RESET_PORTS = discovered
    if args.ecu_ports:
        ECU_CANDIDATES = [p.strip() for p in args.ecu_ports.split(",")]
    elif not args.no_auto:
        discovered = _discover_ecus()
        if discovered:
            ECU_CANDIDATES = discovered

    # Parallel mode (default, fast) always uses raw avrdude — can't run
    # multiple flash.py's against the same board since each would issue
    # its own competing reset. --sequential keeps the existing flash.py
    # option open for per-port debugging.
    use_flash_py = (not args.no_flash_py) and args.sequential

    # Validate paths
    if use_flash_py:
        if not os.path.isfile(args.flash_py):
            print(f"flash.py not found at {args.flash_py}")
            print("  Pass --flash-py <path> or use --no-flash-py for raw avrdude mode.")
            sys.exit(1)
        avrdude = None
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

    if args.sequential:
        mode_str = (f"flash.py ({args.flash_py})" if use_flash_py
                    else f"avrdude ({avrdude}) [sequential]")
    else:
        mode_str = f"avrdude ({avrdude}) [PARALLEL: 1 reset → all ECUs at once]"
    print("=" * 60)
    print("  ANEB Board Port Scanner")
    print("=" * 60)
    print(f"  mode:    {mode_str}")
    print(f"  hex:     {args.hex}")
    print(f"  boards:  {', '.join(boards_to_scan.keys())}")
    print(f"  ecus:    {', '.join(ECU_CANDIDATES)}  ({len(ECU_CANDIDATES)} ports)")
    print(f"  delay:   {args.delay}s")
    print(f"  timeout: {args.timeout}s per port")
    print("=" * 60)
    print()

    results = {}

    for board_name, reset_port in boards_to_scan.items():
        print(f"=== {board_name} (reset: {reset_port}) ===")
        results[board_name] = []

        if not args.sequential:
            # Parallel: one reset, all ECUs flash in parallel.
            # Per-port lines stream live from try_flash_parallel itself.
            t0 = time.monotonic()
            per_port = try_flash_parallel(
                avrdude, args.conf, ECU_CANDIDATES, reset_port, args.hex,
                delay=args.delay, timeout_sec=args.timeout,
            )
            elapsed = time.monotonic() - t0
            for ecu in ECU_CANDIDATES:
                if per_port.get(ecu) == "SUCCESS":
                    results[board_name].append(ecu)
            print(f"  (parallel scan took {elapsed:.1f}s)", flush=True)
        else:
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
