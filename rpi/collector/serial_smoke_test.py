"""Verify the Raspberry Pi UART link to the CyberTrace target ESP32."""

from __future__ import annotations

import argparse
import time

import serial


def send_command(device: serial.Serial, command: str) -> str:
    device.reset_input_buffer()
    device.write(f"{command}\n".encode("ascii"))
    device.flush()
    response = device.readline().decode("ascii", errors="replace").strip()
    if not response:
        raise TimeoutError(f"No response to {command!r}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", default=115200, type=int)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baud, timeout=2) as device:
        time.sleep(0.2)
        for command, expected in (("PING", "PONG"), ("TRIGGER", "TRIGGERED")):
            response = send_command(device, command)
            print(f"{command} -> {response}")
            if response != expected:
                raise RuntimeError(f"Expected {expected!r}, received {response!r}")

    print("PASS: Raspberry Pi and ESP32 UART link is working")


if __name__ == "__main__":
    main()
