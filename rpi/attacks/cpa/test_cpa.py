import numpy as np

from cpa_engine import recover_key_word
from synthetic_traces import generate_traces


def test_recovers_key_on_clean_signal():
    secret_key_word = 0xDEADBEEF
    counters, traces, sample_points = generate_traces(
        secret_key_word, n_traces=3000, noise_std=1.0, seed=42
    )

    traces_per_byte = [traces[:, s - 20:s + 20] for s in sample_points]
    recovered = recover_key_word(counters, traces_per_byte)

    assert recovered == secret_key_word, (
        f"expected 0x{secret_key_word:08x}, got 0x{recovered:08x}"
    )
    print(f"PASS: recovered 0x{recovered:08x} matches injected key")


def test_recovers_key_under_heavier_noise():
    secret_key_word = 0x1337C0DE
    counters, traces, sample_points = generate_traces(
        secret_key_word, n_traces=8000, noise_std=3.0, seed=7
    )

    traces_per_byte = [traces[:, s - 20:s + 20] for s in sample_points]
    recovered = recover_key_word(counters, traces_per_byte)

    assert recovered == secret_key_word, (
        f"expected 0x{secret_key_word:08x}, got 0x{recovered:08x}"
    )
    print(f"PASS: recovered 0x{recovered:08x} under noise_std=3.0")


if __name__ == "__main__":
    print("--- clean signal test ---")
    test_recovers_key_on_clean_signal()
    print("\n--- heavier noise test ---")
    test_recovers_key_under_heavier_noise()
