import pathlib
import sys

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "common"))
sys.path.insert(0, str(_ROOT / "attacks" / "cpa"))

from virtual_device import VirtualESP32, BYTE_LEAK_SAMPLES  # noqa: E402
from cpa_engine import recover_key_word, attack_byte  # noqa: E402


def collect_traces(device, n_traces, seed=None):
    rng = np.random.default_rng(seed)
    counters = rng.integers(0, 2**32, size=n_traces, dtype=np.uint64).astype(np.uint32)
    traces = np.stack([device.encrypt_with_trace(int(c)) for c in counters])
    return counters, traces


def run_cpa(counters, traces, window=20):
    traces_per_byte = [traces[:, s - window:s + window] for s in BYTE_LEAK_SAMPLES]
    return recover_key_word(counters, traces_per_byte, verbose=True)


def peak_confidence_only(counters, traces, byte_index, window=20):
    """Same as attack_byte but just reports the peak correlation achieved,
    without trying to recover a byte -- used to show masking drives
    correlation toward the noise floor rather than merely 'needing more
    traces'."""
    sample = BYTE_LEAK_SAMPLES[byte_index]
    trace_slice = traces[:, sample - window:sample + window]
    known_bytes = (counters >> (8 * byte_index)) & 0xFF
    carry = np.zeros(len(counters), dtype=np.uint32)
    _, _, confidence = attack_byte(known_bytes, carry, trace_slice)
    return confidence


if __name__ == "__main__":
    print("=== Masking Defense Demo ===\n")
    secret_key = 0xC0FFEE11
    n_traces = 4000

    print(f"[setup] hidden key word = 0x{secret_key:08x}, {n_traces} traces per run\n")

    print("--- unprotected device (no masking) ---")
    device_unprotected = VirtualESP32(key_word=secret_key, seed=2)
    device_unprotected.masking_enabled = False
    counters_u, traces_u = collect_traces(device_unprotected, n_traces, seed=10)
    recovered_u = run_cpa(counters_u, traces_u)
    print(f"\nRECOVERED: 0x{recovered_u:08x}  |  MATCH: {recovered_u == secret_key}")
    conf_u = peak_confidence_only(counters_u, traces_u, byte_index=0)
    print(f"peak correlation on byte 0: {conf_u:.3f}\n")

    print("--- masked device (first-order random masking) ---")
    device_masked = VirtualESP32(key_word=secret_key, seed=2)
    device_masked.masking_enabled = True
    counters_m, traces_m = collect_traces(device_masked, n_traces, seed=10)
    recovered_m = run_cpa(counters_m, traces_m)
    print(f"\nRECOVERED: 0x{recovered_m:08x}  |  MATCH: {recovered_m == secret_key}")
    conf_m = peak_confidence_only(counters_m, traces_m, byte_index=0)
    print(f"peak correlation on byte 0: {conf_m:.3f}\n")

    print(
        f"RESULT: masking drops peak correlation from {conf_u:.3f} to {conf_m:.3f} "
        f"({conf_u/max(conf_m,1e-9):.1f}x weaker signal). Because a fresh random mask "
        "is applied per trace, the leaked byte is statistically independent of the key "
        "guess -- standard univariate CPA cannot converge no matter how many traces are "
        "collected. Breaking this requires second-order (multivariate) analysis, which "
        "is out of scope for this project (documented as future work)."
    )
