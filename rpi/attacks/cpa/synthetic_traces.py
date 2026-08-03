import numpy as np

from chacha20_model import target_addition, hamming_weight_vec


def generate_traces(secret_key_word, n_traces=2000, n_samples=300, noise_std=1.0, seed=None):
    """Builds synthetic power traces for a fixed secret key word, with each
    trace using a different known counter (mimicking many encrypted blocks
    under one session key). Leakage is injected as Hamming weight of each
    byte of (counter + key_word) at four fixed sample points, plus Gaussian
    noise everywhere else, so the CPA engine can be validated end-to-end
    without any hardware."""
    rng = np.random.default_rng(seed)

    counters = rng.integers(0, 2**32, size=n_traces, dtype=np.uint64).astype(np.uint32)
    target = np.array([target_addition(int(c), secret_key_word) for c in counters], dtype=np.uint32)

    byte_leak_samples = [60, 140, 200, 260]
    traces = rng.normal(0, noise_std, size=(n_traces, n_samples))

    for byte_index, sample_idx in enumerate(byte_leak_samples):
        byte_val = (target >> (8 * byte_index)) & 0xFF
        leakage = hamming_weight_vec(byte_val).astype(np.float64)
        traces[:, sample_idx] += leakage + rng.normal(0, noise_std, size=n_traces)

    return counters, traces, byte_leak_samples
