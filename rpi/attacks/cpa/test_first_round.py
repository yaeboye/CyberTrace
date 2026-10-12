"""Validate the real first-round ChaCha20 CPA path against synthetic traces
built from the true intermediate (counter ^ (const0 + key0)). Unlike
test_cpa.py (which exercises the simplified counter+key model), this confirms
the attack that is actually correct for a real ChaCha20 core."""

from cpa_engine import recover_key_word0, recover_first_round_a
from chacha20_model import first_round_a
from synthetic_traces import generate_first_round_traces


def test_recovers_key0_clean():
    key0 = 0xDEADBEEF
    counters, traces, samples = generate_first_round_traces(
        key0, n_traces=3000, noise_std=1.0, seed=42
    )
    per_byte = [traces[:, s - 20:s + 20] for s in samples]

    recovered_a = recover_first_round_a(counters, per_byte, verbose=True)
    assert recovered_a == first_round_a(key0), (
        f"a mismatch: got 0x{recovered_a:08x}, want 0x{first_round_a(key0):08x}"
    )

    recovered_key0 = recover_key_word0(counters, per_byte, verbose=True)
    assert recovered_key0 == key0, (
        f"expected 0x{key0:08x}, got 0x{recovered_key0:08x}"
    )
    print(f"PASS: recovered key0 = 0x{recovered_key0:08x} from real first-round XOR target")


def test_recovers_key0_under_noise():
    key0 = 0x1337C0DE
    counters, traces, samples = generate_first_round_traces(
        key0, n_traces=8000, noise_std=3.0, seed=7
    )
    per_byte = [traces[:, s - 20:s + 20] for s in samples]
    recovered = recover_key_word0(counters, per_byte, verbose=False)
    assert recovered == key0, f"expected 0x{key0:08x}, got 0x{recovered:08x}"
    print(f"PASS: recovered key0 = 0x{recovered:08x} under noise_std=3.0")


if __name__ == "__main__":
    print("--- clean signal ---")
    test_recovers_key0_clean()
    print("\n--- heavier noise ---")
    test_recovers_key0_under_noise()
