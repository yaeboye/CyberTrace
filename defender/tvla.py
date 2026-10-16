"""TVLA -- Test Vector Leakage Assessment (non-specific fixed-vs-random t-test).

The industry-standard (ISO 17825 / FIPS 140-3) way to decide whether a device
has exploitable side-channel leakage, independent of any particular attack.
Collect two trace sets -- one with a FIXED input, one with RANDOM inputs -- and
compute Welch's t at each sample. If |t| exceeds 4.5 anywhere, the device leaks
with high confidence. Masking that works makes the fixed set vary as much as the
random set (fresh mask per call), so the t-statistic stays below 4.5 -- a pass.

Needs no successful attack: it measures leakage presence, not key recovery.
"""

from __future__ import annotations

import numpy as np

THRESHOLD = 4.5


def collect_fixed_random(transport, n_each, fixed_counter=0x11111111, rng=None):
    rng = rng or np.random.default_rng()
    fixed, rand = [], []
    rand_counters = rng.integers(0, 2**32, size=n_each, dtype=np.uint64).astype(np.uint32)
    # interleave to cancel slow drift, as TVLA best practice requires
    for i in range(n_each):
        fixed.append(transport.leakloop(fixed_counter))
        rand.append(transport.leakloop(int(rand_counters[i])))
    L = min(min(len(r) for r in fixed), min(len(r) for r in rand))
    return (np.array([r[:L] for r in fixed]),
            np.array([r[:L] for r in rand]))


def welch_t(a, b):
    """Per-sample Welch's t-statistic between trace sets a and b (n, samples)."""
    ma, mb = a.mean(axis=0), b.mean(axis=0)
    va, vb = a.var(axis=0, ddof=1), b.var(axis=0, ddof=1)
    denom = np.sqrt(va / a.shape[0] + vb / b.shape[0])
    denom[denom == 0] = 1e-12
    return (ma - mb) / denom


def assess(transport, n_each=400, rng=None):
    fixed, rand = collect_fixed_random(transport, n_each, rng=rng)
    t = welch_t(fixed, rand)
    peak = float(np.max(np.abs(t)))
    return {
        "n_each": int(n_each),
        "threshold": THRESHOLD,
        "peak_t": peak,
        "peak_sample": int(np.argmax(np.abs(t))),
        "leaks": peak > THRESHOLD,
        "t_trace": t,
    }
