import numpy as np

from chacha20_model import hamming_weight_vec


def correlation_matrix(hypotheses, traces):
    """hypotheses: (n_traces, n_guesses) power model predictions
    traces:     (n_traces, n_samples) measured power traces
    returns:    (n_guesses, n_samples) Pearson correlation"""
    h_centered = hypotheses - hypotheses.mean(axis=0, keepdims=True)
    t_centered = traces - traces.mean(axis=0, keepdims=True)

    numerator = h_centered.T @ t_centered
    h_norm = np.sqrt((h_centered ** 2).sum(axis=0))
    t_norm = np.sqrt((t_centered ** 2).sum(axis=0))

    denom = np.outer(h_norm, t_norm)
    denom[denom == 0] = 1e-12
    return numerator / denom


def attack_byte(known_bytes, carry_in, traces):
    """known_bytes: (n_traces,) the counter byte at this position, varies per trace
    carry_in:    (n_traces,) carry coming in from the lower byte, per trace (0 or 1)
    traces:      (n_traces, n_samples)
    returns (best_guess, corr_matrix, confidence)"""
    guesses = np.arange(256, dtype=np.uint32)
    sums = (known_bytes[:, None].astype(np.uint32) + guesses[None, :] + carry_in[:, None]) & 0xFF
    hypotheses = hamming_weight_vec(sums)

    corr = correlation_matrix(hypotheses, traces)
    peak_per_guess = np.max(np.abs(corr), axis=1)
    best_guess = int(np.argmax(peak_per_guess))
    confidence = float(peak_per_guess[best_guess])
    return best_guess, corr, confidence


def recover_key_word(known_counters, traces_per_byte, verbose=True):
    """known_counters:  (n_traces,) uint32 counter value used for each trace
    traces_per_byte: list of 4 trace matrices (n_traces, n_samples), one per
                     targeted byte position, sliced from the time window
                     where that byte's addition happens
    returns recovered 32-bit key word"""
    n_traces = known_counters.shape[0]
    recovered_bytes = []
    carry = np.zeros(n_traces, dtype=np.uint32)

    for byte_index in range(4):
        known_bytes = (known_counters >> (8 * byte_index)) & 0xFF
        traces = traces_per_byte[byte_index]
        best_guess, corr, confidence = attack_byte(known_bytes, carry, traces)
        recovered_bytes.append(best_guess)

        totals = known_bytes.astype(np.uint32) + best_guess + carry
        carry = (totals >= 256).astype(np.uint32)

        if verbose:
            print(f"byte {byte_index}: recovered 0x{best_guess:02x} (peak corr {confidence:.3f})")

    key_word = 0
    for i, b in enumerate(recovered_bytes):
        key_word |= (b << (8 * i))
    return key_word
