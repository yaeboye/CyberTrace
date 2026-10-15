"""Real-hardware amplified-leakage CPA against the ESP32-S3 target.

The ADS1115 (~860 SPS) cannot resolve microsecond-scale ChaCha20, so
single-shot CPA on the ENCRYPT command sees only post-crypto baseline
(measured max|corr| with the known key ~0.05, the noise floor). The firmware's
LEAKLOOP command instead computes the real first-round intermediate
d = counter ^ (const0 + key0) and, per byte, toggles only the GPIO pins
matching that byte's set bits in a tight loop. The average VCC-rail current
over the loop then scales with HW(byte), lifting the leakage into the
millisecond window the ADC can sample. Four byte-phases run back-to-back under
one trigger pulse, so the collector slices four equal per-byte windows.

The CPA methodology is unchanged from a real attack (first-round XOR target,
Hamming-weight model, Pearson correlation, byte-wise recovery of
a = const0 + key0, then key0 = a - const0). Only the signal MAGNITUDE is
amplified to suit a slow ADC -- document this honestly: it is not single-shot
CPA, which would need an oscilloscope or MHz-class ADC.

Measured on hardware: best-case |corr| ~0.28 (vs 0.05 un-amplified);
full key0 recovery from ~400 traces.

Usage: python leak_cpa.py [n_traces]   (target on /dev/ttyAMA0, USB unplugged
so all target current flows through the shunt).
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "attacks" / "cpa"))
from cpa_engine import correlation_matrix, recover_key_word0  # noqa: E402
from chacha20_model import first_round_xor_target, hamming_weight_vec  # noqa: E402

TARGET_KEY0 = 0xDEADBEEF  # firmware's fixed key word 0, for match-checking


def setup_adc(gain=4, data_rate=860):
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115(i2c, gain=gain)
    ads.mode = Mode.CONTINUOUS
    ads.data_rate = data_rate
    return AnalogIn(ads, Pin.A0, Pin.A1)


def collect_one(uart, chan, counter):
    """Send LEAKLOOP and sample the ADC continuously until LEAKDONE arrives,
    so the samples span the full four-phase window."""
    uart.reset_input_buffer()
    uart.write(b"LEAKLOOP %08x\n" % counter)
    uart.flush()
    buf = []
    while not uart.in_waiting:
        buf.append(chan.voltage)
    uart.readline()
    return buf


def collect(uart, chan, counters):
    raw = [collect_one(uart, chan, int(c)) for c in counters]
    length = min(len(r) for r in raw)
    return np.array([r[:length] for r in raw])


def attack(counters, traces, verbose=True):
    per = traces.shape[1] // 4
    per_byte = [traces[:, b * per:(b + 1) * per] for b in range(4)]
    return recover_key_word0(counters, per_byte, verbose=verbose)


def best_case_corr(counters, traces):
    """Diagnostic: correlation of each phase window with the TRUE key byte's
    Hamming weight -- confirms leakage is present before trusting recovery."""
    per = traces.shape[1] // 4
    tgt = np.array([first_round_xor_target(int(c), TARGET_KEY0) for c in counters], dtype=np.uint32)
    peaks = []
    for b in range(4):
        w = traces[:, b * per:(b + 1) * per]
        hw = hamming_weight_vec((tgt >> (8 * b)) & 0xFF).astype(float)
        peaks.append(float(np.abs(correlation_matrix(hw[:, None], w)[0]).max()))
    return peaks


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    chan = setup_adc()
    uart = serial.Serial("/dev/ttyAMA0", 115200, timeout=5)
    time.sleep(0.3)

    window = len(collect_one(uart, chan, 1))
    print(f"LEAKLOOP window ~= {window} ADC samples")

    rng = np.random.default_rng(7)
    counters = rng.integers(0, 2**32, size=n, dtype=np.uint64).astype(np.uint32)
    t0 = time.time()
    traces = collect(uart, chan, counters)
    print(f"collected {n} x {traces.shape[1]} traces in {time.time() - t0:.0f}s")

    peaks = best_case_corr(counters, traces)
    print("best-case |corr| per byte phase: " + ", ".join(f"{p:.3f}" for p in peaks))

    recovered = attack(counters, traces)
    print(f"RECOVERED key0 = 0x{recovered:08x}  (true 0x{TARGET_KEY0:08x})  "
          f"MATCH={recovered == TARGET_KEY0}")


if __name__ == "__main__":
    main()
