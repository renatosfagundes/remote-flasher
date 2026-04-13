import sys
import serial
import subprocess
import time
import argparse


def reset_board(port, baudrate=19200, command="AT RT"):
    try:
        print(f"[INFO] Resetando placa na porta {port}...")

        ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(1)  # pequena espera para estabilizar

        ser.write((command + "\n").encode())
        ser.close()

        print("[OK] Reset enviado com sucesso.")
        return 0

    except Exception as e:
        print(f"[ERRO] Falha no reset: {e}")
        return 1


def flash_board(port, hex_file, baudrate=57600, mcu="atmega328p"):
    try:
        print(f"[INFO] Iniciando flash na porta {port}...\n")

        cmd = [
            "avrdude.exe",
            "-v",
            "-p", mcu,
            "-c", "arduino",
            "-b", str(baudrate),
            "-P", port,
            "-U", f"flash:w:{hex_file}:i"
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Mostra saída em tempo real
        for line in process.stdout:
            print(line, end="")

        process.wait()

        if process.returncode == 0:
            print("\n[OK] Flash realizado com sucesso.")
        else:
            print("\n[ERRO] Falha no flash.")

        return process.returncode

    except Exception as e:
        print(f"[ERRO] Execução do flash falhou: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Reset + Flash automático")

    parser.add_argument("--reset_port", required=True, help="Porta serial do reset (ex: COM31)")
    parser.add_argument("--flash_port", required=True, help="Porta serial do flash (ex: COM33)")
    parser.add_argument("--hex", required=True, help="Arquivo .hex")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay entre reset e flash (segundos)")

    args = parser.parse_args()

    # 1. Reset
    reset_rc = reset_board(args.reset_port)

    # 2. Delay crítico (ajuste fino aqui!)
    #time.sleep(args.delay)

    # 3. Flash
    flash_rc = flash_board(args.flash_port, args.hex)

    # Propagate the worst exit code so callers (e.g. the remote flasher GUI)
    # can detect failures instead of always seeing 0.
    sys.exit(reset_rc or flash_rc)


if __name__ == "__main__":
    main()
