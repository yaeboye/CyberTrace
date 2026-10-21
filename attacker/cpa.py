"""First-round ChaCha20 CPA with a full analysis report, not just the key.

Targets the real first-round intermediate d = counter ^ (const0 + key0) leaked
by the firmware/sim LEAKLOOP. Recovers a = const0 + key0 byte-wise (XOR target,
signed-correlation selection), then key0 = a - const0. For each byte it reports
the winning value, its correlation peak, the margin to the runner-up (the
"is this real?" number), the point-of-interest sample, and the top candidates;
across the set it reports the NTD convergence curve.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpi" / "attacks" / "cpa"))
from cpa_engine import correlation_matrix  # noqa: E402
from chacha20_model import hamming_weight_vec, CONSTANTS, MASK32  # noqa: E402


def collect(transport, n_traces, counters=None, rng=None, progress=None):
    rng = rng or np.random.default_rng()
    if counters is None:
        counters = rng.integers(0, 2**32, size=n_traces, dtype=np.uint64).astype(np.uint32)
    rows = []
    for i, c in enumerate(counters):
        rows.append(transport.leakloop(int(c)))
        if progress and (i + 1) % progress == 0:
            print(f"    collected {i + 1}/{len(counters)}")
    length = min(len(r) for r in rows)
    return counters, np.array([r[:length] for r in rows])


def align_traces(traces, max_shift=25):
    """Align traces to a common reference to remove the few-sample jitter in
    where the leak loop starts.

    On real hardware the interval between issuing the command and the device
    entering the measured loop varies by a handful of samples (serial and OS
    scheduling latency), so the four byte-phase windows land at slightly
    different sample indices on every trace. Correlating at a fixed sample then
    averages the leakage away. Each trace is shifted (within +/-max_shift) to
    best match the mean trace, which realigns the phases; on already-aligned
    simulation traces the best shift is zero, so this is a safe no-op there.
    Returns traces trimmed by max_shift on each side.
    """
    T = np.asarray(traces, dtype=np.float64)
    n, L = T.shape
    if L <= 2 * max_shift + 4:
        return T
    ref = T.mean(axis=0)
    refc = ref[max_shift:L - max_shift]
    refc = refc - refc.mean()
    refc_norm = np.dot(refc, refc) or 1e-9
    out = np.empty((n, L - 2 * max_shift), dtype=np.float64)
    for i in range(n):
        x = T[i] - T[i].mean()
        best_v, best_sh = -np.inf, 0
        for sh in range(-max_shift, max_shift + 1):
            v = np.dot(x[max_shift + sh:L - max_shift + sh], refc)
            if v > best_v:
                best_v, best_sh = v, sh
        out[i] = T[i][max_shift + best_sh:L - max_shift + best_sh]
    return out


def _byte_corr(known_bytes, traces):
    """(256, n_samples) signed correlation for an XOR target byte."""
    guesses = np.arange(256, dtype=np.uint32)
    xored = (known_bytes[:, None].astype(np.uint32) ^ guesses[None, :]) & 0xFF
    hyp = hamming_weight_vec(xored)
    return correlation_matrix(hyp, traces)


def _analyze_byte(known_bytes, traces):
    corr = _byte_corr(known_bytes, traces)        # (256, n_samples)
    signed_peak = corr.max(axis=1)                # best (positive) corr per guess
    poi_per_guess = corr.argmax(axis=1)
    order = np.argsort(signed_peak)[::-1]
    best, second = int(order[0]), int(order[1])
    top = [(int(g), float(signed_peak[g])) for g in order[:5]]
    return {
        "value": best,
        "corr": float(signed_peak[best]),
        "runner_up": second,
        "runner_up_corr": float(signed_peak[second]),
        "margin": float(signed_peak[best] - signed_peak[second]),
        "poi": int(poi_per_guess[best]),
        "top5": top,
    }


def _recover_a(counters, per_byte_traces):
    a = 0
    bytes_info = []
    for j in range(4):
        info = _analyze_byte((counters >> (8 * j)) & 0xFF, per_byte_traces[j])
        a |= info["value"] << (8 * j)
        bytes_info.append(info)
    return a, bytes_info


def _ntd_curve(counters, traces, per, steps=None):
    """Recover a at increasing trace counts; report the smallest count that
    first yields the value the full set converges to (the NTD). The steps now
    scale to the number of traces collected (geometric spacing up to the full
    set), so the curve reflects the actual batch size rather than a fixed cap."""
    n_total = len(counters)
    if steps is None:
        if n_total <= 50:
            steps = [n_total]
        else:
            steps = sorted(set(int(x) for x in
                               np.geomspace(50, n_total, num=10).astype(int)))
    full_a, _ = _recover_a(counters, [traces[:, b * per:(b + 1) * per] for b in range(4)])
    curve, ntd = [], None
    for n in steps:
        if n > len(counters):
            break
        a, _ = _recover_a(counters[:n], [traces[:n, b * per:(b + 1) * per] for b in range(4)])
        ok = a == full_a
        curve.append((n, ok))
        if ok and ntd is None:
            ntd = n
    return curve, ntd, full_a


def analyze(counters, traces, align=True):
    """Full CPA analysis. Returns a structured report dict.

    Traces are realigned (see align_traces) before correlation by default, which
    removes the hardware leak-loop start jitter; pass align=False to analyse the
    raw traces as captured.
    """
    if align:
        traces = align_traces(traces)
    per = traces.shape[1] // 4
    per_byte = [traces[:, b * per:(b + 1) * per] for b in range(4)]
    a, bytes_info = _recover_a(counters, per_byte)
    key0 = (a - CONSTANTS[0]) & MASK32
    curve, ntd, _ = _ntd_curve(counters, traces, per)

    mean_corr = float(np.mean([b["corr"] for b in bytes_info]))
    mean_margin = float(np.mean([b["margin"] for b in bytes_info]))
    # simple confidence: how far the winning correlations clear the runner-ups,
    # normalised by the per-guess correlation spread (noise scale).
    spread = float(np.mean([np.std([c for _, c in b["top5"]]) for b in bytes_info])) or 1e-9
    confidence = mean_margin / spread

    return {
        "attack": "cpa_first_round",
        "n_traces": int(len(counters)),
        "samples_per_trace": int(traces.shape[1]),
        "recovered_a": a,
        "recovered_key0": key0,
        "mean_peak_corr": mean_corr,
        "mean_margin": mean_margin,
        "confidence": confidence,
        "ntd": ntd,
        "ntd_curve": curve,
        "bytes": bytes_info,
    }
