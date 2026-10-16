# Hardware results — real ESP32-S3 side-channel runs

Captured on the physical testbed (Raspberry Pi 5 driving an ESP32-S3 crypto
target over GPIO UART `/dev/ttyAMA0`, power measured across a 10 Ω shunt by an
ADS1115 differential channel A0–A1, target USB unplugged so all target current
crosses the shunt). These are the measured results behind the figures and
numbers in `report/CyberTrace_Project_Report.docx`.

## Summary of measured outcomes

| Vector | Result |
|---|---|
| ChaCha20 power CPA | key word recovered = `0xDEADBEEF`; peak corr ≈ 0.31–0.35; NTD ≈ 150–400 (trace-count dependent) |
| ChaCha20 masking (TVLA, N=800) | OFF \|t\|=4.5 LEAKS → ON \|t\|=2.5 PASS; corr 0.315→0.147; NTD 233→none; **effective** |
| Kyber coefficient CPA | secret coefficient recovered = `1234`; peak corr ≈ 0.20–0.23; margin ≈ 0.04 |
| Kyber masking (TVLA) | OFF \|t\|=6.8 → ON \|t\|=6.5, **still leaks**, coefficient still recovered — masking **ineffective on hardware** (negative result; works only in the software model) |
| Timing attack | **not recovered** over the serial link — secret-dependent delay (~0.2 ms) below the UART round-trip latency (~8 ms) and its jitter |
| Replay, no nonce | replay accepted (device subverted) |
| Replay, nonce enforced | replay blocked; fresh command accepted |

## Files

- `cpa_report_hw.json` — ChaCha20 CPA analysis (per-byte corr, NTD curve, recovered key)
- `assess_chacha.txt` — ChaCha20 TVLA assessment, N=400
- `chacha_tvla800.txt` — ChaCha20 TVLA assessment, N=800 (used for the report figure)
- `kyber_hw.txt` — Kyber coefficient CPA, 1500 traces
- `figs_run.txt` — combined run: ChaCha TVLA (N=300), Kyber TVLA, Kyber CPA figure
- `timing_hw.txt` — timing attack over the serial link (failed, as expected)
- `replay_hw.txt` — replay attack, nonce off then on
- `hw_raw_chacha.npz` — raw ChaCha CPA traces: `counters` (800,), `traces` (800, 369)
- `hw_raw_kyber.npz` — raw Kyber traces: `u` (1000,), `traces` (1000, 126)

Report figures generated from these runs: `data/reports/cpa_report.png`
(Fig 5.1), `data/reports/tvla.png` (Fig 5.2), `data/reports/kyber_cpa.png`
(Fig 5.3).

## Reproduction scripts

- `kyber_cpa_hw_plot.py` — collect KYBERLEAK traces and plot the coefficient CPA
- `save_raw_hw.py` — archive the raw ChaCha and Kyber traces (`.npz` above)

Both run on the Pi with the target attached, inside `~/ct-venv`. The primary
attacker/defender CLIs reproduce every result with `--hw`, e.g.
`python attacker/ct_attack.py cpa --hw --traces 600`,
`python defender/ct_defend.py assess --hw --target chacha --traces 800`.
