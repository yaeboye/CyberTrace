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

class MLProbingDetector(ProbingDetector):
    """Upgraded ML-based detector using Isolation Forest trained on normal traffic.
    Extracts expanded features: duplicate ratio, counter-sequentialness, 
    compression ratio, inter-arrival autocorrelation, burst ratio, and rate acceleration."""
    
    def __init__(self, window_seconds=10.0, min_samples=10):
        super().__init__(window_seconds, min_samples=min_samples)
        try:
            from sklearn.ensemble import IsolationForest
            self.model = IsolationForest(contamination=0.01, random_state=42)
            self.has_sklearn = True
        except ImportError:
            self.has_sklearn = False
            print("Warning: scikit-learn is not installed. MLProbingDetector will fall back to rule-based.")
        self.is_trained = False
        
    def _expanded_features(self):
        base = self.extract_features()
        if not base:
            return None
            
        payloads = base["payloads"]
        gaps = base["gaps"]
        n = base["n_samples"]
        
        # 1. Duplicate Payload Ratio
        unique_payloads = len(set(payloads))
        duplicate_ratio = 1.0 - (unique_payloads / n)
        
        # 2. Counter-Sequentialness
        seq_count = 0
        try:
            ints = [int.from_bytes(p, "big") for p in payloads if len(p) >= 4]
            if len(ints) > 1:
                seq_count = sum(1 for i in range(1, len(ints)) if ints[i] == ints[i-1] + 1)
        except Exception:
            pass
        sequentialness = seq_count / max(1, len(payloads) - 1)
        
        # 3. Compression ratio
        raw_data = b"".join(payloads)
        if len(raw_data) > 0:
            compressed = zlib.compress(raw_data)
            compression_ratio = len(compressed) / len(raw_data)
        else:
            compression_ratio = 1.0
            
        # 4. Inter-arrival autocorrelation (lag 1)
        if len(gaps) > 1:
            mean_gap = np.mean(gaps)
            var_gap = np.var(gaps)
            if var_gap > 0:
                autocorr = np.sum((gaps[:-1] - mean_gap) * (gaps[1:] - mean_gap)) / ((len(gaps) - 1) * var_gap)
            else:
                autocorr = 0.0
        else:
            autocorr = 0.0
            
        # 5. Burst Ratio
        burst_ratio = max(gaps) / max(np.mean(gaps), 1e-9) if gaps else 1.0
        
        # 6. Rate Acceleration
        accel = np.mean(np.diff(gaps)) if len(gaps) > 1 else 0.0
        
        features = [
            base["entropy"],
            base["rate"],
            base["timing_cv"],
            duplicate_ratio,
            sequentialness,
            compression_ratio,
            autocorr,
            burst_ratio,
            accel
        ]
        return np.array(features)

    def train(self, normal_features_list):
        if not self.has_sklearn:
            return
        if not normal_features_list:
            return
        X = np.vstack(normal_features_list)
        self.model.fit(X)
        self.is_trained = True
        
    def check(self):
        f = self._expanded_features()
        if f is None or not self.is_trained or not self.has_sklearn:
            return super().check()
            
        # Predict: 1 for normal, -1 for anomaly
        prediction = self.model.predict([f])[0]
        is_anomaly = (prediction == -1)
        
        return {
            "alert": is_anomaly,
            "reason": "Isolation Forest detected anomaly in expanded features" if is_anomaly else None,
            "n_samples": len(self.events),
            "entropy": f[0],
            "rate": f[1],
            "timing_cv": f[2]
        }


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

    print("\n--- ML-based (Isolation Forest) ---")
    ml_detector = MLProbingDetector(window_seconds=60)
    if ml_detector.has_sklearn:
        normal_training_features = []
        t = 0.0
        for _ in range(50):
            temp_detector = MLProbingDetector(window_seconds=60)
            t = simulate_normal_traffic(temp_detector, rng, n_events=20, base_time=t)
            f = temp_detector._expanded_features()
            if f is not None:
                normal_training_features.append(f)
                
        ml_detector.train(normal_training_features)
        print(f"Trained Isolation Forest on {len(normal_training_features)} normal traffic windows.")
        
        ml_test_normal = MLProbingDetector(window_seconds=60)
        ml_test_normal.model = ml_detector.model
        ml_test_normal.is_trained = ml_detector.is_trained
        simulate_normal_traffic(ml_test_normal, rng, n_events=40)
        ml_res_norm = ml_test_normal.check()
        print(f"ML normal traffic check -> ALERT: {ml_res_norm['alert']}")
        
        ml_test_attack = MLProbingDetector(window_seconds=60)
        ml_test_attack.model = ml_detector.model
        ml_test_attack.is_trained = ml_detector.is_trained
        simulate_attacker_traffic(ml_test_attack, rng, n_events=200)
        ml_res_atk = ml_test_attack.check()
        print(f"ML attacker traffic check -> ALERT: {ml_res_atk['alert']}")
        if ml_res_atk["alert"]:
             print(f"reason: {ml_res_atk['reason']}")

        print("\n--- Progressive Check (Rule-based vs ML) ---")
        detector_progressive = ProbingDetector(window_seconds=60, min_samples=10)
        ml_progressive = MLProbingDetector(window_seconds=60, min_samples=10)
        ml_progressive.model = ml_detector.model
        ml_progressive.is_trained = ml_detector.is_trained
        
        t = 0.0
        rule_detected_at = None
        ml_detected_at = None
        
        for i in range(200):
            t += 0.01 + rng.normal(0, 0.0005)
            payload = i.to_bytes(4, "big")
            
            detector_progressive.ingest(t, payload)
            ml_progressive.ingest(t, payload)
            
            if rule_detected_at is None:
                if detector_progressive.check()["alert"]:
                    rule_detected_at = i + 1
                    
            if ml_detected_at is None:
                if ml_progressive.check()["alert"]:
                    ml_detected_at = i + 1
                    
            if rule_detected_at is not None and ml_detected_at is not None:
                break
                
        print(f"Rule-based detected after {rule_detected_at} requests")
        print(f"ML-based detected after {ml_detected_at} requests")
    else:
        print("Skipping ML demo because scikit-learn is missing.")
