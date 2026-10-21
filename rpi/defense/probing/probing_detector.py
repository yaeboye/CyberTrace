import math
from collections import Counter, deque
import zlib
import numpy as np

class ProbingDetector:
    """Monitors a stream of encryption/command requests and flags behavior
    consistent with an attacker collecting side-channel traces: structured
    (low-entropy) payloads, high request rate, and unnaturally uniform
    timing between requests. All three are checked independently -- any one
    crossing its threshold raises an alert."""

    def __init__(
        self,
        window_seconds=10.0,
        entropy_threshold=4.0,
        rate_threshold=20.0,
        timing_cv_threshold=0.15,
        min_samples=10,
    ):
        self.window_seconds = window_seconds
        self.entropy_threshold = entropy_threshold
        self.rate_threshold = rate_threshold
        self.timing_cv_threshold = timing_cv_threshold
        self.min_samples = min_samples
        self.events = deque()  # (timestamp, payload_bytes)

    def ingest(self, timestamp, payload_bytes):
        self.events.append((timestamp, bytes(payload_bytes)))
        cutoff = timestamp - self.window_seconds
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()

    def _shannon_entropy(self, payloads):
        counts = Counter()
        total = 0
        for p in payloads:
            for b in p:
                counts[b] += 1
                total += 1
        if total == 0:
            return 0.0
        entropy = 0.0
        for c in counts.values():
            p = c / total
            entropy -= p * math.log2(p)
        return entropy

    def extract_features(self):
        """Extracts the base features for the rule-based logic."""
        n = len(self.events)
        if n < self.min_samples:
            return None

        timestamps = [t for t, _ in self.events]
        payloads = [p for _, p in self.events]

        entropy = self._shannon_entropy(payloads)

        span = max(timestamps[-1] - timestamps[0], 1e-9)
        rate = n / span

        gaps = [timestamps[i] - timestamps[i - 1] for i in range(1, n)]
        mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
        if mean_gap > 0:
            variance = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
            timing_cv = math.sqrt(variance) / mean_gap
        else:
            timing_cv = 0.0

        return {
            "n_samples": n,
            "entropy": entropy,
            "rate": rate,
            "timing_cv": timing_cv,
            "span": span,
            "timestamps": timestamps,
            "payloads": payloads,
            "gaps": gaps
        }

    def check(self):
        features = self.extract_features()
        if not features:
            return {"alert": False, "reason": None, "n_samples": len(self.events)}

        entropy = features["entropy"]
        rate = features["rate"]
        timing_cv = features["timing_cv"]

        reasons = []
        if entropy < self.entropy_threshold:
            reasons.append(f"low payload entropy ({entropy:.2f} < {self.entropy_threshold})")
        if rate > self.rate_threshold:
            reasons.append(f"high request rate ({rate:.1f}/s > {self.rate_threshold}/s)")
        if timing_cv < self.timing_cv_threshold:
            reasons.append(f"uniform timing (cv={timing_cv:.3f} < {self.timing_cv_threshold})")

        return {
            "alert": len(reasons) > 0,
            "reason": "; ".join(reasons) if reasons else None,
            "n_samples": features["n_samples"],
            "entropy": entropy,
            "rate": rate,
            "timing_cv": timing_cv,
        }

FEATURE_NAMES = [
    "entropy", "rate", "timing_cv", "duplicate_ratio",
    "sequentialness", "compression_ratio", "autocorr", "burst_ratio", "accel",
]


class MLProbingDetector(ProbingDetector):
    """ML-based detector: an Isolation Forest over nine traffic features,
    trained only on normal traffic (one-class anomaly detection — no labelled
    attack data required, which matches a real deployment where attacks are
    unseen in advance).

    Two things make this robust where a raw Isolation Forest is not:
      - features are standardised (StandardScaler) before training and
        scoring, so rate (~0-100/s) and autocorrelation (~+-0.6) contribute
        on equal footing instead of rate dominating every split;
      - decisions use the continuous anomaly score against a margin derived
        from the training distribution, rather than the default contamination
        threshold that sits flush against the normal cluster and flips on
        RNG noise.

    The win over the rule-based detector is a *stealthy* attacker that stays
    under the rate/entropy/timing thresholds individually yet is still caught
    because the joint feature signature (sequential counters + compressible
    payloads + regular timing) never occurs in normal traffic."""

    def __init__(self, window_seconds=10.0, min_samples=10, margin_sigmas=3.5):
        super().__init__(window_seconds, min_samples=min_samples)
        self.margin_sigmas = margin_sigmas
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
            self.model = IsolationForest(
                n_estimators=200, contamination="auto", random_state=42
            )
            self.scaler = StandardScaler()
            self.has_sklearn = True
        except ImportError:
            self.model = None
            self.scaler = None
            self.has_sklearn = False
            print("Warning: scikit-learn not installed. MLProbingDetector falls back to rule-based.")
        self.is_trained = False
        self.score_threshold = None

    def _expanded_features(self):
        base = self.extract_features()
        if not base:
            return None

        payloads = base["payloads"]
        gaps = base["gaps"]
        n = base["n_samples"]

        unique_payloads = len(set(payloads))
        duplicate_ratio = 1.0 - (unique_payloads / n)

        seq_count = 0
        try:
            ints = [int.from_bytes(p, "big") for p in payloads if len(p) >= 4]
            if len(ints) > 1:
                seq_count = sum(1 for i in range(1, len(ints)) if ints[i] == ints[i - 1] + 1)
        except Exception:
            pass
        sequentialness = seq_count / max(1, len(payloads) - 1)

        raw_data = b"".join(payloads)
        if len(raw_data) > 0:
            compression_ratio = len(zlib.compress(raw_data)) / len(raw_data)
        else:
            compression_ratio = 1.0

        gaps_arr = np.asarray(gaps, dtype=np.float64)
        if gaps_arr.size > 1:
            mean_gap = gaps_arr.mean()
            var_gap = gaps_arr.var()
            if var_gap > 0:
                autocorr = float(
                    np.sum((gaps_arr[:-1] - mean_gap) * (gaps_arr[1:] - mean_gap))
                    / ((gaps_arr.size - 1) * var_gap)
                )
            else:
                autocorr = 0.0
            burst_ratio = float(gaps_arr.max() / max(mean_gap, 1e-9))
            accel = float(np.mean(np.diff(gaps_arr)))
        else:
            autocorr, burst_ratio, accel = 0.0, 1.0, 0.0

        return np.array([
            base["entropy"], base["rate"], base["timing_cv"], duplicate_ratio,
            sequentialness, compression_ratio, autocorr, burst_ratio, accel,
        ], dtype=np.float64)

    def train(self, normal_features_list):
        if not self.has_sklearn or not normal_features_list:
            return
        X = np.vstack(normal_features_list)
        Xs = self.scaler.fit_transform(X)
        self.model.fit(Xs)

        normal_scores = self.model.score_samples(Xs)
        self.score_threshold = float(
            normal_scores.mean() - self.margin_sigmas * normal_scores.std()
        )
        self.is_trained = True

    def save(self, path):
        """Persist the fitted scaler, forest, and calibrated threshold so the
        detector can be reloaded without retraining (used to ship a model
        trained on real captured traffic)."""
        import joblib
        import pathlib
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "score_threshold": self.score_threshold,
            "margin_sigmas": self.margin_sigmas,
            "window_seconds": self.window_seconds,
            "min_samples": self.min_samples,
            "feature_names": FEATURE_NAMES,
        }, path)
        return path

    def anomaly_score(self):
        """Signed anomaly score for the current window. Lower = more anomalous.
        None if not enough samples or not trained."""
        f = self._expanded_features()
        if f is None or not self.is_trained or not self.has_sklearn:
            return None
        return float(self.model.score_samples(self.scaler.transform([f]))[0])

    def check(self):
        f = self._expanded_features()
        if f is None or not self.is_trained or not self.has_sklearn:
            return super().check()

        score = float(self.model.score_samples(self.scaler.transform([f]))[0])
        is_anomaly = score < self.score_threshold

        return {
            "alert": is_anomaly,
            "reason": (
                f"Isolation Forest anomaly (score {score:.3f} < threshold "
                f"{self.score_threshold:.3f})" if is_anomaly else None
            ),
            "n_samples": len(self.events),
            "score": score,
            "threshold": self.score_threshold,
            "entropy": float(f[0]),
            "rate": float(f[1]),
            "timing_cv": float(f[2]),
        }


def build_trained_ml_detector(window_seconds=60, n_windows=200, events_per_window=None,
                              seed=7, min_samples=10, margin_sigmas=3.5):
    """Trains an MLProbingDetector on freshly simulated normal traffic and
    returns it ready to use. Training windows use VARIED event counts (not a
    fixed 20) so the model generalises across window sizes -- a detector trained
    only on 20-event windows scores larger windows out-of-distribution and
    behaves erratically. Centralises training so demo/tests/API agree."""
    detector = MLProbingDetector(window_seconds=window_seconds,
                                 min_samples=min_samples, margin_sigmas=margin_sigmas)
    if not detector.has_sklearn:
        return detector

    rng = np.random.default_rng(seed)
    features = []
    t = 0.0
    for _ in range(n_windows):
        n_ev = events_per_window if events_per_window else int(rng.integers(12, 60))
        tmp = MLProbingDetector(window_seconds=window_seconds, min_samples=min_samples)
        t = simulate_normal_traffic(tmp, rng, n_events=n_ev, base_time=t)
        f = tmp._expanded_features()
        if f is not None:
            features.append(f)
    detector.train(features)
    return detector


def load_ml_detector(path, window_seconds=None, min_samples=None):
    """Load a detector previously saved with MLProbingDetector.save(). Returns a
    ready-to-use detector whose model was fitted on real captured traffic."""
    import joblib
    d = joblib.load(path)
    det = MLProbingDetector(
        window_seconds=window_seconds if window_seconds is not None else d.get("window_seconds", 10.0),
        min_samples=min_samples if min_samples is not None else d.get("min_samples", 10),
        margin_sigmas=d.get("margin_sigmas", 3.5))
    if not det.has_sklearn:
        raise RuntimeError("scikit-learn not available; cannot load ML detector")
    det.model = d["model"]
    det.scaler = d["scaler"]
    det.score_threshold = d["score_threshold"]
    det.is_trained = True
    return det


def simulate_normal_traffic(detector, rng, n_events=40, base_time=0.0):
    t = base_time
    for _ in range(n_events):
        t += rng.exponential(1.5)
        size = int(rng.integers(4, 16))
        payload = bytes(rng.integers(0, 256, size=size, dtype=np.uint8))
        detector.ingest(t, payload)
    return t


def simulate_attacker_traffic(detector, rng, n_events=200, base_time=0.0, counter_start=0):
    t = base_time
    for i in range(n_events):
        t += 0.01 + rng.normal(0, 0.0005)
        payload = (counter_start + i).to_bytes(4, "big")
        detector.ingest(t, payload)
    return t


def simulate_stealthy_attacker(detector, rng, n_events=180, base_time=0.0,
                               rate_hz=5.0, jitter=0.45):
    """A patient attacker that deliberately stays under every rule threshold:
      - high-entropy random plaintexts (as real CPA uses varied inputs), so
        the entropy rule (< 4.0 bits) never fires;
      - a throttled ~5/s rate, well under the 20/s rate rule;
      - human-like timing jitter, keeping timing-CV above the 0.15 rule.
    None of the three hard rules trip. But 5/s is ~7x the learned normal rate
    (~0.7/s), so the ML model, which scores deviation from the whole normal
    distribution rather than fixed cutoffs, still flags it. That gap between
    'normal behaviour' and 'the loosest threshold that avoids false alarms on
    bursts' is exactly where a throttled attacker hides, and what the ML layer
    closes."""
    t = base_time
    mean_gap = 1.0 / rate_hz
    for _ in range(n_events):
        t += max(0.001, mean_gap * (1.0 + rng.normal(0, jitter)))
        size = int(rng.integers(4, 16))
        payload = bytes(rng.integers(0, 256, size=size, dtype=np.uint8))
        detector.ingest(t, payload)
    return t


if __name__ == "__main__":
    print("=== Probing Detection Demo ===\n")
    rng = np.random.default_rng(3)

    print("--- Rule-based: normal usage pattern ---")
    detector_normal = ProbingDetector(window_seconds=60)
    simulate_normal_traffic(detector_normal, rng, n_events=40)
    result = detector_normal.check()
    print(f"events ingested: {result['n_samples']}")
    print(f"entropy={result.get('entropy', 0):.2f}  rate={result.get('rate', 0):.2f}/s  "
          f"timing_cv={result.get('timing_cv', 0):.3f}")
    print(f"ALERT: {result['alert']}\n")

    print("--- Rule-based: attacker collecting CPA traces ---")
    detector_attack = ProbingDetector(window_seconds=60)
    simulate_attacker_traffic(detector_attack, rng, n_events=200)
    result2 = detector_attack.check()
    print(f"events ingested: {result2['n_samples']}")
    print(f"entropy={result2.get('entropy', 0):.2f}  rate={result2.get('rate', 0):.2f}/s  "
          f"timing_cv={result2.get('timing_cv', 0):.3f}")
    print(f"ALERT: {result2['alert']}")
    if result2["alert"]:
        print(f"reason: {result2['reason']}")

    print("\n--- ML-based (Isolation Forest, standardised features) ---")
    ml_detector = build_trained_ml_detector(window_seconds=60)
    if ml_detector.has_sklearn:
        def ml_view(trained, simulate, **kw):
            d = MLProbingDetector(window_seconds=60)
            d.model, d.scaler = trained.model, trained.scaler
            d.score_threshold, d.is_trained = trained.score_threshold, True
            simulate(d, np.random.default_rng(kw.pop("seed", 11)), **kw)
            return d.check()

        norm = ml_view(ml_detector, simulate_normal_traffic, n_events=40)
        print(f"  normal traffic   -> ALERT={norm['alert']}  score={norm['score']:.3f} "
              f"(threshold {norm['threshold']:.3f})")

        aggressive = ml_view(ml_detector, simulate_attacker_traffic, n_events=200)
        print(f"  aggressive attack-> ALERT={aggressive['alert']}  score={aggressive['score']:.3f}")

        stealthy = ml_view(ml_detector, simulate_stealthy_attacker, n_events=60)
        print(f"  stealthy attack  -> ALERT={stealthy['alert']}  score={stealthy['score']:.3f}")

        print("\n--- novelty: stealthy attacker vs rule-based thresholds ---")
        rule = ProbingDetector(window_seconds=60)
        simulate_stealthy_attacker(rule, np.random.default_rng(11), n_events=60)
        rule_res = rule.check()
        print(f"  rule-based on stealthy attack -> ALERT={rule_res['alert']} "
              f"(rate={rule_res.get('rate', 0):.1f}/s, entropy={rule_res.get('entropy', 0):.2f}, "
              f"timing_cv={rule_res.get('timing_cv', 0):.2f})")
        print(f"  ML       on stealthy attack -> ALERT={stealthy['alert']}")
        if not rule_res["alert"] and stealthy["alert"]:
            print("  => ML catches the throttled attacker the rule thresholds miss.")
    else:
        print("Skipping ML demo because scikit-learn is missing.")
