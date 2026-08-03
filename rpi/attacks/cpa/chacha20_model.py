import numpy as np

MASK32 = 0xFFFFFFFF

CONSTANTS = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]


def rotl32(x, n):
    x &= MASK32
    return ((x << n) | (x >> (32 - n))) & MASK32


def quarter_round(a, b, c, d):
    a = (a + b) & MASK32
    d ^= a
    d = rotl32(d, 16)
    c = (c + d) & MASK32
    b ^= c
    b = rotl32(b, 12)
    a = (a + b) & MASK32
    d ^= a
    d = rotl32(d, 8)
    c = (c + d) & MASK32
    b ^= c
    b = rotl32(b, 7)
    return a, b, c, d


def build_state(key_words, counter, nonce_words):
    return CONSTANTS + list(key_words) + [counter] + list(nonce_words)


def target_addition(counter, key_word0):
    """Simplified/idealized CPA target: the ARX addition combining a known,
    per-block varying value (the counter, sent in clear like an IV) with the
    first secret key word. This mirrors the standard CPA teaching setup
    (known varying input + secret key, byte-wise with carry chaining) used
    for AES first-round attacks.

    Full quarterround(0,4,8,12) mixes the counter into the state via XOR
    *after* an addition of two fixed operands (const + key_word0), so the
    counter does not appear as a direct addition operand in unmodified
    ChaCha20. Attacking the real ARX round requires a guess-and-determine
    chain across quarterround steps (recovering key_word0 first, then using
    it to compute the XOR/rotate output before the second addition). That
    full chain is left as a documented extension; this simplified target
    validates the CPA engine's core statistics (Hamming-weight leakage,
    carry-chained byte recovery) end-to-end before applying it to real
    hardware traces."""
    return (counter + key_word0) & MASK32


def hamming_weight_vec(x):
    x = np.asarray(x, dtype=np.uint32) & 0xFF
    weight = np.zeros(x.shape, dtype=np.uint16)
    v = x.copy()
    for _ in range(8):
        weight += (v & 1).astype(np.uint16)
        v >>= 1
    return weight
