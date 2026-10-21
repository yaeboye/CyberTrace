"""Turn captured real-traffic logs into the labelled feature dataset that the
probing detector is trained and evaluated on.

Reads every data/ml_dataset/raw/<class>_*.csv produced by traffic_logger.py,
slides the detector's window over each log, and emits one row of the nine
standardised traffic features per window, tagged with its class and a
deterministic train/test split. The result is written both as a human-readable
CSV (for reviewers) and an .npz (for the trainer/evaluator).

  data/ml_dataset/windows.csv   entropy,rate,...,accel,label,split,source
  data/ml_dataset/windows.npz   X, y (0=normal,1=attack), label_name, split,
                                feature_names, source

Window features are sampled every --stride events (once the window holds at
least min_samples) so successive rows are not fully overlapping.

Usage:
    python3 defender/ml_dataset.py            # build from all raw logs
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "rpi" / "defense" / "probing"))
from probing_detector import MLProbingDetector, FEATURE_NAMES  # noqa: E402

DS_DIR = REPO / "data" / "ml_dataset"
RAW_DIR = DS_DIR / "raw"

ATTACK_CLASSES = {"aggressive", "throttled"}


def _read_log(path):
    ts, payloads = [], []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            ts.append(float(row["timestamp_s"]))
            payloads.append(bytes.fromhex(row["payload_hex"]))
    return ts, payloads


def _windows_from_log(path, cls, window_seconds, min_samples, stride):
    """Replay one log through a detector and yield (feature_vector) per window."""
    det = MLProbingDetector(window_seconds=window_seconds, min_samples=min_samples)
    ts, payloads = _read_log(path)
    out = []
    for i, (t, p) in enumerate(zip(ts, payloads)):
        det.ingest(t, p)
        if len(det.events) >= min_samples and (i % stride == 0):
            f = det._expanded_features()
            if f is not None:
                out.append(f)
    return out


def build(window_seconds=60.0, min_samples=10, stride=3, test_frac=0.3):
    logs = sorted(RAW_DIR.glob("*.csv"))
    if not logs:
        raise SystemExit(f"no raw logs in {RAW_DIR} -- run traffic_logger.py first")

    rows, labels, names, splits, sources = [], [], [], [], []
    per_class_counts = {}
    for path in logs:
        cls = path.stem.split("_")[0]
        feats = _windows_from_log(path, cls, window_seconds, min_samples, stride)
        per_class_counts[cls] = per_class_counts.get(cls, 0) + len(feats)
        # deterministic split: last test_frac of each log's windows -> test
        n = len(feats)
        cut = int(n * (1.0 - test_frac))
        for j, fv in enumerate(feats):
            rows.append(fv)
            labels.append(1 if cls in ATTACK_CLASSES else 0)
            names.append(cls)
            splits.append("train" if j < cut else "test")
            sources.append(path.name)

    X = np.vstack(rows)
    y = np.array(labels, dtype=np.int64)
    label_name = np.array(names)
    split = np.array(splits)
    source = np.array(sources)

    DS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DS_DIR / "windows.npz", X=X, y=y, label_name=label_name,
                        split=split, source=source,
                        feature_names=np.array(FEATURE_NAMES))
    with open(DS_DIR / "windows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FEATURE_NAMES + ["label", "class", "split", "source"])
        for fv, lab, nm, sp, sr in zip(rows, labels, names, splits, sources):
            w.writerow([f"{v:.6f}" for v in fv] + [lab, nm, sp, sr])

    print(f"built {len(rows)} windows from {len(logs)} logs")
    for cls, c in sorted(per_class_counts.items()):
        print(f"  {cls:11s} {c} windows")
    print(f"  -> {DS_DIR/'windows.csv'}")
    print(f"  -> {DS_DIR/'windows.npz'}")
    return DS_DIR / "windows.npz"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-seconds", type=float, default=60.0)
    ap.add_argument("--min-samples", type=int, default=10)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--test-frac", type=float, default=0.3)
    args = ap.parse_args()
    build(args.window_seconds, args.min_samples, args.stride, args.test_frac)


if __name__ == "__main__":
    main()
