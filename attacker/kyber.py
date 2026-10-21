"""Kyber secret-coefficient CPA (NTT pointwise-multiply target).

Recovers a secret NTT-domain coefficient s_hat_i by varying the attacker-known
u_hat_i, guessing s_hat_i in [0, q), and correlating HW(guess * u_hat_i mod q)
against the measured leakage of the real product. Mirrors ChaCha20's flow:
collect amplified traces, correlate per guess, pick the peak. Validated in sim
here; the same recovery runs on real traces from the firmware KYBERLEAK command.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpi" / "attacks" / "cpa"))
from kyber_model import KYBER_Q, pointwise, hw, hw_vec  # noqa: E402
from cpa_engine import correlation_matrix  # noqa: E402


def recover_coefficient(u_values, traces, align=True):
    """u_values: (n,) known u_hat_i per trace. traces: (n, samples).
    Returns (best_s_hat, peak_corr, margin, ranking). Traces are realigned by
    default to remove the hardware leak-loop start jitter (see cpa.align_traces);
    harmless no-op on aligned simulation traces."""
    if align:
        from cpa import align_traces
        traces = align_traces(np.asarray(traces, dtype=np.float64))
    guesses = np.arange(KYBER_Q, dtype=np.int64)
    # hypothesis[n, g] = HW((guess_g * u_n) mod q)
    prod = (u_values[:, None].astype(np.int64) * guesses[None, :]) % KYBER_Q
    hyp = hw_vec(prod).astype(np.float64)              # (n, q)
    corr = correlation_matrix(hyp, traces)            # (q, samples)
    peak = np.abs(corr).max(axis=1)
    order = np.argsort(peak)[::-1]
    best, second = int(order[0]), int(order[1])
    return {
        "s_hat": best,
        "corr": float(peak[best]),
        "runner_up": int(second),
        "margin": float(peak[best] - peak[second]),
        "top5": [(int(g), float(peak[g])) for g in order[:5]],
    }


def simulate_traces(secret_s_hat, n_traces, n_samples=160, noise_std=2.0,
                    leak_scale=1.0, seed=None):
    """Amplified-leakage sim matching the firmware KYBERLEAK: HW of the real
    product t = s_hat * u mod q sustained across the trace window, + noise."""
    rng = np.random.default_rng(seed)
    u_values = rng.integers(0, KYBER_Q, size=n_traces).astype(np.int64)
    traces = rng.normal(0, noise_std, size=(n_traces, n_samples))
    for i, u in enumerate(u_values):
        t = pointwise(secret_s_hat, u)
        traces[i] += leak_scale * hw(t)
    return u_values, traces


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Kyber secret-coefficient CPA (sim)")
    ap.add_argument("--secret", type=int, default=1234, help="true s_hat_i in [0,q)")
    ap.add_argument("--traces", type=int, default=2000)
    ap.add_argument("--noise", type=float, default=2.0)
    args = ap.parse_args()

    print(f"=== Kyber secret-coefficient CPA (sim) ===")
    print(f"true s_hat = {args.secret}, {args.traces} traces, noise={args.noise}\n")
    u, tr = simulate_traces(args.secret, args.traces, noise_std=args.noise, seed=1)
    r = recover_coefficient(u, tr)
    ok = r["s_hat"] == args.secret
    print(f"recovered s_hat = {r['s_hat']}  (corr {r['corr']:.3f}, "
          f"margin {r['margin']:.3f})  MATCH={ok}")
    print("top-5 candidates:", ", ".join(f"{g}:{c:.2f}" for g, c in r["top5"]))
