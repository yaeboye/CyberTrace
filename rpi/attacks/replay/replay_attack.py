import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from virtual_device import VirtualESP32  # noqa: E402


def capture_command(device, counter, payload):
    """Simulates an attacker sniffing a valid command off the wire.
    Returns the captured (counter, payload) tuple plus whether the
    legitimate send was accepted."""
    accepted = device.submit_command(counter, payload)
    return (counter, payload), accepted


def replay(device, captured):
    """Resends a previously captured command byte-for-byte."""
    counter, payload = captured
    return device.submit_command(counter, payload)


if __name__ == "__main__":
    print("=== Replay Attack Demo ===\n")

    print("--- vulnerable device (no nonce checking) ---")
    vulnerable = VirtualESP32(key_word=0, seed=1)
    vulnerable.nonce_enabled = False

    captured, first_accept = capture_command(vulnerable, counter=1042, payload=b"OPEN_VALVE")
    print(f"legit command  counter=1042 payload={captured[1]!r:<14} -> accepted={first_accept}")

    replay_accept = replay(vulnerable, captured)
    print(f"replayed later counter=1042 payload={captured[1]!r:<14} -> accepted={replay_accept}")
    print(f"replayed again counter=1042 payload={captured[1]!r:<14} -> accepted={replay(vulnerable, captured)}")
    print(f"\nRESULT: replay succeeded = {replay_accept} (device has no memory of prior commands)\n")

    print("--- protected device (nonce + monotonic counter) ---")
    protected = VirtualESP32(key_word=0, seed=1)
    protected.nonce_enabled = True

    captured2, first_accept2 = capture_command(protected, counter=1042, payload=b"OPEN_VALVE")
    print(f"legit command  counter=1042 payload={captured2[1]!r:<14} -> accepted={first_accept2}")

    replay_accept2 = replay(protected, captured2)
    print(f"replayed later counter=1042 payload={captured2[1]!r:<14} -> accepted={replay_accept2}")

    new_counter_accept = protected.submit_command(1043, b"OPEN_VALVE")
    print(f"new command    counter=1043 payload={b'OPEN_VALVE'!r:<14} -> accepted={new_counter_accept}")
    print(f"\nRESULT: replay succeeded = {replay_accept2} (nonce defense rejects the repeated counter)")
    print(f"        fresh command with higher counter still works = {new_counter_accept}")
