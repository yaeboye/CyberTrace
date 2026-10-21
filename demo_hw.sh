#!/bin/bash
# CyberTrace full HARDWARE demo -- every attack and defense on the real ESP32-S3.
# Offline (no internet). Run on the Raspberry Pi with the testbed attached:
#     bash demo_hw.sh
#
# Target ESP (crypto) is on the Pi UART /dev/ttyAMA0 + shunt power (USB OUT).
# Noise ESP (defense) is on /dev/ttyUSB0. ADS1115 on I2C bus 1 (0x48).
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
NOISE=/dev/ttyUSB0
TR=${TRACES:-800}

say(){ printf '\n============================================================\n  %s\n============================================================\n' "$1"; }

noise(){ python3 - "$1" <<'PY' 2>/dev/null
import sys,serial,time
try:
    s=serial.Serial("/dev/ttyUSB0",115200,timeout=1); time.sleep(0.2)
    s.write((sys.argv[1]+"\n").encode()); s.flush(); time.sleep(0.2); s.close()
except Exception: pass
PY
}

say "0. device check"
python3 - <<'PY'
import serial,time
s=serial.Serial("/dev/ttyAMA0",115200,timeout=2); time.sleep(0.3)
s.write(b"PING\n"); s.flush(); time.sleep(0.3)
print("target PING ->", s.read(20)); s.close()
PY

say "1. ChaCha20 power CPA  (recovers key0 = 0xDEADBEEF)"
noise STOP                                   # clean traces: noise off
python3 attacker/ct_attack.py cpa --hw --traces "$TR"

say "2. ChaCha20 masking defense  (TVLA: leaks OFF -> passes ON)"
python3 defender/ct_defend.py assess --hw --target chacha --traces "$TR" --no-plots

say "3. Kyber coefficient CPA  (recovers s_hat = 1234)"
python3 attacker/ct_attack.py kyber --hw --traces "$TR"

say "4. Timing attack"
python3 attacker/ct_attack.py timing --hw --trials 40

say "5. Replay attack  (nonce OFF accepts replay, ON blocks it)"
python3 defender/ct_defend.py toggle nonce off --hw >/dev/null
python3 attacker/ct_attack.py replay --hw
python3 defender/ct_defend.py toggle nonce on  --hw >/dev/null
python3 attacker/ct_attack.py replay --hw
python3 defender/ct_defend.py toggle nonce off --hw >/dev/null

say "6. Probing-detection monitor  (rule vs ML, FPR + latency)"
python3 defender/ct_defend.py monitor

say "7. Noise-injection defense  (CPA correlation degrades under active noise)"
noise START
echo "  [noise injector ON -- re-running ChaCha CPA under active noise]"
python3 attacker/ct_attack.py cpa --hw --traces "$TR"
noise STOP
echo "  [noise injector OFF again]"

say "DEMO COMPLETE -- all attacks and defenses exercised on real hardware"
