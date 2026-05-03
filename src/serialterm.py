"""
Bidirectional serial terminal — reads from a COM port and prints to stdout,
reads from stdin and writes to the COM port.
Designed to run on the remote lab PCs over SSH.

Usage:
    python serialterm.py --port COM25 --baudrate 115200
"""
import argparse
import io
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
# LOCAL ONLY — adds no new remote PC activity.
_stop = threading.Event()


def _reader(ser):
    """Read from serial and print to stdout.

    Also flushes stdout every iteration even when no data arrives — if the
    SSH channel was closed (Close Serial on the client), the next flush
    will raise BrokenPipeError (OSError) and break us out of the loop,
    which signals the main thread to shut down and release the COM port.
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
    """Read from stdin and write to serial."""
    try:
        buf = ""
        while not _stop.is_set():
            ch = sys.stdin.read(1)
            if not ch:
                break
            if ch in ("\n", "\r"):
                if buf:
                    ser.write((buf + "\r\n").encode("utf-8"))
                    ser.flush()
                    buf = ""
            else:
                buf += ch
    except (serial.SerialException, OSError, EOFError):
        pass


def main():
    parser = argparse.ArgumentParser(description="Bidirectional serial terminal")
    parser.add_argument("--port", required=True, help="COM port (e.g. COM25)")
    parser.add_argument("--baudrate", type=int, default=115200, help="Baud rate")
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baudrate} baud...")
    sys.stdout.flush()

    try:
        ser = serial.Serial(args.port, args.baudrate, timeout=1, dsrdtr=False, rtscts=False)
    except serial.SerialException as e:
        print(f"ERROR: Could not open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to {args.port}. Reading... (type to send)")
    sys.stdout.flush()

    reader_thread = threading.Thread(target=_reader, args=(ser,), daemon=True)
    writer_thread = threading.Thread(target=_writer, args=(ser,), daemon=True)
    reader_thread.start()
    writer_thread.start()

    # Exit as soon as EITHER thread dies:
    #   - reader dying  = serial error or broken stdout (SSH close while
    #                     data flowing, caught by print/flush raising)
    #   - writer dying  = stdin EOF (SSH channel closed while Arduino idle)
    try:
        while reader_thread.is_alive() and writer_thread.is_alive():
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
        # LOCAL ONLY — no remote PC interaction beyond what master had.
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
