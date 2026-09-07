# Serial Hardware Test

This test verifies the Raspberry Pi-to-target ESP32 wiring before adding the
ChaCha20 capture target or the ADS1115.

## Firmware pins

- ESP32 GPIO18: UART receive from Raspberry Pi physical pin 8 (TXD).
- ESP32 GPIO17: UART transmit to Raspberry Pi physical pin 10 (RXD).
- ESP32 GPIO4: trigger output to Raspberry Pi physical pin 13 (GPIO27).
- ESP32 GND: Raspberry Pi physical pin 6 (GND).

No Raspberry Pi power pin is connected to the ESP32. Power the ESP32 through
its USB connector only for this serial test.

## Raspberry Pi setup

1. In `sudo raspi-config`, open Interface Options > Serial Port.
2. Disable the login shell over serial and enable the serial hardware.
3. Reboot the Pi and verify that `/dev/serial0` exists.
4. Install pyserial: `python3 -m pip install pyserial`.
5. Run the command below from the repository root:

```powershell
python rpi/collector/serial_smoke_test.py --port /dev/serial0
```

Expected response: `PONG` followed by `TRIGGERED`.

The GPIO4 trigger can be observed with a multimeter or later by the ADS1115
capture workflow. It is not an analogue power measurement.
