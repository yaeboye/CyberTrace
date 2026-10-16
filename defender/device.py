"""Defender-side transport: the device owner's full-control channel.

Unlike the attacker transport, the defender CAN configure the device's
countermeasures and rotate its key -- it owns the target. It also collects
power traces, so it can run its own leakage assessment (TVLA) on the device it
is protecting. Same API over the simulator and the real ESP32.
"""

from __future__ import annotations

import pathlib
import sys
import time

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rpi" / "common"))
sys.path.insert(0, str(_ROOT / "rpi" / "attacks" / "cpa"))


class SimDefenderTransport:
    def __init__(self, device):
        self._dev = device
        self.kind = "sim"

    def leakloop(self, counter):
        return self._dev.leakloop_trace(int(counter))

    def set_defense(self, layer, enabled):
        setattr(self._dev, f"{layer}_enabled", bool(enabled))

    def get_defenses(self):
        return {k: getattr(self._dev, f"{k}_enabled")
                for k in ("masking", "constant_time", "nonce")}

    def rotate_key(self, new_key_word):
        self._dev.set_key(int(new_key_word))


class HwDefenderTransport:
    _LAYER = {"masking": "MASKING", "constant_time": "CTIME", "nonce": "NONCE"}

    def __init__(self, port="/dev/ttyAMA0", baud=115200, gain=4, data_rate=860):
        import serial, board, busio
        from adafruit_ads1x15.ads1115 import ADS1115
        from adafruit_ads1x15.ads1x15 import Mode, Pin
        from adafruit_ads1x15.analog_in import AnalogIn
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS1115(i2c, gain=gain); ads.mode = Mode.CONTINUOUS; ads.data_rate = data_rate
        self._chan = AnalogIn(ads, Pin.A0, Pin.A1)
        self._uart = serial.Serial(port, baud, timeout=5); time.sleep(0.3)
        self.kind = "hw"

    def _cmd(self, c):
        self._uart.reset_input_buffer(); self._uart.write(c + b"\n"); self._uart.flush()
        return self._uart.readline().strip()

    def leakloop(self, counter):
        self._uart.reset_input_buffer()
        self._uart.write(b"LEAKLOOP %08x\n" % int(counter)); self._uart.flush()
        buf = []
        while not self._uart.in_waiting:
            buf.append(self._chan.voltage)
        self._uart.readline()
        return np.asarray(buf, dtype=np.float64)

    def set_defense(self, layer, enabled):
        self._cmd(b"DEFENSE %s %s" % (self._LAYER[layer].encode(), b"ON" if enabled else b"OFF"))

    def get_defenses(self):
        s = self._cmd(b"STATUS").decode()
        return {k: ("%s=1" % n) in s for k, n in
                (("masking", "masking"), ("constant_time", "ctime"), ("nonce", "nonce"))}

    def rotate_key(self, new_key_word):
        self._cmd(b"SET_KEY %08x" % (int(new_key_word) & 0xFFFFFFFF))


def open_defender_transport(args):
    if getattr(args, "hw", False):
        return HwDefenderTransport(port=args.port)
    from virtual_device import VirtualESP32
    dev = VirtualESP32(key_word=0xDEADBEEF, secret_bytes=b"K3Y!",
                       seed=getattr(args, "seed", None))
    return SimDefenderTransport(dev)
