"""
Bidirectional serial terminal — reads from a COM port and prints to stdout,
reads from stdin and writes to the COM port.
Designed to run on the remote lab PCs over SSH.

Usage:
    python serialterm.py --port COM25 --baudrate 115200
"""
import argparse
import io
import os
import subprocess
import sys
import threading
import time
import serial


# Force UTF-8 output so non-ASCII characters from the Arduino (e.g. em-dash,
# degree signs, accented text) don't crash the reader on Windows hosts that
# default to cp1252 stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:  # pre-3.7 fallback
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# Module-level shutdown flag. Set from the main thread's finally-block
# so the reader thread can observe it and exit its readline() loop
# cleanly *before* ser.close() runs on the main thread — avoiding the
# pyserial race where close() nulls out _overlapped_read while the
# reader is mid-read, leaking the COM handle on Windows.
_stop = threading.Event()


def _reader(ser):
    """Read from serial and print to stdout.

    Also flushes stdout every iteration even when no data arrives — if the
    SSH channel was closed (Close Serial on the client), the next flush
    will raise BrokenPipeError (OSError) and break us out of the loop,
    which signals the main thread to shut down and release the COM port.
    Without this periodic flush, an idle Arduino → no prints → pipe break
    goes unnoticed → python lingers → COM port stays held → Acesso Negado
    on the next Open Serial.
    """
    try:
        while not _stop.is_set():
            data = ser.readline()
            if data:
                try:
                    text = data.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    text = repr(data)
                try:
                    print(text)
                except UnicodeEncodeError:
                    print(text.encode("ascii", errors="replace").decode("ascii"))
            sys.stdout.flush()
    except (serial.SerialException, OSError):
        pass


def _writer(ser):
    """Read from stdin and write to serial.

    Recognizes a special `__RF_QUIT__` marker from the Remote Flasher
    client: when Close Serial is clicked, the client sends that line and
    we trigger a clean shutdown here (set _stop + cancel pyserial's
    blocking read) so main's finally runs ser.close() promptly — without
    the client having to Force-kill us (which leaves the FTDI USB endpoint
    half-released and disturbs the camera bus on the next cycle).
    """
    try:
        buf = ""
        while not _stop.is_set():
            ch = sys.stdin.read(1)
            if not ch:
                break
            if ch in ("\n", "\r"):
                if buf == "__RF_QUIT__":
                    _stop.set()
                    try:
                        ser.cancel_read()
                    except Exception:
                        pass
                    break
                if buf:
                    ser.write((buf + "\r\n").encode("utf-8"))
                    ser.flush()
                buf = ""
            else:
                buf += ch
    except (serial.SerialException, OSError, EOFError):
        pass


def _reap_port_holders(port: str):
    """Kill any OTHER process still holding the requested COM port.

    "Acesso negado" on open is almost always a prior serialterm.py that
    died ungracefully OR an avrdude from a failed/cancelled flash that
    never got to close its -P handle. Rather than waiting up to 5 min
    for the scheduled janitor to notice, reap either holder inline so
    the retry below can succeed.

    Port-scoped: only matches serialterm/avrdude bound to this exact COM.
    Excludes self via $me. Camera pythons (no 'serialterm' in args) are
    never matched, so the reap can't accidentally kill the webcam feed.

    Note: with the Remote Flasher client's cooperative shutdown
    (`__RF_QUIT__` marker + channel close, no Force kill), this reap
    should essentially never fire in normal use. It's kept as a safety
    net for (a) avrdude crashes during flash and (b) legacy Flasher
    versions that still Force-kill.
    """
    my_pid = os.getpid()
    script = (
        "$me = %d; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        "  $_.ProcessId -ne $me -and $_.CommandLine -and ("
        "    ($_.CommandLine -like '*serialterm*' -and "
        "     $_.CommandLine -match '--port\\s+%s\\b') -or "
        "    ($_.Name -eq 'avrdude.exe' -and "
        "     $_.CommandLine -match '-P\\s+%s\\b')"
        "  )"
        "} | ForEach-Object { "
        "  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
        "}"
    ) % (my_pid, port, port)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=5, capture_output=True,
        )
    except Exception:
        pass


def _open_port_with_retry(port: str, baudrate: int):
    """Open port; on 'Acesso negado' / PermissionError, reap stale
    holders and retry once. Returns the open Serial or raises."""
    try:
        return serial.Serial(port, baudrate, timeout=1)
    except serial.SerialException as e:
        msg = str(e).lower()
        denied = (
            "acesso negado" in msg
            or "access is denied" in msg
            or "permissionerror" in msg
            or "permission" in msg
        )
        if not denied:
            raise
        print(
            f"[serialterm] {port} denied — reaping stale serialterm holders and retrying...",
            flush=True,
        )
        _reap_port_holders(port)
        # Give the OS ~1.5 s to finalize the handle release after Stop-Process;
        # FTDI drivers sometimes take a moment to drop the last reference.
        time.sleep(1.5)
        return serial.Serial(port, baudrate, timeout=1)


def main():
    parser = argparse.ArgumentParser(description="Bidirectional serial terminal")
    parser.add_argument("--port", required=True, help="COM port (e.g. COM25)")
    parser.add_argument("--baudrate", type=int, default=115200, help="Baud rate")
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baudrate} baud...")
    sys.stdout.flush()

    try:
        ser = _open_port_with_retry(args.port, args.baudrate)
    except serial.SerialException as e:
        print(f"ERROR: Could not open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to {args.port}. Reading... (type to send)")
    sys.stdout.flush()

    reader_thread = threading.Thread(target=_reader, args=(ser,), daemon=True)
    writer_thread = threading.Thread(target=_writer, args=(ser,), daemon=True)
    reader_thread.start()
    writer_thread.start()

    # Main's exit condition is reader-death ONLY. Writer death (stdin EOF)
    # is common on Windows OpenSSH — cmd.exe's stdin handle is flaky
    # across sessions — and treating it as "time to shut down" caused
    # immediate exit on every 3rd-or-later Open Serial. Reader death is
    # the reliable signal: it fires when the client closes the channel
    # (stdout flush raises BrokenPipeError) OR when the port goes away.
    # The client also sends `__RF_QUIT__` on Close, which the writer
    # thread turns into a clean shutdown — so we never rely on stdin EOF.
    try:
        while reader_thread.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        # Signal both threads to stop, then wake the reader out of its
        # blocking readline() before touching ser.close() — otherwise the
        # reader's thread is still inside pyserial's Windows overlapped
        # I/O machinery when close() nulls _overlapped_read, producing:
        #     AttributeError: 'NoneType' object has no attribute 'hEvent'
        # The exception escapes mid-close and leaves Windows' COM handle
        # in limbo, so the next Open Serial sees "Acesso negado".
        _stop.set()
        try:
            ser.cancel_read()
        except Exception:
            pass
        # Give the reader a bounded window to exit its readline(); 1.5 s
        # covers the 1 s pyserial timeout plus slack.
        reader_thread.join(timeout=1.5)
        try: ser.close()
        except Exception: pass
        try: print("Serial port closed.", flush=True)
        except Exception: pass
        sys.exit(0)


if __name__ == "__main__":
    main()
