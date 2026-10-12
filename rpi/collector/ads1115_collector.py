"""Collect power traces from ESP32-S3 target via ADS1115 ADC over I2C.

Protocol: RPi sends 'ENCRYPT <counter_hex>' over UART, simultaneously
polls ADS1115 as fast as possible during the trigger-pin window, then
reads back the ciphertext. Each trace is saved as a row in a numpy array.
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np
import serial

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.ads1x15 import Mode, Pin
    from adafruit_ads1x15.analog_in import AnalogIn
    HAS_I2C = True
except ImportError:
    HAS_I2C = False

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "traces"


def setup_adc(gain: float = 4, data_rate: int = 860):
    if not HAS_I2C:
        raise RuntimeError(
            "I2C libraries not installed. "
            "pip install adafruit-circuitpython-ads1x15 adafruit-blinka"
        )
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    ads.gain = gain
    ads.data_rate = data_rate
    ads.mode = Mode.CONTINUOUS
    chan = AnalogIn(ads, Pin.A0, Pin.A1)
    return chan


def collect_single_trace(
    uart: serial.Serial,
    chan,
    counter: int,
    num_samples: int,
) -> tuple[np.ndarray, str]:
    uart.reset_input_buffer()

    cmd = f"ENCRYPT {counter:08x}\n"
    uart.write(cmd.encode("ascii"))
    uart.flush()

    trace = np.empty(num_samples, dtype=np.float64)
    for i in range(num_samples):
        trace[i] = chan.voltage

    response = uart.readline().decode("ascii", errors="replace").strip()
    return trace, response


def collect_batch(
    uart: serial.Serial,
    chan,
    num_traces: int,
    num_samples: int,
    start_counter: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    counters = np.arange(start_counter, start_counter + num_traces, dtype=np.uint32)
    traces = np.empty((num_traces, num_samples), dtype=np.float64)

    for i, ctr in enumerate(counters):
        traces[i], _ = collect_single_trace(uart, chan, int(ctr), num_samples)
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  [{i+1}/{num_traces}]  mean_voltage={traces[i].mean():.6f} V")

    return counters, traces


def calibrate(traces: np.ndarray, top_n: int = 10) -> np.ndarray:
    """Find sample indices with highest inter-trace variance (likely leakage)."""
    var = np.var(traces, axis=0)
    top = np.argsort(var)[-top_n:][::-1]
    print("\n--- calibration ---")
    print(f"top {top_n} high-variance sample indices: {top}")
    for idx in top:
        print(f"  sample {idx:>4d}  variance={var[idx]:.8f}")
    return top


def save(counters: np.ndarray, traces: np.ndarray, tag: str = "run"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    prefix = DATA_DIR / f"{tag}_{ts}"
    np.save(f"{prefix}_counters.npy", counters)
    np.save(f"{prefix}_traces.npy", traces)
    print(f"saved {len(counters)} traces -> {prefix}_*.npy")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--traces", type=int, default=1000)
    ap.add_argument("--samples", type=int, default=300)
    ap.add_argument("--gain", type=int, default=4,
                    help="ADS1115 PGA gain (2/3, 1, 2, 4, 8, 16)")
    ap.add_argument("--calibrate-only", action="store_true",
                    help="collect a small batch and show variance map")
    ap.add_argument("--tag", default="cpa")
    args = ap.parse_args()

    chan = setup_adc(gain=args.gain)

    uart = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.3)

    uart.write(b"PING\n")
    uart.flush()
    pong = uart.readline().decode("ascii", errors="replace").strip()
    if pong != "PONG":
        print(f"WARNING: expected PONG, got {pong!r}")

    if args.calibrate_only:
        print("calibration run (200 traces)...")
        counters, traces = collect_batch(uart, chan, 200, args.samples)
        calibrate(traces)
        save(counters, traces, tag="calibration")
        return

    print(f"collecting {args.traces} traces ({args.samples} samples each)...")
    counters, traces = collect_batch(uart, chan, args.traces, args.samples)
    calibrate(traces)
    save(counters, traces, tag=args.tag)


if __name__ == "__main__":
    main()
