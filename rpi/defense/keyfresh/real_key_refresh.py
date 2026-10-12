"""Real hardware key refresh over UART.

Sends 'SET_KEY <hex>' to the ESP32 target and tracks rotation history.
Integrates with ProbingDetector for attack-triggered rotation.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import serial


class HardwareKeyRefreshManager:
    def __init__(
        self,
        uart: serial.Serial,
        rotate_every_n: int | None = None,
        rotate_every_seconds: float | None = None,
        rng_seed: int | None = None,
    ):
        self.uart = uart
        self.rotate_every_n = rotate_every_n
        self.rotate_every_seconds = rotate_every_seconds
        self.rng = np.random.default_rng(rng_seed)

        self.count_since_rotation = 0
        self.last_rotation_time = time.time()
        self.history: list[tuple[int, str, str]] = []
        self._idx = 0

    def note_encryption(self):
        self.count_since_rotation += 1
        if self.rotate_every_n and self.count_since_rotation >= self.rotate_every_n:
            self.force_rotate("usage_threshold")

    def maybe_time_rotate(self):
        if self.rotate_every_seconds:
            if (time.time() - self.last_rotation_time) >= self.rotate_every_seconds:
                self.force_rotate("time_threshold")

    def force_rotate(self, reason: str) -> str:
        new_key = int(self.rng.integers(0, 2**32))
        key_hex = f"{new_key:08x}"

        self.uart.reset_input_buffer()
        self.uart.write(f"SET_KEY {key_hex}\n".encode("ascii"))
        self.uart.flush()
        resp = self.uart.readline().decode("ascii", errors="replace").strip()

        if resp != "OK":
            print(f"  WARNING: SET_KEY got {resp!r} instead of OK")

        self._idx += 1
        self.history.append((self._idx, key_hex, reason))
        self.count_since_rotation = 0
        self.last_rotation_time = time.time()
        return key_hex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--rotate-every", type=int, default=5)
    ap.add_argument("--encryptions", type=int, default=15)
    args = ap.parse_args()

    uart = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.3)

    mgr = HardwareKeyRefreshManager(uart, rotate_every_n=args.rotate_every, rng_seed=42)

    print("=== Real Hardware Key Refresh Demo ===\n")
    print(f"rotating every {args.rotate_every} encryptions\n")

    for i in range(1, args.encryptions + 1):
        uart.reset_input_buffer()
        uart.write(f"ENCRYPT {i:08x}\n".encode("ascii"))
        uart.flush()
        _ = uart.readline()
        mgr.note_encryption()
        print(f"  encryption {i:>3d}  rotations so far: {len(mgr.history)}")

    print(f"\ntotal rotations: {len(mgr.history)}")
    for idx, key_hex, reason in mgr.history:
        print(f"  #{idx}: -> {key_hex}  ({reason})")


if __name__ == "__main__":
    main()
