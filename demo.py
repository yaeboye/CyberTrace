"""CyberTrace full software demonstration (no hardware required).

Runs the real attacker and defender programs in sequence via their actual CLIs,
so the demo shows the exact commands a user would type. Every step runs against
the simulator; add --hw to any individual command to drive the real ESP32.

  python demo.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PY = sys.executable

STEPS = [
    ("ATTACKER  -  ChaCha20 power CPA (first-round key word)",
     ["attacker/ct_attack.py", "cpa", "--traces", "1500", "--seed", "1", "--no-plots"]),
    ("ATTACKER  -  full 256-bit ChaCha20 key recovery",
     ["attacker/chacha_full.py", "--traces", "4000"]),
    ("ATTACKER  -  Kyber NTT-coefficient CPA (post-quantum)",
     ["attacker/ct_attack.py", "kyber", "--traces", "2500", "--seed", "1"]),
    ("ATTACKER  -  timing attack",
     ["attacker/ct_attack.py", "timing"]),
    ("ATTACKER  -  replay attack (nonce off)",
     ["attacker/ct_attack.py", "replay"]),
    ("DEFENDER  -  ChaCha20 leakage assessment (TVLA / NTD / suppression)",
     ["defender/ct_defend.py", "assess", "--target", "chacha", "--traces", "800", "--no-plots"]),
    ("DEFENDER  -  Kyber leakage assessment",
     ["defender/ct_defend.py", "assess", "--target", "kyber", "--traces", "2500", "--no-plots"]),
    ("DEFENDER  -  probing-detection analytics (rule vs ML, FPR + latency)",
     ["defender/ct_defend.py", "monitor"]),
]


def run(title, argv):
    print("\n" + "#" * 64)
    print("# " + title)
    print("# $ python " + " ".join(argv))
    print("#" * 64)
    script = ROOT / argv[0]
    subprocess.run([PY, str(script), *argv[1:]], cwd=script.parent)


def main():
    print("=" * 64)
    print("  CyberTrace -- full software demonstration (simulator)")
    print("  attacker: key recovery only   |   defender: device owner's console")
    print("=" * 64)
    for title, argv in STEPS:
        run(title, argv)
    print("\n" + "=" * 64)
    print("  demo complete. add --hw to any command to drive the real ESP32.")
    print("=" * 64)


if __name__ == "__main__":
    main()
