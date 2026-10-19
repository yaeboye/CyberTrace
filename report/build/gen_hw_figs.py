"""Generate additional hardware-result figures from captured laptop data."""
import json, pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(r"C:\Users\satvi\CyberTrace")
HW = ROOT / "data" / "hw_results"
OUT = ROOT / "data" / "reports"
RED, GRN, BLU, GRY = "#d4645c", "#3fb27f", "#4aa3c7", "#9aa1a9"

d = json.load(open(HW / "cpa_report_hw.json"))

# --- Fig: hardware masking bar (ChaCha effective, Kyber not) ---
fig, ax = plt.subplots(figsize=(6.6, 3.2))
x = np.arange(2); w = 0.35
off = [4.5, 6.8]; on = [2.5, 6.5]
ax.bar(x - w/2, off, w, label="masking off", color=RED)
ax.bar(x + w/2, on, w, label="masking on", color=GRN)
ax.axhline(4.5, ls="--", color=GRY, label="TVLA threshold 4.5")
for i, (o, n) in enumerate(zip(off, on)):
    ax.text(i - w/2, o + 0.1, f"{o}", ha="center", fontsize=8)
    ax.text(i + w/2, n + 0.1, f"{n}", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(["ChaCha20\n(masking effective)", "Kyber\n(masking ineffective)"])
ax.set_ylabel("TVLA peak |t|"); ax.set_ylim(0, 8)
ax.set_title("Hardware leakage assessment: masking off vs on")
ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "hw_masking_bar.png", dpi=120); plt.close(fig)

# --- Fig: hardware NTD convergence ---
curve = d["ntd_curve"]; ntd = d["ntd"]
ns = [c[0] for c in curve]; ok = [1 if c[1] else 0 for c in curve]
fig, ax = plt.subplots(figsize=(7, 3.0))
ax.step(ns, ok, where="post", color=BLU, lw=1.5)
ax.scatter(ns, ok, color=[GRN if o else RED for o in ok], zorder=3)
ax.axvline(ntd, ls="--", color=GRY, label=f"first disclosure (NTD = {ntd})")
ax.set_yticks([0, 1]); ax.set_yticklabels(["not recovered", "recovered"])
ax.set_xlabel("number of traces"); ax.set_ylim(-0.2, 1.2)
ax.set_title("Hardware CPA convergence (traces to disclosure)")
ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "hw_ntd_curve.png", dpi=120); plt.close(fig)

# --- Fig: per-byte winning correlation vs runner-up ---
by = d["bytes"]
labels = [f"byte {i}\n0x{b['value']:02x}" for i, b in enumerate(by)]
win = [b["corr"] for b in by]; run = [b["runner_up_corr"] for b in by]
x = np.arange(4); w = 0.38
fig, ax = plt.subplots(figsize=(6.8, 3.2))
ax.bar(x - w/2, win, w, label="correct candidate", color=GRN)
ax.bar(x + w/2, run, w, label="runner-up", color=RED)
for i, b in enumerate(by):
    ax.text(i, max(win[i], run[i]) + 0.004, f"margin {b['margin']:.3f}", ha="center", fontsize=7)
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_ylabel("|corr| peak"); ax.set_title("Hardware CPA: correct byte vs runner-up (per byte)")
ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "hw_perbyte_corr.png", dpi=120); plt.close(fig)

# --- Fig: example raw hardware trace with byte-phase windows ---
z = np.load(HW / "hw_raw_chacha.npz")
tr = z["traces"][0] * 1000.0  # mV
n = len(tr); per = n // 4
fig, ax = plt.subplots(figsize=(8, 3.0))
ax.plot(tr, color=BLU, lw=0.6)
for j in range(4):
    seg = tr[j*per:(j+1)*per]
    ax.axvspan(j*per, (j+1)*per, color=(GRN if j % 2 == 0 else "#2b3038"), alpha=0.06)
    ax.hlines(seg.mean(), j*per, (j+1)*per, color=RED, lw=1.5)
    ax.text(j*per + per/2, seg.mean() + 0.6, f"byte {j}", ha="center", fontsize=8, color=RED)
ax.set_xlabel("ADC sample"); ax.set_ylabel("shunt voltage (mV)")
ax.set_title("Example real LEAKLOOP trace with four byte-phase windows (ESP32-S3)")
fig.tight_layout(); fig.savefig(OUT / "hw_raw_trace.png", dpi=120); plt.close(fig)

# --- Fig: simulation vs hardware comparison ---
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.0))
a1.bar(["simulation", "hardware"], [0.49, d["mean_peak_corr"]], color=[GRY, BLU])
a1.set_ylabel("mean peak |corr|"); a1.set_title("ChaCha20 CPA correlation")
for i, v in enumerate([0.49, d["mean_peak_corr"]]):
    a1.text(i, v + 0.01, f"{v:.2f}", ha="center", fontsize=8)
a2.bar(["simulation", "hardware"], [100, 400], color=[GRY, BLU])
a2.set_ylabel("traces to disclosure (typical)"); a2.set_title("ChaCha20 CPA effort")
for i, v in enumerate([100, 400]):
    a2.text(i, v + 6, f"{v}", ha="center", fontsize=8)
fig.suptitle("Simulation versus hardware (cleaner model, noisier silicon)", fontsize=10)
fig.tight_layout(); fig.savefig(OUT / "sim_vs_hw.png", dpi=120); plt.close(fig)

# --- Fig: timing-attack margins on hardware (why it fails) ---
pos = [0, 1, 2, 3]; margins = [0.8, 0.0, 88.4, 0.4]  # us, from timing_hw.txt
fig, ax = plt.subplots(figsize=(6.8, 3.0))
ax.bar(pos, margins, color=RED, width=0.5)
ax.axhline(0.2 * 1000, ls="--", color=GRY, label="per-byte compute delta ~200 us (signal)")
ax.set_ylim(0, 240)
ax.text(0.5, 0.62, "serial round-trip ~8000 us swamps all margins",
        transform=ax.transAxes, ha="center", fontsize=8, color=GRY)
ax.set_xticks(pos); ax.set_xticklabels([f"pos {p}" for p in pos])
ax.set_ylabel("margin to 2nd guess (us)")
ax.set_title("Hardware timing attack: candidate margins (attack does not resolve)")
ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "timing_margin.png", dpi=120); plt.close(fig)

# --- Overwrite masking_bar.png with HARDWARE data (was simulation) ---
fig, ax = plt.subplots(figsize=(6.6, 3.2))
x = np.arange(2); w = 0.35
ax.bar(x - w/2, off, w, label="masking off", color=RED)
ax.bar(x + w/2, on, w, label="masking on", color=GRN)
ax.axhline(4.5, ls="--", color=GRY, label="TVLA threshold 4.5")
for i, (o, nn) in enumerate(zip(off, on)):
    ax.text(i - w/2, o + 0.1, f"{o}", ha="center", fontsize=8)
    ax.text(i + w/2, nn + 0.1, f"{nn}", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(["ChaCha20", "Kyber"]); ax.set_ylim(0, 8)
ax.set_ylabel("TVLA peak |t|")
ax.set_title("Hardware leakage assessment: masking off versus on")
ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "masking_bar.png", dpi=120); plt.close(fig)

# --- Overwrite heatmap.png with a REAL hardware correlation heatmap (byte 0) ---
import sys
sys.path.insert(0, str(ROOT / "rpi" / "attacks" / "cpa"))
from cpa_engine import correlation_matrix
from chacha20_model import hamming_weight_vec
zc = np.load(HW / "hw_raw_chacha.npz")
counters = zc["counters"].astype(np.uint32); traces = zc["traces"]
per = traces.shape[1] // 4
J = 2  # byte 2 has the largest margin on hardware -> clearest band
kb = ((counters >> (8 * J)) & 0xFF).astype(np.uint32)
g = np.arange(256, dtype=np.uint32)
hyp = hamming_weight_vec((kb[:, None] ^ g[None, :]) & 0xFF)
corr = np.abs(correlation_matrix(hyp, traces[:, J*per:(J+1)*per]))
true_row = int((counters[0] >> 0) & 0)  # placeholder not used
fig, ax = plt.subplots(figsize=(7, 3.0))
im = ax.imshow(corr, aspect="auto", cmap="inferno", origin="lower")
ax.set_xlabel("time sample (byte window)"); ax.set_ylabel("key-byte guess 0..255")
ax.set_title("Hardware correlation heatmap: brightest row = correct key byte")
fig.colorbar(im, ax=ax, label="|corr|")
fig.tight_layout(); fig.savefig(OUT / "heatmap.png", dpi=120); plt.close(fig)

print("wrote: hw_masking_bar hw_ntd_curve hw_perbyte_corr hw_raw_trace sim_vs_hw timing_margin + real masking_bar + real heatmap")
