"""Train the probing detector on the REAL captured-traffic dataset and persist
it for reuse and for review.

Keeps the one-class design: the Isolation Forest is fitted only on real NORMAL
windows from the training split (attacks stay unseen, as in deployment). The
decision threshold is calibrated from the same normal-training scores at the
mean - margin_sigmas * std operating point (~1% false positives). The fitted
scaler, forest, and threshold are written to models/probing_iforest.joblib,
with a sidecar models/probing_iforest.meta.json recording provenance.

Usage:
    python3 defender/ml_train.py          # train from data/ml_dataset/windows.npz
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import subprocess
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "rpi" / "defense" / "probing"))
from probing_detector import MLProbingDetector, FEATURE_NAMES  # noqa: E402

DS = REPO / "data" / "ml_dataset" / "windows.npz"
MODEL = REPO / "models" / "probing_iforest.joblib"
META = REPO / "models" / "probing_iforest.meta.json"


def _git_commit():
    try:
        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def train(dataset=DS, margin_sigmas=2.0):
    data = np.load(dataset, allow_pickle=True)
    X, label_name, split = data["X"], data["label_name"], data["split"]

    train_mask = (label_name == "normal") & (split == "train")
    n_train = int(train_mask.sum())
    if n_train < 20:
        raise SystemExit(f"only {n_train} real normal-train windows; capture more traffic first")

    det = MLProbingDetector(window_seconds=60.0, margin_sigmas=margin_sigmas)
    if not det.has_sklearn:
        raise SystemExit("scikit-learn not installed")
    det.train(list(X[train_mask]))
    # det.train sets score_threshold = mean - margin_sigmas * std of the real
    # normal-training scores. A distributional estimator is used rather than an
    # empirical quantile because the real normal set is small, which makes a raw
    # low-percentile cutoff land on a single bursty outlier. margin_sigmas is
    # tunable from the CLI if a tighter or looser operating point is wanted.
    det.save(MODEL)

    classes, counts = np.unique(label_name, return_counts=True)
    meta = {
        "trained_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "dataset": str(dataset.relative_to(REPO)),
        "feature_names": FEATURE_NAMES,
        "algorithm": "IsolationForest(n_estimators=200, contamination='auto', random_state=42) + StandardScaler",
        "training": "one-class: fitted on real NORMAL traffic, train split only",
        "n_train_normal_windows": n_train,
        "threshold_rule": "mean - margin_sigmas * std of real normal-train scores",
        "score_threshold": det.score_threshold,
        "margin_sigmas": margin_sigmas,
        "class_window_counts": {str(c): int(n) for c, n in zip(classes, counts)},
    }
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2))

    print(f"trained on {n_train} real normal windows")
    print(f"  threshold {det.score_threshold:.4f}  (mean - {margin_sigmas}*sigma of normal-train scores)")
    print(f"  -> {MODEL}")
    print(f"  -> {META}")
    return MODEL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(DS))
    ap.add_argument("--margin-sigmas", type=float, default=2.0)
    args = ap.parse_args()
    train(pathlib.Path(args.dataset), args.margin_sigmas)


if __name__ == "__main__":
    main()
