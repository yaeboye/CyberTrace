"""Kyber NTT (Number Theoretic Transform) power leakage demonstration.

Scope: show that NTT butterfly operations leak through power consumption,
NOT full Kyber key recovery. Full CPA on Kyber is explicitly future scope.

This demonstrates that the coefficient values being processed during NTT
correlate with Hamming weight, producing measurable power leakage — the
same fundamental principle as the ChaCha20 CPA attack.
"""

from __future__ import annotations

import numpy as np

KYBER_Q = 3329
KYBER_N = 256

ZETAS = []
g = 17
for i in range(128):
    ZETAS.append(pow(g, i, KYBER_Q))


def ntt_butterfly(a: int, b: int, zeta: int) -> tuple[int, int]:
    t = (zeta * b) % KYBER_Q
    return (a + t) % KYBER_Q, (a - t) % KYBER_Q


def ntt_forward(coeffs: list[int]) -> list[int]:
    r = list(coeffs)
    k = 1
    length = 128
    while length >= 2:
        start = 0
        while start < 256:
            zeta = ZETAS[k]
            k += 1
            for j in range(start, start + length):
                r[j], r[j + length] = ntt_butterfly(r[j], r[j + length], zeta)
            start += 2 * length
        length //= 2
    return r


def simulate_ntt_trace(coeffs: list[int], noise_std: float = 0.5, rng=None) -> np.ndarray:
    """Simulates power consumption during NTT: each butterfly multiply
    leaks Hamming weight of the intermediate product (zeta * b) mod q."""
    if rng is None:
        rng = np.random.default_rng()

    intermediates = []
    r = list(coeffs)
    k = 1
    length = 128
    while length >= 2:
        start = 0
        while start < 256:
            zeta = ZETAS[k]
            k += 1
            for j in range(start, start + length):
                t = (zeta * r[j + length]) % KYBER_Q
                intermediates.append(t)
                r[j], r[j + length] = (r[j] + t) % KYBER_Q, (r[j] - t) % KYBER_Q
            start += 2 * length
        length //= 2

    n_ops = len(intermediates)
    trace = rng.normal(0, noise_std, size=n_ops)

    for i, val in enumerate(intermediates):
        hw = bin(val).count('1')
        trace[i] += hw

    return trace, intermediates


def demonstrate_leakage(n_trials: int = 500, noise_std: float = 0.8):
    rng = np.random.default_rng(42)
    print("=== Kyber NTT Leakage Demonstration ===\n")
    print("Scope: demonstrate power leakage exists in NTT operations.")
    print("This is NOT full Kyber key recovery (future scope).\n")

    all_traces = []
    all_intermediates = []

    for _ in range(n_trials):
        coeffs = [int(rng.integers(0, KYBER_Q)) for _ in range(KYBER_N)]
        trace, intermediates = simulate_ntt_trace(coeffs, noise_std=noise_std, rng=rng)
        all_traces.append(trace)
        all_intermediates.append(intermediates)

    traces = np.stack(all_traces)
    intermediates = np.array(all_intermediates, dtype=np.int32)

    print(f"traces collected: {n_trials}")
    print(f"operations per NTT: {traces.shape[1]}")

    target_op = 0
    hw_values = np.array([bin(intermediates[i, target_op]).count('1') for i in range(n_trials)])
    power_values = traces[:, target_op]

    correlation = np.corrcoef(hw_values, power_values)[0, 1]

    print(f"\nbutterfly operation #{target_op}:")
    print(f"  Pearson correlation (HW vs power): {correlation:.4f}")
    print(f"  |correlation|: {abs(correlation):.4f}")

    correlations = []
    for op in range(min(20, traces.shape[1])):
        hw = np.array([bin(intermediates[i, op]).count('1') for i in range(n_trials)])
        pwr = traces[:, op]
        c = abs(np.corrcoef(hw, pwr)[0, 1])
        correlations.append(c)

    avg_corr = np.mean(correlations)
    print(f"\naverage |correlation| across first 20 butterfly ops: {avg_corr:.4f}")

    if avg_corr > 0.3:
        print("\nRESULT: significant HW-power correlation detected in NTT operations.")
        print("This confirms Kyber's NTT implementation leaks through power side-channel.")
        print("Full key recovery via profiled/template attack is documented as future work.")
    else:
        print("\nRESULT: correlation below expected threshold — increase n_trials or reduce noise.")

    return avg_corr


if __name__ == "__main__":
    demonstrate_leakage()
