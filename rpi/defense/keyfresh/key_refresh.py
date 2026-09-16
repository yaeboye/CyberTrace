import pathlib
import sys
import time

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "common"))
sys.path.insert(0, str(_ROOT / "attacks" / "cpa"))
sys.path.insert(0, str(_ROOT / "defense" / "probing"))

from virtual_device import VirtualESP32, BYTE_LEAK_SAMPLES  # noqa: E402
from cpa_engine import recover_key_word  # noqa: E402
from probing_detector import ProbingDetector, simulate_attacker_traffic  # noqa: E402


class KeyRefreshManager:
    """Rotates the device's key on a usage-based schedule, a time-based
    schedule, or immediately on demand (e.g. triggered by a ProbingDetector
    alert). Every rotation is logged with its trigger reason."""

    def __init__(self, device, rotate_every_n=None, rotate_every_seconds=None, rng_seed=None):
        self.device = device
        self.rotate_every_n = rotate_every_n
        self.rotate_every_seconds = rotate_every_seconds
        self.rng = np.random.default_rng(rng_seed)

        self.count_since_rotation = 0
        self.last_rotation_time = time.time()
        self.history = []  # (index, old_key, new_key, reason)
        self._rotation_index = 0

    def note_encryption(self):
        self.count_since_rotation += 1
        if self.rotate_every_n and self.count_since_rotation >= self.rotate_every_n:
            self.force_rotate(reason="usage_threshold")

    def maybe_time_rotate(self, now=None):
        now = now if now is not None else time.time()
        if self.rotate_every_seconds and (now - self.last_rotation_time) >= self.rotate_every_seconds:
            self.force_rotate(reason="time_threshold")

    def force_rotate(self, reason):
        old_key = self.device.key_word
        new_key = int(self.rng.integers(0, 2**32))
        self.device.set_key(new_key)

        self._rotation_index += 1
        self.history.append((self._rotation_index, old_key, new_key, reason))
        self.count_since_rotation = 0
        self.last_rotation_time = time.time()
        return new_key


def attack_with_rotation(device, manager, n_traces, seed=None):
    """Collects n_traces while the key rotates underneath the attacker
    according to `manager`'s schedule, mixing traces encrypted under
    different keys into one dataset -- exactly what a real attacker would
    be forced to do if they can't tell a rotation happened."""
    rng = np.random.default_rng(seed)
    counters = rng.integers(0, 2**32, size=n_traces, dtype=np.uint64).astype(np.uint32)
    traces = []
    for c in counters:
        traces.append(device.encrypt_with_trace(int(c)))
        manager.note_encryption()
    return counters, np.stack(traces)


def run_cpa(counters, traces, window=20):
    traces_per_byte = [traces[:, s - window:s + window] for s in BYTE_LEAK_SAMPLES]
    return recover_key_word(counters, traces_per_byte, verbose=False)


if __name__ == "__main__":
    print("=== Key Refresh Defense Demo ===\n")

    secret_key = 0xAABBCCDD
    n_traces = 4000
    print(f"[setup] hidden key word = 0x{secret_key:08x}\n")

    print("--- baseline: no rotation, attacker collects freely ---")
    device_static = VirtualESP32(key_word=secret_key, seed=5)
    manager_static = KeyRefreshManager(device_static, rotate_every_n=None)
    counters_s, traces_s = attack_with_rotation(device_static, manager_static, n_traces, seed=20)
    recovered_static = run_cpa(counters_s, traces_s)
    print(f"traces collected: {n_traces}  |  RECOVERED: 0x{recovered_static:08x}  "
          f"|  MATCH: {recovered_static == secret_key}\n")

    print("--- defended: key rotates every 800 encryptions ---")
    device_rotating = VirtualESP32(key_word=secret_key, seed=5)
    manager_rotating = KeyRefreshManager(device_rotating, rotate_every_n=800, rng_seed=99)
    counters_r, traces_r = attack_with_rotation(device_rotating, manager_rotating, n_traces, seed=20)
    recovered_rotating = run_cpa(counters_r, traces_r)
    print(f"traces collected: {n_traces}  |  key rotations during collection: {len(manager_rotating.history)}")
    for idx, old_k, new_k, reason in manager_rotating.history:
        print(f"  rotation {idx}: 0x{old_k:08x} -> 0x{new_k:08x}  ({reason})")
    print(f"RECOVERED: 0x{recovered_rotating:08x}  |  MATCH (vs original key): "
          f"{recovered_rotating == secret_key}  |  MATCH (vs final key): "
          f"{recovered_rotating == device_rotating.key_word}\n")
    print(
        "RESULT: mixing traces from multiple keys destroys the correlation signal for "
        "ANY single key -- the attacker recovers neither the original nor the final key.\n"
    )

    print("--- full integration: probing detection triggers immediate key refresh ---")
    device_full = VirtualESP32(key_word=secret_key, seed=5)
    manager_full = KeyRefreshManager(device_full, rng_seed=99)
    detector = ProbingDetector(window_seconds=5, min_samples=10)

    rng = np.random.default_rng(42)
    t = 0.0
    detected_at = None
    for i in range(300):
        t += 0.01 + rng.normal(0, 0.0005)
        payload = i.to_bytes(4, "big")
        detector.ingest(t, payload)
        result = detector.check()
        if result["alert"] and detected_at is None:
            detected_at = i + 1
            new_key = manager_full.force_rotate(reason="probing_detected")
            print(f"request {detected_at}: probing detected ({result['reason']})")
            print(f"  -> key force-rotated to 0x{new_key:08x}")
            break
    if detected_at is None:
        print("probing not detected within 300 requests")
    else:
        print(f"\nattacker's first {detected_at} collected traces are now under a key that "
              f"no longer exists on the device -- any further collection restarts from zero.")
