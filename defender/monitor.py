"""Probing-detection analytics for the defender console.

Reuses the project's rule-based and ML (Isolation Forest) detectors and reports
the numbers a defender cares about: detection latency (requests until the attack
is flagged), false-positive rate on normal traffic, and the rule-vs-ML
comparison on a stealthy (throttled) attacker that hides under the rule
thresholds.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpi" / "defense" / "probing"))
from probing_detector import (  # noqa: E402
    ProbingDetector, build_trained_ml_detector,
    simulate_normal_traffic, simulate_attacker_traffic, simulate_stealthy_attacker,
)


def _fresh_ml(trained, window=60):
    from probing_detector import MLProbingDetector
    d = MLProbingDetector(window_seconds=window)
    d.model, d.scaler = trained.model, trained.scaler
    d.score_threshold, d.is_trained = trained.score_threshold, True
    return d


def detection_latency(make_detector, simulate, seed=11, max_events=250):
    """Feed attack traffic one request at a time; return how many requests
    until the detector first alerts (None if never)."""
    det = make_detector()
    rng = np.random.default_rng(seed)
    t = 0.0
    for i in range(max_events):
        t = simulate(det, rng, n_events=1, base_time=t)
        if det.check()["alert"]:
            return i + 1
    return None


def false_positive_rate(make_detector, trials=30):
    """Fraction of normal-traffic windows that wrongly alert."""
    fp = 0
    for s in range(trials):
        det = make_detector()
        simulate_normal_traffic(det, np.random.default_rng(100 + s), n_events=40)
        if det.check()["alert"]:
            fp += 1
    return fp / trials


def analytics(window=60):
    ml = build_trained_ml_detector(window_seconds=window)
    rule = lambda: ProbingDetector(window_seconds=window, min_samples=10)
    ml_d = (lambda: _fresh_ml(ml, window)) if ml.has_sklearn else None

    res = {
        "rule": {
            "fpr": false_positive_rate(rule),
            "latency_aggressive": detection_latency(rule, simulate_attacker_traffic),
            "latency_stealthy": detection_latency(rule, simulate_stealthy_attacker),
        }
    }
    if ml_d:
        res["ml"] = {
            "fpr": false_positive_rate(ml_d),
            "latency_aggressive": detection_latency(ml_d, simulate_attacker_traffic),
            "latency_stealthy": detection_latency(ml_d, simulate_stealthy_attacker),
        }
    res["has_ml"] = bool(ml_d)
    return res
