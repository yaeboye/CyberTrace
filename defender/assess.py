"""Defender leakage assessment: quantify how well each countermeasure works.

Combines three views on the device the defender is protecting:
  - TVLA (Welch t-test) with the countermeasure off then on -- does exploitable
    leakage exist at all?
  - NTD comparison -- traces-to-disclosure unprotected vs protected (the attack
    engine is reused so the numbers are the attacker's own).
  - correlation suppression -- peak CPA correlation off vs on, as a ratio / dB.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "attacker"))
import cpa  # noqa: E402  (attacker's analysis engine, reused honestly)
import tvla  # noqa: E402


def _collect(transport, n, rng):
    counters = rng.integers(0, 2**32, size=n, dtype=np.uint64).astype(np.uint32)
    rows = [transport.leakloop(int(c)) for c in counters]
    L = min(len(r) for r in rows)
    return counters, np.array([r[:L] for r in rows])


def assess_masking(transport, n_traces=800, n_tvla=400, seed=0):
    rng = np.random.default_rng(seed)
    out = {}

    for state in ("off", "on"):
        transport.set_defense("masking", state == "on")

        tv = tvla.assess(transport, n_each=n_tvla, rng=np.random.default_rng(seed + 1))
        counters, traces = _collect(transport, n_traces, np.random.default_rng(seed + 2))
        cpa_res = cpa.analyze(counters, traces)

        out[state] = {
            "tvla_peak_t": tv["peak_t"],
            "tvla_leaks": tv["leaks"],
            "ntd": cpa_res["ntd"],
            "peak_corr": cpa_res["mean_peak_corr"],
            "recovered_key0": cpa_res["recovered_key0"],
            "t_trace": tv["t_trace"],
        }

    transport.set_defense("masking", False)

    off, on = out["off"], out["on"]
    # When TVLA passes (no exploitable leakage) the CPA "recovery" is just a
    # consistent wrong guess, so its NTD is meaningless -- blank it out.
    if not on["tvla_leaks"]:
        on["ntd"] = None
    ratio = off["peak_corr"] / max(on["peak_corr"], 1e-9)
    out["summary"] = {
        "suppression_ratio": ratio,
        "suppression_db": float(20 * np.log10(ratio)),
        "tvla_verdict": f"off: {'LEAKS' if off['tvla_leaks'] else 'pass'} (t={off['tvla_peak_t']:.1f}) | "
                        f"on: {'LEAKS' if on['tvla_leaks'] else 'PASS'} (t={on['tvla_peak_t']:.1f})",
        # authoritative criterion: exploitable leakage present unprotected,
        # absent (TVLA pass) once the countermeasure is on.
        "defense_effective": off["tvla_leaks"] and not on["tvla_leaks"],
    }
    return out
