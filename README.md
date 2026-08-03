# CyberTrace

Multi-vector side-channel attack and defense framework for embedded CPS devices.

## Overview

Demonstrates three attack classes against an ESP32-S3 running ChaCha20 and CRYSTALS-Kyber:
- **Correlation Power Analysis (CPA)** — recover keys from power measurements
- **Timing Attack** — recover secrets from response time differences  
- **Replay Attack** — bypass authentication without breaking crypto

Includes a unified defense framework with masking, constant-time implementation, nonce-based replay prevention, and an active probing detection system.

## Hardware

- ESP32-S3 DevKit ×2
- ADS1115 16-bit ADC
- 10Ω shunt resistor
- Raspberry Pi 4/5
- Breadboard + jumper wires

## Structure

```
esp32/          ESP32-S3 firmware (ChaCha20 + Kyber variants)
rpi/            Raspberry Pi backend
  collector/    ADS1115 trace collection
  attacks/      CPA, timing, replay engines
  defense/      Masking, probing detection, key refresh
  api/          FastAPI server
frontend/       React dashboard
data/           Power traces and keys (gitignored)
docs/           Wiring diagrams and notes
```

## Setup

Coming soon.
