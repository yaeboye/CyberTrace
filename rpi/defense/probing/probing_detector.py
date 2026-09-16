import math
from collections import Counter, deque

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

    def check(self):
        n = len(self.events)
        if n < self.min_samples:
            return {"alert": False, "reason": None, "n_samples": n}

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
            "n_samples": n,
            "entropy": entropy,
            "rate": rate,
            "timing_cv": timing_cv,
        }


def simulate_normal_traffic(detector, rng, n_events=40, base_time=0.0):
    t = base_time
    for _ in range(n_events):
        t += rng.exponential(1.5)  # irregular human-scale gaps
        size = int(rng.integers(4, 16))
        payload = bytes(rng.integers(0, 256, size=size, dtype=np.uint8))
        detector.ingest(t, payload)
    return t


def simulate_attacker_traffic(detector, rng, n_events=200, base_time=0.0, counter_start=0):
    t = base_time
    for i in range(n_events):
        t += 0.01 + rng.normal(0, 0.0005)  # tight, near-uniform interval
        payload = (counter_start + i).to_bytes(4, "big")  # structured, low-entropy
        detector.ingest(t, payload)
    return t


if __name__ == "__main__":
    print("=== Probing Detection Demo ===\n")
    rng = np.random.default_rng(3)

    print("--- normal usage pattern ---")
    detector_normal = ProbingDetector(window_seconds=60)
    end_time = simulate_normal_traffic(detector_normal, rng, n_events=40)
    result = detector_normal.check()
    print(f"events ingested: {result['n_samples']}")
    print(f"entropy={result.get('entropy', 0):.2f}  rate={result.get('rate', 0):.2f}/s  "
          f"timing_cv={result.get('timing_cv', 0):.3f}")
    print(f"ALERT: {result['alert']}\n")

    print("--- attacker collecting CPA traces ---")
    detector_attack = ProbingDetector(window_seconds=60)
    simulate_attacker_traffic(detector_attack, rng, n_events=200)
    result2 = detector_attack.check()
    print(f"events ingested: {result2['n_samples']}")
    print(f"entropy={result2.get('entropy', 0):.2f}  rate={result2.get('rate', 0):.2f}/s  "
          f"timing_cv={result2.get('timing_cv', 0):.3f}")
    print(f"ALERT: {result2['alert']}")
    if result2["alert"]:
        print(f"reason: {result2['reason']}")

    print("\n--- attacker detected mid-collection (progressive check) ---")
    detector_progressive = ProbingDetector(window_seconds=60, min_samples=10)
    t = 0.0
    detected_at = None
    for i in range(200):
        t += 0.01 + rng.normal(0, 0.0005)
        payload = i.to_bytes(4, "big")
        detector_progressive.ingest(t, payload)
        r = detector_progressive.check()
        if r["alert"] and detected_at is None:
            detected_at = i + 1
            print(f"probing detected after {detected_at} requests (reason: {r['reason']})")
            break
    if detected_at is None:
        print("not detected within 200 requests")
