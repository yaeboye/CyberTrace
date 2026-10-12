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


def first_round_a(key_word0):
    """a = state0 + state4 = const0 + key0, the fixed sum formed at the very
    start of QR(0,4,8,12). Known once key0 is known; const0 is public."""
    return (CONSTANTS[0] + key_word0) & MASK32


def first_round_xor_target(counter, key_word0):
    """Real ChaCha20 first-round CPA target (no simplification).

    In QR(0,4,8,12):
        a = const0 + key0          # fixed across traces
        d = counter ^ a            # known-varying counter XORs secret-derived a
        d = rotl(d, 16)

    The XOR intermediate (counter ^ a) is the cleanest CPA target: byte j
    depends only on counter byte j and a byte j, with no carry between bytes,
    and the following rotl(16) is byte-aligned so it merely relabels which
    sample window a byte leaks in. Recover a byte-wise, then key0 = a - const0.

    This is the correct target for a real ChaCha20 core, unlike target_addition
    which assumes the counter is added to the key directly (it is not -- the
    counter enters by XOR against const0+key0)."""
    return counter ^ first_round_a(key_word0)


def first_round_key4_target(counter, key_word0, key_word4):
    """Second-stage target in the same quarterround, for recovering key4 once
    key0 (hence a and d) is known:
        d = rotl(counter ^ a, 16)  # fully known after key0 recovered
        c = state8 + d = key4 + d  # key4 added to known-varying d
    This is an ADD target (recover byte-wise with carry chaining), the same
    machinery as recover_key_word."""
    a = first_round_a(key_word0)
    d = rotl32(counter ^ a, 16)
    return (key_word4 + d) & MASK32


def hamming_weight_vec(x):
    x = np.asarray(x, dtype=np.uint32) & 0xFF
    weight = np.zeros(x.shape, dtype=np.uint16)
    v = x.copy()
    for _ in range(8):
        weight += (v & 1).astype(np.uint16)
        v >>= 1
    return weight
