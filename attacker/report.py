"""Human-readable console report, JSON artifact, and plots for attacker runs."""

from __future__ import annotations

import json
import pathlib

import numpy as np


def _bar(width, frac):
    fill = int(round(frac * width))
    return "#" * fill + "-" * (width - fill)


def print_cpa(result, known_key0=None):
    r = result
    print("=" * 62)
    print("  CPA FIRST-ROUND ANALYSIS")
    print("=" * 62)
    print(f"  traces={r['n_traces']}  samples/trace={r['samples_per_trace']}")
    print(f"  recovered a    = 0x{r['recovered_a']:08x}")
    print(f"  recovered key0 = 0x{r['recovered_key0']:08x}  (key0 = a - const0)")
    if known_key0 is not None:
        print(f"  verification   : {'MATCH' if r['recovered_key0'] == known_key0 else 'MISMATCH'} "
              f"(ground-truth 0x{known_key0:08x})")
    print(f"  mean peak corr = {r['mean_peak_corr']:.3f}   mean margin = {r['mean_margin']:.3f}"
          f"   confidence = {r['confidence']:.1f}")
    print(f"  NTD (traces to disclosure) = {r['ntd']}")
    print()
    print("  per-byte detail:")
    print("  byte  value  corr   runner-up  margin  POI   top-3 candidates")
    print("  " + "-" * 58)
    for j, b in enumerate(r["bytes"]):
        cands = " ".join(f"{g:02x}:{c:.2f}" for g, c in b["top5"][:3])
        print(f"   {j}    0x{b['value']:02x}  {b['corr']:.3f}   0x{b['runner_up']:02x}:{b['runner_up_corr']:.2f}"
              f"   {b['margin']:.3f}  {b['poi']:>4}  {cands}")
    print()
    print("  NTD convergence:")
    for n, ok in r["ntd_curve"]:
        print(f"    {n:>5} traces  [{_bar(20, 1.0 if ok else 0.0)}]  {'recovered' if ok else 'not yet'}")
    print("=" * 62)


def save_json(result, path):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # ints like 0xdeadbeef serialize fine; tuples -> lists
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(x) for x in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return o
    path.write_text(json.dumps(clean(result), indent=2))
    print(f"  JSON report -> {path}")


def plot_cpa(result, counters, traces, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  (plot skipped: {e})")
        return
    from cpa import _byte_corr  # reuse the signed-corr computation
    per = traces.shape[1] // 4

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    # (0,0) per-byte peak correlation
    ax = axes[0, 0]
    ax.bar(range(4), [b["corr"] for b in result["bytes"]], color="#4aa3c7")
    ax.bar(range(4), [b["runner_up_corr"] for b in result["bytes"]], color="#d4645c", width=0.4)
    ax.set_title("per-byte peak corr (blue=best, red=runner-up)")
    ax.set_xlabel("key byte"); ax.set_ylabel("|corr|")

    # (0,1) NTD convergence
    ax = axes[0, 1]
    ns = [n for n, _ in result["ntd_curve"]]
    oks = [1 if ok else 0 for _, ok in result["ntd_curve"]]
    ax.plot(ns, oks, "o-", color="#3fb27f")
    ax.set_title(f"NTD convergence (NTD={result['ntd']})")
    ax.set_xlabel("traces"); ax.set_ylabel("recovered (1/0)"); ax.set_ylim(-0.1, 1.1)

    # (1,0) correlation vs all guesses for byte 0 (shows the spike)
    ax = axes[1, 0]
    corr0 = np.abs(_byte_corr((counters >> 0) & 0xFF, traces[:, 0:per])).max(axis=1)
    ax.plot(corr0, color="#9aa1a9")
    ax.plot(result["bytes"][0]["value"], corr0[result["bytes"][0]["value"]], "ro")
    ax.set_title("byte 0: |corr| across 256 guesses")
    ax.set_xlabel("guess"); ax.set_ylabel("|corr|")

    # (1,1) a leakage trace with phase boundaries
    ax = axes[1, 1]
    ax.plot(traces[0], color="#4aa3c7", lw=0.8)
    for b in range(1, 4):
        ax.axvline(b * per, color="#d6a44c", ls="--", lw=0.8)
    ax.set_title("example trace (dashed = byte-phase boundaries)")
    ax.set_xlabel("sample"); ax.set_ylabel("ADC")

    fig.tight_layout()
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  plots -> {path}")
