"""Collect KYBERLEAK traces from the real ESP32-S3 and plot the coefficient CPA.

Run on the Raspberry Pi (hardware attached), inside the ct-venv:
    python3 kyber_cpa_hw_plot.py
Writes data/reports/kyber_cpa.png and prints the recovered coefficient.

Paths below assume the Pi layout (~/CyberTrace). Adjust the three sys.path
inserts and the output path if the repo lives elsewhere.
"""
import sys
import numpy as np

sys.path.insert(0, "/home/student/CyberTrace/attacker")
sys.path.insert(0, "/home/student/CyberTrace/rpi/attacks/cpa")
sys.path.insert(0, "/home/student/CyberTrace/rpi/common")
from transport import HwTransport
from kyber_model import KYBER_Q, hw_vec
from cpa_engine import correlation_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

tr = HwTransport(port="/dev/ttyAMA0")
n = 1200
rng = np.random.default_rng(0)
u = rng.integers(0, KYBER_Q, size=n).astype(np.int64)
rows = [tr.kyberleak(int(x)) for x in u]
L = min(len(r) for r in rows)
traces = np.array([r[:L] for r in rows])

g = np.arange(KYBER_Q, dtype=np.int64)
hyp = hw_vec((u[:, None] * g[None, :]) % KYBER_Q).astype(np.float64)
peak = np.abs(correlation_matrix(hyp, traces)).max(axis=1)
best = int(np.argmax(peak))
print("KYBER_FIG best=%d corr=%.4f true_corr=%.4f" % (best, peak[best], peak[1234]))

fig, ax = plt.subplots(figsize=(8, 3.2))
ax.plot(peak, color="#4aa3c7", lw=0.5)
ax.axvline(1234, color="#d4645c", ls="--", lw=1, label="true s_hat = 1234")
ax.plot(best, peak[best], "o", color="#d4645c", ms=5)
ax.set_xlabel("candidate coefficient (0..q-1)")
ax.set_ylabel("|corr| peak")
ax.set_title("Kyber coefficient CPA: correct secret versus all guesses (hardware)")
ax.legend()
fig.tight_layout()
fig.savefig("/home/student/CyberTrace/data/reports/kyber_cpa.png", dpi=120)
print("saved kyber_cpa.png")
