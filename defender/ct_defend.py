"""CyberTrace defender -- the device owner's console.

Protects the target: assesses its leakage, configures its countermeasures,
monitors for probing, and rotates its key. Unlike the attacker, this program
owns the device and reports how well the defenses hold, not how to break them.

Usage:
  python ct_defend.py assess   [--traces N] [--hw]      leakage assessment (TVLA/NTD/suppression)
  python ct_defend.py monitor                            probing detection analytics
  python ct_defend.py toggle   <layer> <on|off> [--hw]  set a device countermeasure
  python ct_defend.py refresh  [--hw]                    rotate the device key
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np

import assess as assess_mod
import monitor as monitor_mod
from device import open_defender_transport


def cmd_assess(args):
    tr = open_defender_transport(args)
    print(f"[defender] leakage assessment via {tr.kind} (masking off vs on)...\n")
    r = assess_mod.assess_masking(tr, n_traces=args.traces)
    off, on, s = r["off"], r["on"], r["summary"]
    print("=" * 62)
    print("  LEAKAGE ASSESSMENT  (masking defense)")
    print("=" * 62)
    print(f"  {'metric':<22}{'OFF':>16}{'ON':>16}")
    print("  " + "-" * 54)
    print(f"  {'TVLA peak |t|':<22}{off['tvla_peak_t']:>16.1f}{on['tvla_peak_t']:>16.1f}")
    print(f"  {'TVLA verdict':<22}{('LEAKS' if off['tvla_leaks'] else 'pass'):>16}"
          f"{('LEAKS' if on['tvla_leaks'] else 'PASS'):>16}")
    print(f"  {'CPA peak corr':<22}{off['peak_corr']:>16.3f}{on['peak_corr']:>16.3f}")
    print(f"  {'NTD (traces)':<22}{str(off['ntd']):>16}{str(on['ntd']):>16}")
    print(f"  {'key recovered':<22}{('0x%08x' % off['recovered_key0']):>16}"
          f"{('0x%08x' % on['recovered_key0']):>16}")
    print("  " + "-" * 54)
    print(f"  correlation suppression : {s['suppression_ratio']:.1f}x ({s['suppression_db']:.1f} dB)")
    print(f"  TVLA                    : {s['tvla_verdict']}")
    print(f"  defense effective       : {s['defense_effective']}")
    print("=" * 62)
    if not args.no_plots:
        _plot_tvla(off["t_trace"], on["t_trace"], args.out)


def cmd_monitor(args):
    print("[defender] probing-detection analytics...\n")
    r = monitor_mod.analytics()
    print("=" * 62)
    print("  PROBING DETECTION ANALYTICS")
    print("=" * 62)
    print(f"  {'detector':<10}{'FPR':>8}{'latency(aggressive)':>22}{'latency(stealthy)':>20}")
    print("  " + "-" * 58)
    for name in ("rule", "ml"):
        if name not in r:
            continue
        d = r[name]
        la = d["latency_aggressive"] if d["latency_aggressive"] is not None else "miss"
        ls = d["latency_stealthy"] if d["latency_stealthy"] is not None else "miss"
        print(f"  {name:<10}{d['fpr']*100:>6.1f}%{str(la)+' req':>22}{str(ls)+' req':>20}")
    print("  " + "-" * 58)
    if r.get("has_ml"):
        print("  note: the stealthy attacker stays under every rule threshold; only")
        print("        the ML detector flags it (deviation from the learned normal).")
    print("=" * 62)


def cmd_toggle(args):
    tr = open_defender_transport(args)
    tr.set_defense(args.layer, args.state == "on")
    print(f"[defender] {args.layer} -> {args.state}  | device now: {tr.get_defenses()}")


def cmd_refresh(args):
    tr = open_defender_transport(args)
    new_key = int(np.random.default_rng().integers(0, 2**32))
    tr.rotate_key(new_key)
    print(f"[defender] key rotated -> 0x{new_key:08x} "
          f"(any traces an attacker already collected are now worthless)")


def _plot_tvla(t_off, t_on, out):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  (plot skipped: {e})"); return
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(np.abs(t_off), color="#d4645c", label="masking OFF", lw=0.9)
    ax.plot(np.abs(t_on), color="#3fb27f", label="masking ON", lw=0.9)
    ax.axhline(4.5, color="#9aa1a9", ls="--", label="TVLA threshold 4.5")
    ax.set_title("TVLA |t| per sample"); ax.set_xlabel("sample"); ax.set_ylabel("|t|")
    ax.legend(); fig.tight_layout()
    p = pathlib.Path(out) / "tvla.png"; p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=110); plt.close(fig)
    print(f"  TVLA plot -> {p}")


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="CyberTrace defender (device owner's console)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("assess")
    pa.add_argument("--traces", type=int, default=800)
    pa.add_argument("--out", default=str(root / "data" / "reports"))
    pa.add_argument("--no-plots", action="store_true")
    pa.set_defaults(func=cmd_assess)

    pm = sub.add_parser("monitor"); pm.set_defaults(func=cmd_monitor)

    pt = sub.add_parser("toggle")
    pt.add_argument("layer", choices=["masking", "constant_time", "nonce"])
    pt.add_argument("state", choices=["on", "off"])
    pt.set_defaults(func=cmd_toggle)

    pr = sub.add_parser("refresh"); pr.set_defaults(func=cmd_refresh)

    for p in (pa, pt, pr):
        p.add_argument("--hw", action="store_true")
        p.add_argument("--port", default="/dev/ttyAMA0")
        p.add_argument("--seed", type=int, default=0)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
