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
import serial


# Force UTF-8 output so non-ASCII characters from the Arduino (e.g. em-dash,
# degree signs, accented text) don't crash the reader on Windows hosts that
# default to cp1252 stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:  # pre-3.7 fallback
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _reader(ser):
    """Read from serial and print to stdout."""
    try:
        while True:
            data = ser.readline()
            if data:
                try:
                    text = data.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    text = repr(data)
                # errors="replace" on stdout protects us even if a weird byte
                # slips through — '?' is better than a traceback.
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
        while True:
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
        ser = serial.Serial(args.port, args.baudrate, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: Could not open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to {args.port}. Reading... (type to send)")
    sys.stdout.flush()

    reader_thread = threading.Thread(target=_reader, args=(ser,), daemon=True)
    writer_thread = threading.Thread(target=_writer, args=(ser,), daemon=True)
    reader_thread.start()
    writer_thread.start()

    try:
        reader_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main()
