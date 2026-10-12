"""Real hardware replay attack over UART against ESP32-S3 target.

Sends 'CMD <counter> <payload_hex>' commands. The ESP32 firmware accepts
or rejects based on whether nonce validation is enabled.
"""

from __future__ import annotations

import argparse
import time

import serial


def toggle_nonce(uart: serial.Serial, on: bool):
    cmd = f"DEFENSE NONCE {'ON' if on else 'OFF'}\n"
    uart.write(cmd.encode("ascii"))
    uart.flush()
    resp = uart.readline().decode("ascii", errors="replace").strip()
    print(f"  nonce defense {'enabled' if on else 'disabled'}: {resp}")


def send_command(uart: serial.Serial, counter: int, payload: bytes) -> bool:
    payload_hex = payload.hex()
    cmd = f"CMD {counter} {payload_hex}\n".encode("ascii")
    uart.reset_input_buffer()
    uart.write(cmd)
    uart.flush()
    resp = uart.readline().decode("ascii", errors="replace").strip()
    return resp == "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    uart = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.3)

    counter = 1042
    payload = b"OPEN_VALVE"

    print("=== Real Hardware Replay Attack ===\n")

    print("--- vulnerable (no nonce) ---")
    toggle_nonce(uart, False)

    ok1 = send_command(uart, counter, payload)
    print(f"  legit   counter={counter}  -> accepted={ok1}")

    ok2 = send_command(uart, counter, payload)
    print(f"  replay  counter={counter}  -> accepted={ok2}")

    ok3 = send_command(uart, counter, payload)
    print(f"  replay  counter={counter}  -> accepted={ok3}")

    print(f"\n  RESULT: replay {'succeeded' if ok2 else 'failed'}\n")

    print("--- protected (nonce + monotonic counter) ---")
    toggle_nonce(uart, True)

    ok4 = send_command(uart, counter + 100, payload)
    print(f"  legit   counter={counter+100}  -> accepted={ok4}")

    ok5 = send_command(uart, counter + 100, payload)
    print(f"  replay  counter={counter+100}  -> accepted={ok5}")

    ok6 = send_command(uart, counter + 101, payload)
    print(f"  fresh   counter={counter+101}  -> accepted={ok6}")

    print(f"\n  RESULT: replay {'succeeded' if ok5 else 'blocked by nonce defense'}")
    print(f"          fresh command accepted={ok6}")


if __name__ == "__main__":
    main()
