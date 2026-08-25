#!/usr/bin/env python3
"""
Live monitor for the CHARGE/SOLAR CURRENT byte on CAN ID 0x0000E000.

Confirmed by cross-referencing two candump logs held at known steady
currents:
    log @ 1.0 A -> raw 0x0A / 0x0B  -> 1.0 / 1.1
    log @ 2.0 A -> raw 0x14 / 0x13  -> 2.0 / 1.9
Scale is raw / 10, no offset.

Mirrors carrying the same value (used here as a live sanity check):
    0x4D4       byte 3   raw / 10          (identical raw values)
    0x18904010  byte 5   (raw - 48) / 10
    0x18FA28F4  byte 4   (raw - 16) / 10

Usage:
    python3 current_check.py            # default: can0
    python3 current_check.py vcan0      # or specify interface
"""

import sys
import time

try:
    import can
except ImportError:
    print("Missing dependency. Install with:")
    print("  pip install python-can --break-system-packages")
    sys.exit(1)

# ---- Primary (confirmed) ----------------------------------------------
CURRENT_ID = 0x0000E000
BYTE_INDEX = 7        # 0-based index into the 8-byte payload
SCALE = 10.0          # raw / 10 = amps
OFFSET = 0            # no offset needed

# ---- Mirrors: (byte_index, offset, divisor) ---------------------------
# Each decodes to the same amps value. If one disagrees with the primary,
# that's worth knowing.
MIRROR_IDS = {
    0x4D4:        (3, 0,  10.0),
    0x18904010:   (5, 48, 10.0),
    0x18FA28F4:   (4, 16, 10.0),
}


def decode(raw, offset, divisor):
    return (raw - offset) / divisor


def fmt_id(can_id):
    """Format ID compactly: 3 hex digits for standard, 8 for extended."""
    return f"0x{can_id:03X}" if can_id <= 0x7FF else f"0x{can_id:08X}"


def main():
    iface = sys.argv[1] if len(sys.argv) > 1 else "can0"

    print(f"Listening on {iface}")
    print(f"  Current: {fmt_id(CURRENT_ID)} byte[{BYTE_INDEX}] / {SCALE:g} = amps")
    print("  Mirrors: " + ", ".join(
        f"{fmt_id(mid)} byte[{i}]" for mid, (i, _, _) in MIRROR_IDS.items()
    ))
    print("Ctrl+C to stop.\n")

    try:
        bus = can.interface.Bus(channel=iface, bustype="socketcan")
    except Exception as e:
        print(f"Failed to open {iface}: {e}")
        print("Check that the interface is up, e.g.:")
        print(f"  sudo ip link set {iface} up type can bitrate 250000")
        sys.exit(1)

    last_print = 0.0
    current = None
    current_raw = None
    mirrors = {}

    while True:
        msg = bus.recv(timeout=1.0)
        if msg is None:
            continue

        if msg.arbitration_id == CURRENT_ID and len(msg.data) > BYTE_INDEX:
            current_raw = msg.data[BYTE_INDEX]
            current = decode(current_raw, OFFSET, SCALE)

        elif msg.arbitration_id in MIRROR_IDS:
            idx, off, div = MIRROR_IDS[msg.arbitration_id]
            if len(msg.data) > idx:
                mirrors[msg.arbitration_id] = decode(msg.data[idx], off, div)

        # Throttle printing so the terminal doesn't scroll too fast
        now = time.time()
        if now - last_print >= 0.2 and current is not None:
            last_print = now

            # Flag any mirror that disagrees with the primary reading
            parts = []
            for mid, mval in mirrors.items():
                flag = "" if abs(mval - current) < 0.05 else " !"
                parts.append(f"{fmt_id(mid)}={mval:.1f}{flag}")
            mirror_str = " | ".join(parts)

            print(f"\rCURRENT: {current:5.1f} A   raw=0x{current_raw:02X}   "
                  f"[{mirror_str}]      ",
                  end="", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")