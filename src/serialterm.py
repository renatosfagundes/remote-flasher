"""
Simple serial terminal — reads from a COM port and prints to stdout.
Designed to run on the remote lab PCs over SSH.

Usage:
    python serialterm.py --port COM25 --baudrate 115200
"""
import argparse
import sys
import serial


def main():
    parser = argparse.ArgumentParser(description="Serial terminal reader")
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

    print(f"Connected to {args.port}. Reading...")
    sys.stdout.flush()

    try:
        while True:
            data = ser.readline()
            if data:
                try:
                    text = data.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    text = repr(data)
                print(text)
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main()
