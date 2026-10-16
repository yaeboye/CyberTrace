"""Archive raw hardware power traces for ChaCha20 CPA and Kyber CPA.

Run on the Raspberry Pi (hardware attached), inside the ct-venv:
    python3 save_raw_hw.py
Writes data/hw_raw_chacha.npz (counters, traces) and
       data/hw_raw_kyber.npz  (u, traces).

These are the raw ADS1115 shunt-voltage traces behind the report figures,
kept as archival evidence so the analysis can be re-run without the device.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/student/CyberTrace/attacker")
sys.path.insert(0, "/home/student/CyberTrace/rpi/attacks/cpa")
sys.path.insert(0, "/home/student/CyberTrace/rpi/common")
from transport import HwTransport
import cpa
from kyber_model import KYBER_Q

tr = HwTransport(port="/dev/ttyAMA0")

# ChaCha20 first-round CPA raw traces
counters, traces = cpa.collect(tr, 800, progress=400)
np.savez_compressed("/home/student/CyberTrace/data/hw_raw_chacha.npz",
                    counters=counters, traces=traces)
print("chacha raw", traces.shape)

# Kyber pointwise-multiply raw traces
rng = np.random.default_rng(1)
u = rng.integers(0, KYBER_Q, size=1000).astype(np.int64)
rows = [tr.kyberleak(int(x)) for x in u]
L = min(len(r) for r in rows)
kt = np.array([r[:L] for r in rows])
np.savez_compressed("/home/student/CyberTrace/data/hw_raw_kyber.npz", u=u, traces=kt)
print("kyber raw", kt.shape)
