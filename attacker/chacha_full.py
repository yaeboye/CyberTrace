"""Full 256-bit ChaCha20 key recovery via all four first-round columns.

The first round applies one quarter-round per column:
  QR(0,4,8,12)  b=key0 c=key4 d=counter
  QR(1,5,9,13)  b=key1 c=key5 d=nonce0
  QR(2,6,10,14) b=key2 c=key6 d=nonce1
  QR(3,7,11,15) b=key3 c=key7 d=nonce2
In each, a = const_k + key_k (fixed), then d ^= a; d = rotl(d,16); then c += d.
So with a known-varying value in the d slot (the counter for column 0, a nonce
word for columns 1-3), two targets fall out per column:
  XOR  d ^ a         -> recover a = const_k + key_k  -> key_k = a - const_k
  ADD  key_{k+4} + D -> recover key_{k+4}  (D = rotl(d ^ a,16), known after a)
Four columns x two words = the full eight-word key. Columns 1-3 require
chosen-nonce collection (the nonce is public/attacker-set). Validated in sim
here; the same recovery runs on hardware once the firmware leaks each column.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpi" / "attacks" / "cpa"))
from chacha20_model import CONSTANTS, MASK32, hamming_weight_vec  # noqa: E402
from cpa_engine import attack_byte_xor, attack_byte  # noqa: E402

FIRMWARE_KEY = [0xDEADBEEF, 0xCAFEBABE, 0x13371337, 0xA5A5A5A5,
                0x5A5A5A5A, 0xF0F0F0F0, 0x0F0F0F0F, 0xBAADF00D]


def _rotl32(v, n):
    v &= MASK32
    return ((v << n) | (v >> (32 - n))) & MASK32


def simulate_column(key_lo, key_hi, const, n_traces, n_samples=320,
                    noise_std=2.0, leak_scale=1.0, seed=None):
    """Traces for one column: 8 phase windows carry HW of, in order, the four
    bytes of the XOR intermediate (d ^ a) then the four bytes of the ADD
    intermediate (key_hi + D)."""
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 2**32, size=n_traces, dtype=np.uint64).astype(np.uint32)
    a = (const + key_lo) & MASK32
    xor_val = x ^ a
    D = _rotl32(xor_val.astype(np.uint64), 16).astype(np.uint32)
    add_val = (key_hi + D) & MASK32

    per = n_samples // 8
    traces = rng.normal(0, noise_std, size=(n_traces, n_samples))
    phases = ([((xor_val >> (8 * j)) & 0xFF) for j in range(4)] +
              [((add_val >> (8 * j)) & 0xFF) for j in range(4)])
    for p, byte_vals in enumerate(phases):
        hw = hamming_weight_vec(byte_vals).astype(np.float64)
        traces[:, p * per:(p + 1) * per] += leak_scale * hw[:, None]
    return x, traces


def recover_column(x, traces, const):
    """Recover (key_lo, key_hi) for a column from its 8-phase traces."""
    per = traces.shape[1] // 8
    win = [traces[:, p * per:(p + 1) * per] for p in range(8)]

    a = 0
    for j in range(4):
        best, _, _ = attack_byte_xor((x >> (8 * j)) & 0xFF, win[j])
        a |= best << (8 * j)
    key_lo = (a - const) & MASK32

    D = _rotl32((x ^ a).astype(np.uint64), 16).astype(np.uint32)
    carry = np.zeros(len(x), dtype=np.uint32)
    key_hi = 0
    for j in range(4):
        known = (D >> (8 * j)) & 0xFF
        best, _, _ = attack_byte(known, carry, win[4 + j])
        key_hi |= best << (8 * j)
        totals = known.astype(np.uint32) + best + carry
        carry = (totals >= 256).astype(np.uint32)
    return key_lo, key_hi


def recover_full_key(key=FIRMWARE_KEY, n_traces=4000, noise_std=2.0, seed=0, verbose=True):
    recovered = [None] * 8
    for col in range(4):
        x, traces = simulate_column(key[col], key[col + 4], CONSTANTS[col],
                                    n_traces, noise_std=noise_std, seed=seed + col)
        lo, hi = recover_column(x, traces, CONSTANTS[col])
        recovered[col] = lo
        recovered[col + 4] = hi
        if verbose:
            ok_lo = lo == key[col]
            ok_hi = hi == key[col + 4]
            src = "counter" if col == 0 else f"nonce{col - 1}"
            print(f"  col{col} ({src:7}): key{col}=0x{lo:08x} {'OK' if ok_lo else 'X'}  "
                  f"key{col + 4}=0x{hi:08x} {'OK' if ok_hi else 'X'}")
    return recovered


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Full 256-bit ChaCha20 key recovery (sim)")
    ap.add_argument("--traces", type=int, default=4000)
    ap.add_argument("--noise", type=float, default=2.0)
    args = ap.parse_args()

    print("=== Full ChaCha20 key recovery (256-bit, simulation) ===\n")
    rec = recover_full_key(n_traces=args.traces, noise_std=args.noise)
    match = rec == FIRMWARE_KEY
    print("\nrecovered key:", " ".join(f"{w:08x}" for w in rec))
    print("true key:     ", " ".join(f"{w:08x}" for w in FIRMWARE_KEY))
    print(f"\nFULL KEY RECOVERED: {match}")
