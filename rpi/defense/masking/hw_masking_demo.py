"""Real-hardware masking defense demo against the amplified-leakage CPA.

Collects LEAKLOOP power traces from the ESP32-S3 target twice -- once with
masking disabled, once enabled (toggled at runtime over the UART with
DEFENSE MASKING ON/OFF) -- and runs the first-round CPA on each.

Unprotected, CPA recovers key word 0. With first-order masking the firmware
leaks (d ^ mask) with a fresh per-call random mask, so the masked value's
Hamming weight is independent of the key and the correlation collapses to the
noise floor -- recovery fails. Same firmware, runtime toggle, no reflash.

Measured on hardware (800 traces each):
  masking OFF -> best|corr| ~0.33, key0 = 0xDEADBEEF recovered
  masking ON  -> best|corr| ~0.10 (noise floor), recovery fails

Target on /dev/ttyAMA0, USB unplugged so all current flows through the shunt.
Usage: python hw_masking_demo.py [n_traces]
"""

from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import serial
import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.ads1x15 import Mode, Pin
from adafruit_ads1x15.analog_in import AnalogIn

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "attacks" / "cpa"))
from cpa_engine import correlation_matrix, recover_key_word0  # noqa: E402
from chacha20_model import first_round_xor_target, hamming_weight_vec  # noqa: E402

KEY0 = 0xDEADBEEF


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115(i2c, gain=4); ads.mode = Mode.CONTINUOUS; ads.data_rate = 860
    chan = AnalogIn(ads, Pin.A0, Pin.A1)
    uart = serial.Serial("/dev/ttyAMA0", 115200, timeout=5); time.sleep(0.3)

    def cmd(c):
        uart.reset_input_buffer(); uart.write(c + b"\n"); uart.flush()
        return uart.readline().strip()

    def collect(count):
        rng = np.random.default_rng(7)
        counters = rng.integers(0, 2**32, size=count, dtype=np.uint64).astype(np.uint32)
        raw = []
        for c in counters:
            uart.reset_input_buffer(); uart.write(b"LEAKLOOP %08x\n" % int(c)); uart.flush()
            b = []
            while not uart.in_waiting:
                b.append(chan.voltage)
            uart.readline(); raw.append(b)
        length = min(len(r) for r in raw)
        return counters, np.array([r[:length] for r in raw])

    def analyze(counters, traces, tag):
        per = traces.shape[1] // 4
        tgt = np.array([first_round_xor_target(int(c), KEY0) for c in counters], dtype=np.uint32)
        peaks = [
            float(np.abs(correlation_matrix(
                hamming_weight_vec((tgt >> (8 * b)) & 0xFF).astype(float)[:, None],
                traces[:, b * per:(b + 1) * per])[0]).max())
            for b in range(4)
        ]
        rec = recover_key_word0(counters, [traces[:, b * per:(b + 1) * per] for b in range(4)], verbose=False)
        print(f"[{tag}] best|corr|/byte = {','.join(f'{p:.3f}' for p in peaks)}  "
              f"| recovered 0x{rec:08x}  MATCH={rec == KEY0}")
        return rec == KEY0

    print("masking OFF:", cmd(b"DEFENSE MASKING OFF"), "| STATUS:", cmd(b"STATUS"))
    off_ok = analyze(*collect(n), "masking OFF")
    print("masking ON :", cmd(b"DEFENSE MASKING ON"), "| STATUS:", cmd(b"STATUS"))
    on_ok = analyze(*collect(n), "masking ON ")
    cmd(b"DEFENSE MASKING OFF")

    print(f"\ndefense effective = {off_ok and not on_ok}")


if __name__ == "__main__":
    main()
