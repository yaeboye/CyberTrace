"""Kyber arithmetic + leakage model for side-channel key recovery.

Scope: the CPA target is Kyber's NTT-domain pointwise multiplication during
decapsulation, t_i = s_hat_i * u_hat_i mod q, where u_hat is attacker-known
(from the ciphertext) and s_hat is the secret key in the NTT domain. The
Hamming weight of t_i leaks; varying u_hat_i and guessing s_hat_i recovers the
secret coefficient -- the standard published Kyber CPA target (Primas/Pessl et
al.), a genuine key recovery rather than a leakage demonstration.

This module is the portable reference math; the firmware runs the same
operation on-device and amplifies the leak for the slow ADC.
"""

from __future__ import annotations

import numpy as np

KYBER_Q = 3329
KYBER_N = 256


def hw(x):
    """Hamming weight of the low 12 bits (a Kyber coefficient is < q < 2^12)."""
    return bin(int(x) & 0xFFF).count("1")


def hw_vec(x):
    x = np.asarray(x, dtype=np.int64) & 0xFFF
    w = np.zeros(x.shape, dtype=np.int64)
    for _ in range(12):
        w += x & 1
        x >>= 1
    return w


def pointwise(s_hat_i, u_hat_i):
    """One NTT-domain product coefficient mod q -- the leaking intermediate."""
    return (int(s_hat_i) * int(u_hat_i)) % KYBER_Q
