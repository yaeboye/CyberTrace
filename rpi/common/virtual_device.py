import pathlib
import sys
import time

import numpy as np

_CPA_DIR = pathlib.Path(__file__).resolve().parents[1] / "attacks" / "cpa"
sys.path.insert(0, str(_CPA_DIR))
from chacha20_model import target_addition, hamming_weight_vec  # noqa: E402

BYTE_LEAK_SAMPLES = [60, 140, 200, 260]


class VirtualESP32:
    """Software stand-in for the ESP32 target device. Reproduces the same
    leakage model as attacks/cpa/synthetic_traces.py so every attack/defense
    can be built and demonstrated before any hardware is wired up, then
    pointed at real ADS1115 traces later with no change to the attack code."""

    def __init__(self, key_word, secret_bytes=b"", seed=None):
        self.key_word = key_word & 0xFFFFFFFF
        self.secret_bytes = bytes(secret_bytes)
        self.rng = np.random.default_rng(seed)

        self.masking_enabled = False
        self.constant_time_enabled = False
        self.nonce_enabled = False

        self.last_seen_counter = -1
        self.encryption_count = 0
        self.request_log = []  # (timestamp, payload_bytes)

    def set_key(self, key_word):
        self.key_word = key_word & 0xFFFFFFFF

    # ---------- CPA target: one power trace per encryption ----------
    def encrypt_with_trace(self, counter, n_samples=300, noise_std=1.0):
        counter &= 0xFFFFFFFF
        target = target_addition(counter, self.key_word)
        mask = int(self.rng.integers(0, 256)) if self.masking_enabled else 0

        trace = self.rng.normal(0, noise_std, size=n_samples)
        for byte_index, sample_idx in enumerate(BYTE_LEAK_SAMPLES):
            byte_val = (target >> (8 * byte_index)) & 0xFF
            if self.masking_enabled:
                byte_val ^= mask
            leakage = hamming_weight_vec(np.array([byte_val]))[0]
            trace[sample_idx] += leakage + self.rng.normal(0, noise_std)

        self.encryption_count += 1
        self._log_request(counter.to_bytes(4, "big"))
        return trace

    # ---------- Timing attack target: secret comparison ----------
    def check_secret(self, candidate):
        """Returns (accepted, simulated_elapsed_seconds). Elapsed time is
        computed analytically rather than via time.sleep(): at the per-byte
        cost this attack operates on (~0.2ms), real sleep() is dominated by
        OS scheduler resolution (Windows in particular is ~15ms granular),
        which would bury the timing signal in noise having nothing to do
        with the attack. This models what a real oscilloscope/high-resolution
        timer would see on the actual hardware."""
        candidate = bytes(candidate)
        compute_cost = 0.0002
        jitter_std = 0.00003

        if self.constant_time_enabled:
            diff = 0 if len(candidate) == len(self.secret_bytes) else 1
            iterations = len(list(zip(candidate, self.secret_bytes)))
            for a, b in zip(candidate, self.secret_bytes):
                diff |= a ^ b
            accepted = diff == 0
        else:
            accepted = len(candidate) == len(self.secret_bytes)
            iterations = 0
            for a, b in zip(candidate, self.secret_bytes):
                iterations += 1
                if a != b:
                    accepted = False
                    break

        elapsed = iterations * compute_cost + abs(self.rng.normal(0, jitter_std))
        self._log_request(candidate)
        return accepted, elapsed

    # ---------- Replay attack target: nonce-checked command ----------
    def submit_command(self, counter, payload):
        if self.nonce_enabled and counter <= self.last_seen_counter:
            self._log_request(payload)
            return False
        self.last_seen_counter = max(self.last_seen_counter, counter)
        self._log_request(payload)
        return True

    def _log_request(self, payload_bytes):
        self.request_log.append((time.time(), bytes(payload_bytes)))
