"""Capture REAL request traffic to the ESP32 target and log it for the
probing-detection dataset.

Unlike the simulators in probing_detector.py, this issues genuine commands to
the live device over the hardware UART and records, for every request, the
real send timestamp and the request payload. The timing therefore carries real
serial latency, real device-compute stalls, and real OS scheduling jitter --
the traffic a deployed monitor would actually observe.

Three behaviour classes are captured, matching the threat model:

  normal      varied payloads at a human-like pace, with idle gaps and the
              occasional short burst (entropy high, rate low, timing irregular)
  aggressive  a trace-collection flood: sequential counters, as fast as the
              link allows (the signature of CPA acquisition)
  throttled   a patient attacker: random payloads at ~5/s with jitter, staying
              under the fixed rule thresholds

Each row is written as `timestamp_s,payload_hex` to a per-class CSV under
data/ml_dataset/raw/. Run several sessions per class for a fuller dataset.

Usage (on the Pi, device attached):
    python3 rpi/collector/traffic_logger.py normal     --events 300
    python3 rpi/collector/traffic_logger.py aggressive --events 300
    python3 rpi/collector/traffic_logger.py throttled  --events 300
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib
import time

import numpy as np
import serial

REPO = pathlib.Path(__file__).resolve().parents[2]
RAW_DIR = REPO / "data" / "ml_dataset" / "raw"


def _send(uart, payload: bytes):
    """Issue one real ENCRYPT command carrying the first four payload bytes as
    the counter, and drain the device reply so the timing reflects the real
    round trip. Returns nothing; the caller timestamps the send."""
    counter = int.from_bytes((payload + b"\x00\x00\x00\x00")[:4], "big")
    uart.reset_input_buffer()
    uart.write(f"ENCRYPT {counter:08x}\n".encode("ascii"))
    uart.flush()
    uart.readline()  # block on the ciphertext reply -> real round-trip timing


def capture(cls: str, events: int, port: str, baud: int, seed: int) -> pathlib.Path:
    rng = np.random.default_rng(seed)
    uart = serial.Serial(port, baud, timeout=2)
    time.sleep(0.3)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = RAW_DIR / f"{cls}_{stamp}.csv"

    rows = []
    counter = int(rng.integers(0, 1 << 20))
    burst_left = 0
    for i in range(events):
        if cls == "normal":
            # human pace: exponential gaps, occasional idle, occasional burst
            if burst_left > 0:
                gap = 0.05 + abs(rng.normal(0, 0.02)); burst_left -= 1
            else:
                gap = float(rng.exponential(1.5))
                if rng.random() < 0.05:
                    gap += float(rng.uniform(5, 12))      # idle stretch
                if rng.random() < 0.08:
                    burst_left = int(rng.integers(3, 8))  # a short flurry
            payload = os.urandom(int(rng.integers(4, 16)))
        elif cls == "aggressive":
            gap = 0.0                                     # as fast as the link
            payload = (counter + i).to_bytes(4, "big")    # sequential counters
        elif cls == "throttled":
            gap = max(0.001, (1.0 / 5.0) * (1.0 + rng.normal(0, 0.45)))  # ~5/s
            payload = os.urandom(int(rng.integers(4, 16)))
        else:
            raise SystemExit(f"unknown class {cls!r}")

        if gap > 0:
            time.sleep(gap)
        t = time.time()
        _send(uart, payload)
        rows.append((f"{t:.6f}", payload.hex()))

    uart.close()
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_s", "payload_hex"])
        w.writerows(rows)
    span = float(rows[-1][0]) - float(rows[0][0]) if len(rows) > 1 else 0.0
    print(f"{cls}: {len(rows)} real requests over {span:.1f}s "
          f"({len(rows)/max(span,1e-9):.2f}/s) -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cls", choices=["normal", "aggressive", "throttled"])
    ap.add_argument("--events", type=int, default=300)
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    capture(args.cls, args.events, args.port, args.baud, args.seed)


if __name__ == "__main__":
    main()
