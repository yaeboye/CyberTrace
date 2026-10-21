#!/bin/bash
# Standalone, offline runner for the probing-detection ML pipeline on the
# Raspberry Pi (ESP32-S3 target attached on /dev/ttyAMA0). No network needed.
#
# It captures real request traffic, builds the labelled feature dataset, trains
# the Isolation Forest on the real normal traffic, and evaluates it on the real
# test split -- end to end, with one command:
#
#     bash run_ml_pipeline.sh                # full capture (recommended)
#     bash run_ml_pipeline.sh --quick        # fast, smaller capture
#     bash run_ml_pipeline.sh --check        # only verify deps + device, no run
#     SESSIONS=3 EVENTS_NORMAL=300 bash run_ml_pipeline.sh    # override sizes
#
# Outputs (under the repo):
#     data/ml_dataset/raw/*.csv      raw per-request logs
#     data/ml_dataset/windows.csv    labelled feature dataset (for review)
#     data/ml_dataset/windows.npz    same, as arrays
#     data/ml_dataset/eval_real.txt  metrics on the real test split
#     models/probing_iforest.joblib  trained model (+ .meta.json provenance)

set -euo pipefail

# --- locate repo root (this script's directory) and make tools findable ------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
export PATH="$HOME/.local/bin:$PATH"
PORT="${PORT:-/dev/ttyAMA0}"

# --- sizes (override via environment) ----------------------------------------
MODE="${1:-}"
if [ "$MODE" = "--quick" ]; then
    SESSIONS="${SESSIONS:-2}"; EVENTS_NORMAL="${EVENTS_NORMAL:-120}"
    EVENTS_AGGR="${EVENTS_AGGR:-300}"; EVENTS_THROT="${EVENTS_THROT:-200}"
else
    SESSIONS="${SESSIONS:-3}"; EVENTS_NORMAL="${EVENTS_NORMAL:-300}"
    EVENTS_AGGR="${EVENTS_AGGR:-300}"; EVENTS_THROT="${EVENTS_THROT:-250}"
fi

say(){ echo ">>> $*"; }

# --- dependency + device check -----------------------------------------------
check() {
    say "checking Python dependencies"
    python3 - <<'PY'
import importlib, sys
need = ["numpy", "serial", "sklearn", "joblib"]
missing = [m for m in need if importlib.util.find_spec(m) is None]
if missing:
    print("MISSING:", ", ".join(missing))
    print("install with: pip install --break-system-packages "
          "numpy pyserial scikit-learn joblib adafruit-circuitpython-ads1x15 adafruit-blinka")
    sys.exit(1)
print("python deps OK")
PY
    say "checking target on $PORT"
    python3 - "$PORT" <<'PY'
import sys, time, serial
port = sys.argv[1]
try:
    s = serial.Serial(port, 115200, timeout=2); time.sleep(0.3)
    s.reset_input_buffer(); s.write(b"PING\n"); s.flush(); time.sleep(0.4)
    r = s.read(20); s.close()
    print("device replied to PING:", r.strip() or b"(nothing)")
    sys.exit(0 if b"PONG" in r else 2)
except Exception as e:
    print("cannot open/talk to device:", e); sys.exit(2)
PY
}

check
if [ "$MODE" = "--check" ]; then say "check only -- done"; exit 0; fi

# --- capture real traffic -----------------------------------------------------
say "baseline: masking off"
python3 defender/ct_defend.py toggle masking off --hw --port "$PORT" >/dev/null 2>&1 || true

rm -rf data/ml_dataset/raw data/ml_dataset/windows.* models
say "capturing $SESSIONS session(s) per class on $PORT"
for s in $(seq 0 $((SESSIONS-1))); do
    python3 rpi/collector/traffic_logger.py normal     --events "$EVENTS_NORMAL" --port "$PORT" --seed "$s"
    python3 rpi/collector/traffic_logger.py aggressive --events "$EVENTS_AGGR"  --port "$PORT" --seed "$((10+s))"
    python3 rpi/collector/traffic_logger.py throttled  --events "$EVENTS_THROT" --port "$PORT" --seed "$((20+s))"
done

# --- build, train, evaluate ---------------------------------------------------
say "building dataset"
python3 defender/ml_dataset.py
say "training model on real normal traffic"
python3 defender/ml_train.py
say "evaluating on real test split"
python3 defender/ml_eval.py --dataset data/ml_dataset/windows.npz | tee data/ml_dataset/eval_real.txt

say "done. artifacts:"
echo "    data/ml_dataset/windows.csv   (dataset for review)"
echo "    data/ml_dataset/eval_real.txt (metrics)"
echo "    models/probing_iforest.joblib (trained model + .meta.json)"
