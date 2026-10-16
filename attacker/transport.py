"""Attacker-side transport: the ONLY channel the attacker has to the target.

Exposes the target's legitimate interface plus power measurement -- and nothing
else. There is deliberately no way to toggle or even query the device's
defenses from here: a real attacker cannot reach into the victim and flip its
countermeasures. The defender program owns that. The same API backs both the
software simulator and the real ESP32 (UART + ADS1115), so every attack in this
package is identical in sim and on hardware.
"""

from __future__ import annotations

import pathlib
import sys
import time

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rpi" / "common"))
sys.path.insert(0, str(_ROOT / "rpi" / "attacks" / "cpa"))


class SimTransport:
    """Drives a VirtualESP32 instance. The device-under-test (its hidden key
    and whatever defenses the defender has configured) is created by the
    scenario, not by the attacker; the attacker only calls the methods below."""

    def __init__(self, device):
        self._dev = device  # VirtualESP32 -- attacker does not read .key_word
        self.kind = "sim"

    def leakloop(self, counter):
        return self._dev.leakloop_trace(int(counter))

    def kyberleak(self, u):
        return self._dev.kyberleak_trace(int(u))

    def check(self, candidate):
        return self._dev.check_secret(bytes(candidate))

    def command(self, counter, payload):
        return self._dev.submit_command(int(counter), bytes(payload))

    def device_rotations(self):
        return list(getattr(self._dev, "rotations", []))


class HwTransport:
    """Drives the real ESP32 over UART (/dev/ttyAMA0) plus the ADS1115 ADC.
    Target must be on shunt power (USB unplugged) so its current is measured."""

    def __init__(self, port="/dev/ttyAMA0", baud=115200, gain=4, data_rate=860):
        import serial
        import board
        import busio
        from adafruit_ads1x15.ads1115 import ADS1115
        from adafruit_ads1x15.ads1x15 import Mode, Pin
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS1115(i2c, gain=gain)
        ads.mode = Mode.CONTINUOUS
        ads.data_rate = data_rate
        self._chan = AnalogIn(ads, Pin.A0, Pin.A1)
        self._uart = serial.Serial(port, baud, timeout=5)
        time.sleep(0.3)
        self.kind = "hw"

    def leakloop(self, counter):
        self._uart.reset_input_buffer()
        self._uart.write(b"LEAKLOOP %08x\n" % int(counter))
        self._uart.flush()
        buf = []
        while not self._uart.in_waiting:
            buf.append(self._chan.voltage)
        self._uart.readline()
        return np.asarray(buf, dtype=np.float64)

    def kyberleak(self, u):
        self._uart.reset_input_buffer()
        self._uart.write(b"KYBERLEAK %x\n" % (int(u) & 0xFFFFFFFF))
        self._uart.flush()
        buf = []
        while not self._uart.in_waiting:
            buf.append(self._chan.voltage)
        self._uart.readline()
        return np.asarray(buf, dtype=np.float64)

    def check(self, candidate):
        self._uart.reset_input_buffer()
        t0 = time.perf_counter()
        self._uart.write(b"CHECK " + bytes(candidate).hex().encode() + b"\n")
        self._uart.flush()
        resp = self._uart.readline().strip()
        elapsed = time.perf_counter() - t0
        return resp == b"OK", elapsed

    def command(self, counter, payload):
        self._uart.reset_input_buffer()
        self._uart.write(b"CMD %d %s\n" % (int(counter), bytes(payload).hex().encode()))
        self._uart.flush()
        return self._uart.readline().strip() == b"OK"


def open_transport(args):
    """Build a transport from CLI args. Hardware if --hw, else a simulated
    device-under-test with a hidden key (fixed to the firmware's 0xDEADBEEF so
    sim and hardware recover the same value) and optional masking."""
    if getattr(args, "hw", False):
        return HwTransport(port=args.port)
    from virtual_device import VirtualESP32
    dev = VirtualESP32(key_word=0xDEADBEEF, secret_bytes=b"K3Y!",
                       seed=getattr(args, "seed", None))
    dev.masking_enabled = getattr(args, "masked", False)
    dev.constant_time_enabled = getattr(args, "constant_time", False)
    dev.nonce_enabled = getattr(args, "nonce", False)
    dev.probing_detection_enabled = getattr(args, "probing", False)
    dev.key_refresh_enabled = getattr(args, "key_refresh", False)
    return SimTransport(dev)
