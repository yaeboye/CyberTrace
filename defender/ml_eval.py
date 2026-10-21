"""Reproducible evaluation of the Isolation-Forest probing detector.

Reports the numbers the project cites for the ML defence, computed over many
seeds rather than a single demo run so the figures are stable:

  * single-window ROC-AUC (normal vs aggressive, normal vs stealthy)
  * single-window false-positive rate at the calibrated 1%-FPR operating point
  * single-window true-positive rate for aggressive and stealthy attackers
  * streaming detection: fraction caught and median requests-to-detection when
    the window is checked after every request (the way the live monitor runs)
  * multi-window aggregate detection for the throttled attacker

Run:  python defender/ml_eval.py
All randomness is seeded, so the printed table is deterministic.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpi" / "defense" / "probing"))
from probing_detector import (  # noqa: E402
    MLProbingDetector, build_trained_ml_detector,
    simulate_normal_traffic, simulate_attacker_traffic, simulate_stealthy_attacker,
)

WIN = 60


def _fresh(trained):
    d = MLProbingDetector(window_seconds=WIN)
    d.model, d.scaler = trained.model, trained.scaler
    d.score_threshold, d.is_trained = trained.score_threshold, True
    return d


def _window_score(trained, simulate, seed, **kw):
    d = _fresh(trained)
    simulate(d, np.random.default_rng(seed), **kw)
    f = d._expanded_features()
    if f is None:
        return None
    return float(d.model.score_samples(d.scaler.transform([f]))[0])


def _collect(trained, simulate, seeds, varied=None, **kw):
    out = []
    for s in seeds:
        if varied is not None:
            kw = dict(kw)
            kw["n_events"] = int(np.random.default_rng(s * 13 + 1).integers(*varied))
        sc = _window_score(trained, simulate, s, **kw)
        if sc is not None:
            out.append(sc)
    return np.array(out)


def _auc(normal_scores, attack_scores):
    # anomaly = lower score; score the attack class with -score
    from sklearn.metrics import roc_auc_score
    y = np.r_[np.zeros(len(normal_scores)), np.ones(len(attack_scores))]
    s = np.r_[-normal_scores, -attack_scores]
    return float(roc_auc_score(y, s))


def _streaming_latency(trained, simulate, seed, max_events=250):
    d = _fresh(trained)
    rng = np.random.default_rng(seed)
    t = 0.0
    for i in range(max_events):
        t = simulate(d, rng, n_events=1, base_time=t)
        if d.check()["alert"]:
            return i + 1
    return None


def evaluate(n_seeds=200, verbose=True):
    ml = build_trained_ml_detector(window_seconds=WIN)
    if not ml.has_sklearn:
        if verbose:
            print("scikit-learn missing; cannot evaluate ML detector.")
        return None

    # single-window score populations (operational = varied window sizes)
    normal = _collect(ml, simulate_normal_traffic, range(20000, 20000 + n_seeds), varied=(12, 60))
    aggr = _collect(ml, simulate_attacker_traffic, range(22000, 22000 + n_seeds), n_events=200)
    stealthy = _collect(ml, simulate_stealthy_attacker, range(23000, 23000 + n_seeds), varied=(30, 120))

    thr = ml.score_threshold  # calibrated ~1% FPR (mean - 3.5 sigma of training scores)
    metrics = {
        "threshold": thr,
        "auc_aggressive": _auc(normal, aggr),
        "auc_stealthy": _auc(normal, stealthy),
        "fpr": float(np.mean(normal < thr)),
        "tpr_aggressive": float(np.mean(aggr < thr)),
        "tpr_stealthy": float(np.mean(stealthy < thr)),
    }

    # streaming (per-request) detection
    n_stream = max(60, n_seeds // 3)
    for name, sim in [("aggressive", simulate_attacker_traffic), ("stealthy", simulate_stealthy_attacker)]:
        lat = [_streaming_latency(ml, sim, s) for s in range(30000, 30000 + n_stream)]
        caught = [x for x in lat if x is not None]
        metrics[f"stream_catch_{name}"] = len(caught) / n_stream
        metrics[f"stream_median_{name}"] = int(np.median(caught)) if caught else None

    # multi-window aggregate for the throttled attacker (mean of 3 window scores)
    K = 3
    nb, sb = [], []
    for b in range(n_seeds):
        nseeds = [40000 + b * 17 + j for j in range(K)]
        nb.append(_collect(ml, simulate_normal_traffic, nseeds, varied=(12, 60)).mean())
        sseeds = [50000 + b * 17 + j for j in range(K)]
        sb.append(_collect(ml, simulate_stealthy_attacker, sseeds, varied=(30, 90)).mean())
    nb, sb = np.array(nb), np.array(sb)
    thr_agg = float(np.quantile(nb, 0.01))
    metrics["agg_windows"] = K
    metrics["agg_fpr"] = float(np.mean(nb < thr_agg))
    metrics["agg_tpr_stealthy"] = float(np.mean(sb < thr_agg))

    if verbose:
        print("=== Isolation-Forest probing detector: robust evaluation ===")
        print(f"seeds per class: {n_seeds}   operating point: score < {thr:.3f} (~1% FPR)\n")
        print(f"single-window ROC-AUC   aggressive {metrics['auc_aggressive']:.3f}   "
              f"stealthy {metrics['auc_stealthy']:.3f}")
        print(f"single-window FPR (normal)          {metrics['fpr']*100:5.1f} %")
        print(f"single-window TPR aggressive        {metrics['tpr_aggressive']*100:5.1f} %")
        print(f"single-window TPR stealthy          {metrics['tpr_stealthy']*100:5.1f} %")
        print(f"streaming  aggressive  caught {metrics['stream_catch_aggressive']*100:4.0f} %"
              f"  median {metrics['stream_median_aggressive']} requests")
        print(f"streaming  stealthy    caught {metrics['stream_catch_stealthy']*100:4.0f} %"
              f"  median {metrics['stream_median_stealthy']} requests")
        print(f"{K}-window aggregate  stealthy TPR {metrics['agg_tpr_stealthy']*100:4.0f} %"
              f"  at FPR {metrics['agg_fpr']*100:.1f} %")
    return metrics


def evaluate_dataset(npz_path, model_path, verbose=True):
    """Evaluate a persisted detector on the REAL captured-traffic test split.
    Reports ROC-AUC, FPR and per-attack-class TPR at the model's own threshold.
    """
    import numpy as np
    from sklearn.metrics import roc_auc_score
    sys.path.insert(0, str(pathlib.Path(REPO := pathlib.Path(__file__).resolve().parents[1]) / "rpi" / "defense" / "probing"))
    from probing_detector import load_ml_detector

    det = load_ml_detector(model_path)
    data = np.load(npz_path, allow_pickle=True)
    X, label_name, split = data["X"], data["label_name"], data["split"]
    test = split == "test"
    sc = det.model.score_samples(det.scaler.transform(X[test]))
    names = label_name[test]
    thr = det.score_threshold

    normal = sc[names == "normal"]
    metrics = {"threshold": float(thr), "fpr": float(np.mean(normal < thr)),
               "n_normal_test": int((names == "normal").sum())}
    if verbose:
        print("=== probing detector on REAL captured test traffic ===")
        print(f"operating point: score < {thr:.3f}")
        print(f"normal FPR                 {metrics['fpr']*100:5.1f} %  (n={metrics['n_normal_test']})")
    for cls in sorted(set(names) - {"normal"}):
        a = sc[names == cls]
        if len(a) == 0:
            continue
        y = np.r_[np.zeros(len(normal)), np.ones(len(a))]
        auc = float(roc_auc_score(y, np.r_[-normal, -a]))
        tpr = float(np.mean(a < thr))
        metrics[f"auc_{cls}"] = auc
        metrics[f"tpr_{cls}"] = tpr
        if verbose:
            print(f"{cls:11s} ROC-AUC {auc:.3f}   TPR {tpr*100:5.1f} %  (n={len(a)})")
    return metrics


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", help="evaluate a persisted model on this windows.npz "
                                      "(real test split) instead of synthetic traffic")
    ap.add_argument("--model", default=str(pathlib.Path(__file__).resolve().parents[1]
                                           / "models" / "probing_iforest.joblib"))
    a = ap.parse_args()
    if a.dataset:
        evaluate_dataset(a.dataset, a.model)
    else:
        evaluate()
