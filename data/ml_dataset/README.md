# Probing-detection dataset (real captured traffic)

This dataset trains and evaluates the Isolation-Forest probing detector
(`rpi/defense/probing/probing_detector.py`) on **real request traffic captured
from the live ESP32-S3 testbed**, rather than on traffic synthesised at
runtime. It exists so the model's training data is inspectable and reproducible
for review.

## What is captured

The detector watches the *stream of requests* to the device (not power traces).
`rpi/collector/traffic_logger.py` issues genuine commands to the target over the
hardware UART and logs, for every request, the real send timestamp and the
request payload. Three behaviour classes from the threat model are recorded:

| class      | behaviour                                                        |
|------------|-----------------------------------------------------------------|
| normal     | varied payloads at a human pace, with idle gaps and short bursts |
| aggressive | a trace-collection flood: sequential counters, full link speed   |
| throttled  | a patient attacker: random payloads at ~5/s with jitter          |

The timing in these logs is real — it carries serial latency, device-compute
stalls and OS scheduling jitter, i.e. what a deployed monitor would see.

## Files

```
raw/<class>_<timestamp>.csv   one row per request: timestamp_s, payload_hex
windows.csv                   one row per 60 s window: 9 features + label/class/split/source
windows.npz                   same, as arrays (X, y, label_name, split, source, feature_names)
```

`y` is `0` for normal and `1` for either attack class; `label_name` keeps the
specific class. `split` is a deterministic per-log train/test split (last 30 %
of each log's windows is test).

## Pipeline

```
# 1. capture real traffic on the Pi (device attached), several sessions per class
python3 rpi/collector/traffic_logger.py normal     --events 300 --seed 0
python3 rpi/collector/traffic_logger.py aggressive  --events 300 --seed 10
python3 rpi/collector/traffic_logger.py throttled   --events 300 --seed 20

# 2. build the labelled feature dataset
python3 defender/ml_dataset.py

# 3. train the detector on real NORMAL traffic only (one-class) and persist it
python3 defender/ml_train.py
#    -> models/probing_iforest.joblib  + models/probing_iforest.meta.json

# 4. evaluate the persisted model on the real test split
python3 defender/ml_eval.py --dataset data/ml_dataset/windows.npz
```

## Model

- `IsolationForest(n_estimators=200, contamination="auto", random_state=42)`
  over a `StandardScaler`, fitted **only on real normal windows** from the
  training split (attacks stay unseen, as in deployment).
- Decision threshold: the empirical 1 % quantile of the real normal-training
  scores (~1 % false-positive operating point); robust to score skew.
- The fitted scaler, forest and threshold are saved to
  `models/probing_iforest.joblib`; provenance (capture counts, split, git
  commit, train date, threshold) is in `models/probing_iforest.meta.json`.
- `load_ml_detector()` reloads it for live use without retraining.
