import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sys, pathlib
ROOT = pathlib.Path(r"C:\Users\satvi\CyberTrace")
sys.path.insert(0, str(ROOT / "attacker"))
sys.path.insert(0, str(ROOT / "rpi" / "attacks" / "cpa"))
out = str(ROOT / "data" / "reports") + "\\"


def box(ax, x, y, t, w=1.9, h=0.9, c="#e8eef3"):
    ax.add_patch(plt.Rectangle((x, y), w, h, fc=c, ec="#2b3a55", lw=1.3))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=8)


# Fig 3.2 quarter-round data flow
fig, ax = plt.subplots(figsize=(7.5, 3.2)); ax.axis("off")
box(ax, 0.2, 2.0, "const0", w=1.5, h=0.7)
box(ax, 2.0, 2.0, "key0", w=1.5, h=0.7, c="#f3e8e8")
box(ax, 0.2, 0.3, "counter", w=1.5, h=0.7, c="#e8f3ea")
box(ax, 4.0, 2.0, "a = const0 + key0", w=2.6, h=0.7, c="#eef0f2")
box(ax, 4.0, 0.3, "d = counter XOR a", w=2.6, h=0.7, c="#f3eee8")
ax.annotate("", xy=(4.0, 2.35), xytext=(3.5, 2.35), arrowprops=dict(arrowstyle="->"))
ax.annotate("", xy=(5.3, 1.0), xytext=(5.3, 2.0), arrowprops=dict(arrowstyle="->"))
ax.annotate("", xy=(4.0, 0.65), xytext=(1.7, 0.65), arrowprops=dict(arrowstyle="->"))
ax.text(5.4, 1.4, "CPA target", color="#b23", fontsize=8)
ax.set_xlim(0, 7.3); ax.set_ylim(0, 3.0)
ax.set_title("Figure 3.2  First-round data flow and the CPA target")
fig.tight_layout(); fig.savefig(out + "quarterround.png", dpi=120); plt.close(fig)

# Fig 3.3 wiring
fig, ax = plt.subplots(figsize=(7.5, 3.2)); ax.axis("off")
box(ax, 0.2, 1.2, "Power 5V")
box(ax, 2.6, 1.2, "10 ohm shunt", c="#f3eee8")
box(ax, 5.0, 1.2, "ESP32-S3 target")
box(ax, 2.6, 2.6, "ADS1115 ADC", c="#eef0f2")
box(ax, 5.0, 2.6, "Raspberry Pi 5", c="#e8f3ea")
ax.annotate("", xy=(2.6, 1.65), xytext=(2.1, 1.65), arrowprops=dict(arrowstyle="->"))
ax.annotate("", xy=(5.0, 1.65), xytext=(4.5, 1.65), arrowprops=dict(arrowstyle="->"))
ax.annotate("", xy=(3.55, 2.6), xytext=(3.55, 2.1), arrowprops=dict(arrowstyle="->")); ax.text(3.6, 2.35, "shunt V", fontsize=7)
ax.annotate("", xy=(5.0, 3.05), xytext=(4.5, 3.05), arrowprops=dict(arrowstyle="<->")); ax.text(4.35, 3.15, "I2C", fontsize=7)
ax.annotate("", xy=(5.95, 2.6), xytext=(5.95, 2.1), arrowprops=dict(arrowstyle="<->")); ax.text(6.0, 2.35, "UART", fontsize=7)
ax.set_xlim(0, 7.3); ax.set_ylim(0.8, 3.4)
ax.set_title("Figure 3.3  Measurement setup and wiring")
fig.tight_layout(); fig.savefig(out + "wiring.png", dpi=120); plt.close(fig)

# Fig 5.5 correlation heatmap
from synthetic_traces import generate_first_round_traces
from cpa_engine import correlation_matrix
from chacha20_model import hamming_weight_vec
c, t, s = generate_first_round_traces(0xDEADBEEF, n_traces=2000, noise_std=1.0, seed=3)
kb = (c >> 0) & 0xFF
g = np.arange(256)
hyp = hamming_weight_vec((kb[:, None] ^ g[None, :]) & 0xFF)
corr = np.abs(correlation_matrix(hyp, t[:, s[0] - 20:s[0] + 20]))
fig, ax = plt.subplots(figsize=(7, 3.0))
im = ax.imshow(corr, aspect="auto", cmap="inferno", origin="lower")
ax.set_xlabel("time sample (byte-0 window)"); ax.set_ylabel("key guess 0..255")
ax.set_title("Figure 5.5  Correlation heatmap: bright row = correct key byte")
fig.colorbar(im, ax=ax, label="|corr|")
fig.tight_layout(); fig.savefig(out + "heatmap.png", dpi=120); plt.close(fig)

# Fig 5.6 masking suppression bar
fig, ax = plt.subplots(figsize=(6.5, 3.0))
x = np.arange(2); w = 0.35
ax.bar(x - w / 2, [7.7, 25.1], w, label="masking off", color="#d4645c")
ax.bar(x + w / 2, [3.0, 2.6], w, label="masking on", color="#3fb27f")
ax.axhline(4.5, ls="--", color="#555", label="TVLA threshold 4.5")
ax.set_xticks(x); ax.set_xticklabels(["ChaCha20", "Kyber"]); ax.set_ylabel("TVLA peak |t|")
ax.set_title("Figure 5.6  Leakage assessment: masking off vs on"); ax.legend()
fig.tight_layout(); fig.savefig(out + "masking_bar.png", dpi=120); plt.close(fig)
print("figures: quarterround wiring heatmap masking_bar")
