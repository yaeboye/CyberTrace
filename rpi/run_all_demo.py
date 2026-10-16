"""CyberTrace full pipeline demo — runs all three attacks and all five
defenses end-to-end using the VirtualESP32 simulator. This is the single
script that demonstrates the entire project's functionality without
requiring any physical hardware.

Run: python run_all_demo.py
"""

from __future__ import annotations

import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "common"))
sys.path.insert(0, str(ROOT / "attacks" / "cpa"))
sys.path.insert(0, str(ROOT / "defense" / "probing"))

from virtual_device import VirtualESP32, BYTE_LEAK_SAMPLES
from cpa_engine import recover_key_word, attack_byte
from probing_detector import (
    ProbingDetector, MLProbingDetector, build_trained_ml_detector,
    simulate_normal_traffic, simulate_attacker_traffic, simulate_stealthy_attacker,
)


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def collect_traces(device, n_traces, seed=None):
    rng = np.random.default_rng(seed)
    counters = rng.integers(0, 2**32, size=n_traces, dtype=np.uint64).astype(np.uint32)
    traces = np.stack([device.encrypt_with_trace(int(c)) for c in counters])
    return counters, traces


def run_cpa(counters, traces, window=20):
    traces_per_byte = [traces[:, s - window:s + window] for s in BYTE_LEAK_SAMPLES]
    return recover_key_word(counters, traces_per_byte, verbose=True)


# ══════════════════════════════════════════════════════════════
#  ATTACK 1: CPA
# ══════════════════════════════════════════════════════════════

def demo_cpa():
    separator("ATTACK 1: Correlation Power Analysis (CPA)")

    secret_key = 0xDEADBEEF
    n = 3000
    print(f"target key = 0x{secret_key:08x},  {n} traces\n")

    device = VirtualESP32(key_word=secret_key, seed=42)
    counters, traces = collect_traces(device, n, seed=100)
    recovered = run_cpa(counters, traces)

    match = recovered == secret_key
    print(f"\nRECOVERED: 0x{recovered:08x}  MATCH: {match}")
    return match


# ══════════════════════════════════════════════════════════════
#  ATTACK 2: Timing
# ══════════════════════════════════════════════════════════════

def demo_timing():
    separator("ATTACK 2: Timing Attack")

    secret = b"K3Y!"
    print(f"hidden secret = {secret!r}\n")

    device = VirtualESP32(key_word=0, secret_bytes=secret, seed=1)
    device.constant_time_enabled = False

    recovered = bytearray()
    for pos in range(len(secret)):
        best_guess, best_time = 0, -1.0
        for guess in range(256):
            candidate = bytes(recovered) + bytes([guess]) + bytes(len(secret) - pos - 1)
            _, elapsed = device.check_secret(candidate)
            if elapsed > best_time:
                best_time = elapsed
                best_guess = guess
        recovered.append(best_guess)
        ch = chr(best_guess) if 32 <= best_guess < 127 else f"0x{best_guess:02x}"
        print(f"  byte {pos}: {ch!r}  ({best_time*1000:.3f} ms)")

    correct = sum(1 for a, b in zip(recovered, secret) if a == b)
    print(f"\nRECOVERED: {bytes(recovered)!r}  correct: {correct}/{len(secret)}")
    print("(last byte indistinguishable — known artifact of early-exit comparison)")
    return correct >= len(secret) - 1


# ══════════════════════════════════════════════════════════════
#  ATTACK 3: Replay
# ══════════════════════════════════════════════════════════════

def demo_replay():
    separator("ATTACK 3: Replay Attack")

    device = VirtualESP32(key_word=0, seed=1)
    device.nonce_enabled = False

    ok1 = device.submit_command(1042, b"OPEN_VALVE")
    ok2 = device.submit_command(1042, b"OPEN_VALVE")

    print(f"  legit command  -> accepted={ok1}")
    print(f"  replayed       -> accepted={ok2}")
    print(f"\n  replay succeeded = {ok2}")
    return ok2


# ══════════════════════════════════════════════════════════════
#  DEFENSE 1: Masking
# ══════════════════════════════════════════════════════════════

def demo_masking():
    separator("DEFENSE 1: Masking (vs CPA)")

    secret_key = 0xC0FFEE11
    n = 4000

    device_u = VirtualESP32(key_word=secret_key, seed=2)
    device_u.masking_enabled = False
    cu, tu = collect_traces(device_u, n, seed=10)
    rec_u = run_cpa(cu, tu)
    kb_u = (cu >> 0) & 0xFF
    carry = np.zeros(len(cu), dtype=np.uint32)
    _, _, conf_u = attack_byte(kb_u, carry, tu[:, BYTE_LEAK_SAMPLES[0]-20:BYTE_LEAK_SAMPLES[0]+20])

    print(f"\nunprotected: recovered 0x{rec_u:08x}  match={rec_u == secret_key}  peak_corr={conf_u:.3f}\n")

    device_m = VirtualESP32(key_word=secret_key, seed=2)
    device_m.masking_enabled = True
    cm, tm = collect_traces(device_m, n, seed=10)
    rec_m = run_cpa(cm, tm)
    kb_m = (cm >> 0) & 0xFF
    _, _, conf_m = attack_byte(kb_m, carry[:len(cm)], tm[:, BYTE_LEAK_SAMPLES[0]-20:BYTE_LEAK_SAMPLES[0]+20])

    print(f"\nmasked: recovered 0x{rec_m:08x}  match={rec_m == secret_key}  peak_corr={conf_m:.3f}")
    print(f"\ncorrelation drop: {conf_u:.3f} -> {conf_m:.3f} ({conf_u/max(conf_m,1e-9):.1f}x)")
    return rec_m != secret_key


# ══════════════════════════════════════════════════════════════
#  DEFENSE 2: Constant-Time
# ══════════════════════════════════════════════════════════════

def demo_constant_time():
    separator("DEFENSE 2: Constant-Time Comparison (vs Timing)")

    secret = b"K3Y!"
    device = VirtualESP32(key_word=0, secret_bytes=secret, seed=1)
    device.constant_time_enabled = True

    recovered = bytearray()
    for pos in range(len(secret)):
        best_guess, best_time = 0, -1.0
        for guess in range(256):
            candidate = bytes(recovered) + bytes([guess]) + bytes(len(secret) - pos - 1)
            _, elapsed = device.check_secret(candidate)
            if elapsed > best_time:
                best_time = elapsed
                best_guess = guess
        recovered.append(best_guess)

    correct = sum(1 for a, b in zip(recovered, secret) if a == b)
    print(f"  recovered with constant-time: {bytes(recovered)!r}  correct: {correct}/{len(secret)}")
    defended = correct <= 1
    print(f"  defense effective: {defended}")
    return defended


# ══════════════════════════════════════════════════════════════
#  DEFENSE 3: Nonce Validation
# ══════════════════════════════════════════════════════════════

def demo_nonce():
    separator("DEFENSE 3: Nonce + Monotonic Counter (vs Replay)")

    device = VirtualESP32(key_word=0, seed=1)
    device.nonce_enabled = True

    ok1 = device.submit_command(1042, b"OPEN_VALVE")
    ok2 = device.submit_command(1042, b"OPEN_VALVE")
    ok3 = device.submit_command(1043, b"OPEN_VALVE")

    print(f"  legit command  counter=1042 -> accepted={ok1}")
    print(f"  replay         counter=1042 -> accepted={ok2}")
    print(f"  fresh command  counter=1043 -> accepted={ok3}")
    print(f"\n  replay blocked = {not ok2},  fresh accepted = {ok3}")
    return not ok2 and ok3


# ══════════════════════════════════════════════════════════════
#  DEFENSE 4: Probing Detection
# ══════════════════════════════════════════════════════════════

def demo_probing():
    separator("DEFENSE 4: Probing Detection System (NOVEL)")

    rng = np.random.default_rng(3)

    print("--- rule-based ---")
    det_n = ProbingDetector(window_seconds=60)
    simulate_normal_traffic(det_n, rng, n_events=40)
    r_n = det_n.check()
    print(f"  normal traffic: ALERT={r_n['alert']}")

    det_a = ProbingDetector(window_seconds=60)
    simulate_attacker_traffic(det_a, rng, n_events=200)
    r_a = det_a.check()
    print(f"  attacker traffic: ALERT={r_a['alert']}")
    if r_a["alert"]:
        print(f"    reason: {r_a['reason']}")

    print("\n--- ML-based (Isolation Forest) ---")
    ml_det = build_trained_ml_detector(window_seconds=60)
    ml_ok = True
    if ml_det.has_sklearn:
        def ml_view(simulate, **kw):
            d = MLProbingDetector(window_seconds=60)
            d.model, d.scaler = ml_det.model, ml_det.scaler
            d.score_threshold, d.is_trained = ml_det.score_threshold, True
            simulate(d, np.random.default_rng(kw.pop("seed", 11)), **kw)
            return d.check()

        def ml_detect_within(simulate, max_req, seed=11):
            """Progressive detection: feed one request at a time (how an attack
            actually ramps) and return the request count at first alert, else
            None. This is the realistic measure -- a throttled attacker is
            flagged as the window fills, not from a single full-window snapshot."""
            d = MLProbingDetector(window_seconds=60, min_samples=10)
            d.model, d.scaler = ml_det.model, ml_det.scaler
            d.score_threshold, d.is_trained = ml_det.score_threshold, True
            rng = np.random.default_rng(seed)
            t = 0.0
            for i in range(max_req):
                t = simulate(d, rng, n_events=1, base_time=t)
                if d.check()["alert"]:
                    return i + 1
            return None

        ml_n = ml_view(simulate_normal_traffic, n_events=40)
        agg_at = ml_detect_within(simulate_attacker_traffic, 200)
        stl_at = ml_detect_within(simulate_stealthy_attacker, 200)
        print(f"  normal traffic:    ALERT={ml_n['alert']}  score={ml_n['score']:.3f}")
        print(f"  aggressive attack: detected after {agg_at} requests")
        print(f"  stealthy attack:   detected after {stl_at} requests")

        rule_s = ProbingDetector(window_seconds=60)
        simulate_stealthy_attacker(rule_s, np.random.default_rng(11), n_events=180)
        rule_s_res = rule_s.check()
        print(f"\n  stealthy attack evades rule-based: {not rule_s_res['alert']} "
              f"(rate={rule_s_res.get('rate', 0):.1f}/s entropy={rule_s_res.get('entropy', 0):.2f} "
              f"cv={rule_s_res.get('timing_cv', 0):.2f})")
        print(f"  ML catches it progressively:       within {stl_at} requests")
        ml_ok = ((not ml_n["alert"]) and agg_at is not None and stl_at is not None
                 and not rule_s_res["alert"])
    else:
        print("  scikit-learn not installed, skipping ML demo")

    return not r_n["alert"] and r_a["alert"] and ml_ok


# ══════════════════════════════════════════════════════════════
#  DEFENSE 5: Key Refresh
# ══════════════════════════════════════════════════════════════

def demo_key_refresh():
    separator("DEFENSE 5: Key Refresh (vs CPA)")

    secret_key = 0xAABBCCDD
    n = 4000

    from key_refresh import KeyRefreshManager, attack_with_rotation, run_cpa as kr_cpa

    print("--- no rotation ---")
    dev_s = VirtualESP32(key_word=secret_key, seed=5)
    mgr_s = KeyRefreshManager(dev_s, rotate_every_n=None)
    cs, ts = attack_with_rotation(dev_s, mgr_s, n, seed=20)
    rec_s = kr_cpa(cs, ts)
    print(f"  recovered: 0x{rec_s:08x}  match={rec_s == secret_key}")

    print("\n--- rotation every 800 encryptions ---")
    dev_r = VirtualESP32(key_word=secret_key, seed=5)
    mgr_r = KeyRefreshManager(dev_r, rotate_every_n=800, rng_seed=99)
    cr, tr = attack_with_rotation(dev_r, mgr_r, n, seed=20)
    rec_r = kr_cpa(cr, tr)
    print(f"  rotations: {len(mgr_r.history)}")
    print(f"  recovered: 0x{rec_r:08x}  match_original={rec_r == secret_key}  match_final={rec_r == dev_r.key_word}")

    return rec_s == secret_key and rec_r != secret_key


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "defense" / "keyfresh"))

    print("=" * 60)
    print("  CyberTrace -- Full Pipeline Demonstration")
    print("  Multi-Vector Side-Channel Attack & Defense")
    print("=" * 60)

    results = {}

    results["CPA Attack"] = demo_cpa()
    results["Timing Attack"] = demo_timing()
    results["Replay Attack"] = demo_replay()
    results["Masking Defense"] = demo_masking()
    results["Constant-Time Defense"] = demo_constant_time()
    results["Nonce Defense"] = demo_nonce()
    results["Probing Detection"] = demo_probing()
    results["Key Refresh Defense"] = demo_key_refresh()

    separator("SUMMARY")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}]  {name}")

    print(f"\n  overall: {'ALL PASSED' if all_pass else 'SOME FAILED'}")
