#!/usr/bin/env python3
"""
Solar charge session logger.

Listens on the CAN bus, decodes charge current / pack voltage / SOC / cell
temps, and continuously writes two files:

    SolarLog_<DATE>_<TIME>.txt   human-readable live report (overwritten)
    SolarLog_<DATE>_<TIME>.csv   raw sample log (appended)

Check the report at any time while it's running:
    cat SolarLog_*.txt
    watch -n 2 cat SolarLog_*.txt     # auto-refreshing view

Usage:
    python3 solar_logger.py                  # default: can0
    python3 solar_logger.py can0 --dir ~/solar_logs
"""

import argparse
import os
import sys
import time
from collections import deque
from datetime import datetime, timedelta

try:
    import can
except ImportError:
    print("Missing dependency. Install with:")
    print("  pip install python-can --break-system-packages")
    sys.exit(1)


# ----------------------------------------------------------------------
# CAN decode map
# ----------------------------------------------------------------------
# Charge/solar current: confirmed against two logs held at known steady
# values (1.0 A -> raw 0x0A, 2.0 A -> raw 0x14). Scale raw/10, no offset.
ID_CURRENT = 0x0000E000
IDX_CURRENT = 7

ID_VOLTAGE = 0x02018100     # (data[2] << 8 | data[3]) / 10  -> volts
ID_SOC = 0x02028100         # data[3] -> percent
ID_TEMP_31 = 0x18F812F3     # data[0]-40 = cell3, data[3]-40 = cell1
ID_TEMP_2 = 0x18F814F3      # data[3] = cell2

# Mirrors of the current value, used only as a sanity check.
# (byte_index, offset, divisor)
CURRENT_MIRRORS = {
    0x4D4:      (3, 0,  10.0),
    0x18904010: (5, 48, 10.0),
    0x18FA28F4: (4, 16, 10.0),
}

REPORT_INTERVAL = 2.0       # seconds between report file rewrites
SAMPLE_INTERVAL = 1.0       # seconds between CSV samples
ROLLING_WINDOW = 300        # samples kept for "recent" averages (~5 min)


def fmt_id(can_id):
    return f"0x{can_id:03X}" if can_id <= 0x7FF else f"0x{can_id:08X}"


def fmt_duration(seconds):
    """Format seconds as e.g. '2h 14m 06s'."""
    if seconds is None:
        return "--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


class SolarSession:
    def __init__(self, outdir):
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs(outdir, exist_ok=True)
        self.report_path = os.path.join(outdir, f"SolarLog_{stamp}.txt")
        self.csv_path = os.path.join(outdir, f"SolarLog_{stamp}.csv")

        self.start_wall = now
        self.start_mono = time.monotonic()

        # Live values
        self.current = None
        self.voltage = None
        self.soc = None
        self.temp1 = None
        self.temp2 = None
        self.temp3 = None
        self.mirrors = {}

        # First-seen values
        self.initial_voltage = None
        self.initial_soc = None
        self.initial_temp_max = None

        # Aggregates
        self.current_sum = 0.0
        self.current_n = 0
        self.current_max = None
        self.current_min = None

        self.voltage_max = None
        self.voltage_min = None

        self.power_sum = 0.0
        self.power_n = 0
        self.power_max = None

        self.amp_hours = 0.0
        self.watt_hours = 0.0

        self.temp_max_seen = None

        # SOC step tracking: list of (soc_value, elapsed_seconds_at_first_seen)
        self.soc_steps = []

        # Rolling window of (elapsed, current, voltage) for recent averages
        self.recent = deque(maxlen=ROLLING_WINDOW)

        self.last_integrate = None
        self.samples = 0

        self._init_csv()

    # ------------------------------------------------------------------
    def _init_csv(self):
        with open(self.csv_path, "w") as f:
            f.write("timestamp,elapsed_s,current_a,voltage_v,power_w,"
                    "soc_pct,cell1_c,cell2_c,cell3_c,amp_hours,watt_hours\n")

    def elapsed(self):
        return time.monotonic() - self.start_mono

    # ------------------------------------------------------------------
    def handle_frame(self, msg):
        aid = msg.arbitration_id
        data = msg.data

        if aid == ID_CURRENT and len(data) > IDX_CURRENT:
            self.current = data[IDX_CURRENT] / 10.0

        elif aid == ID_VOLTAGE and len(data) > 3:
            self.voltage = ((data[2] << 8) | data[3]) / 10.0
            if self.initial_voltage is None:
                self.initial_voltage = self.voltage

        elif aid == ID_SOC and len(data) > 3:
            soc = data[3]
            if self.initial_soc is None:
                self.initial_soc = soc
            # Record the moment each new SOC value first appears
            if self.soc != soc:
                self.soc_steps.append((soc, self.elapsed()))
            self.soc = soc

        elif aid == ID_TEMP_31 and len(data) > 3:
            self.temp3 = data[0] - 40
            self.temp1 = data[3] - 40

        elif aid == ID_TEMP_2 and len(data) > 3:
            self.temp2 = data[3]

        elif aid in CURRENT_MIRRORS:
            idx, off, div = CURRENT_MIRRORS[aid]
            if len(data) > idx:
                self.mirrors[aid] = (data[idx] - off) / div

    # ------------------------------------------------------------------
    def sample(self):
        """Take a periodic sample: integrate energy, update aggregates, log CSV."""
        now = time.monotonic()
        el = self.elapsed()

        if self.current is None:
            return  # nothing decoded yet

        i = self.current
        v = self.voltage
        p = (i * v) if v is not None else None

        # --- integrate Ah / Wh over the interval since last sample ---
        if self.last_integrate is not None:
            dt_h = (now - self.last_integrate) / 3600.0
            self.amp_hours += i * dt_h
            if p is not None:
                self.watt_hours += p * dt_h
        self.last_integrate = now

        # --- current stats ---
        self.current_sum += i
        self.current_n += 1
        self.current_max = i if self.current_max is None else max(self.current_max, i)
        self.current_min = i if self.current_min is None else min(self.current_min, i)

        # --- voltage stats ---
        if v is not None:
            self.voltage_max = v if self.voltage_max is None else max(self.voltage_max, v)
            self.voltage_min = v if self.voltage_min is None else min(self.voltage_min, v)

        # --- power stats ---
        if p is not None:
            self.power_sum += p
            self.power_n += 1
            self.power_max = p if self.power_max is None else max(self.power_max, p)

        # --- temp stats ---
        temps = [t for t in (self.temp1, self.temp2, self.temp3) if t is not None]
        if temps:
            tmax = max(temps)
            if self.initial_temp_max is None:
                self.initial_temp_max = tmax
            self.temp_max_seen = tmax if self.temp_max_seen is None else max(self.temp_max_seen, tmax)

        self.recent.append((el, i, v))
        self.samples += 1

        with open(self.csv_path, "a") as f:
            f.write(
                f"{datetime.now().isoformat(timespec='seconds')},"
                f"{el:.1f},{i:.1f},"
                f"{'' if v is None else f'{v:.1f}'},"
                f"{'' if p is None else f'{p:.1f}'},"
                f"{'' if self.soc is None else self.soc},"
                f"{'' if self.temp1 is None else self.temp1},"
                f"{'' if self.temp2 is None else self.temp2},"
                f"{'' if self.temp3 is None else self.temp3},"
                f"{self.amp_hours:.4f},{self.watt_hours:.3f}\n"
            )

    # ------------------------------------------------------------------
    def soc_metrics(self):
        """Return (pct_gained, avg_sec_per_pct, last_sec_per_pct, eta_seconds)."""
        if self.soc is None or self.initial_soc is None:
            return None, None, None, None

        gained = self.soc - self.initial_soc

        # Only count upward transitions for per-percent timing
        rises = []
        for idx in range(1, len(self.soc_steps)):
            prev_soc, prev_t = self.soc_steps[idx - 1]
            cur_soc, cur_t = self.soc_steps[idx]
            if cur_soc > prev_soc:
                # spread the elapsed time over however many points it climbed
                steps = cur_soc - prev_soc
                rises.append((cur_t - prev_t) / steps)

        avg_per_pct = sum(rises) / len(rises) if rises else None
        last_per_pct = rises[-1] if rises else None

        # ETA: prefer the average of the last few rises, fall back to overall avg
        basis = None
        if len(rises) >= 3:
            basis = sum(rises[-3:]) / 3
        elif avg_per_pct is not None:
            basis = avg_per_pct

        eta = None
        if basis is not None and self.soc < 100:
            eta = basis * (100 - self.soc)

        return gained, avg_per_pct, last_per_pct, eta

    def recent_avg_current(self):
        vals = [i for _, i, _ in self.recent]
        return sum(vals) / len(vals) if vals else None

    # ------------------------------------------------------------------
    def write_report(self):
        el = self.elapsed()
        gained, avg_pct, last_pct, eta = self.soc_metrics()

        avg_current = self.current_sum / self.current_n if self.current_n else None
        avg_power = self.power_sum / self.power_n if self.power_n else None
        rec_current = self.recent_avg_current()

        def val(x, unit="", fmt="{:.1f}"):
            return f"{fmt.format(x)}{unit}" if x is not None else "--"

        lines = []
        A = lines.append

        A("=" * 58)
        A("           SOLAR CHARGE SESSION - LIVE REPORT")
        A("=" * 58)
        A(f"Session started : {self.start_wall.strftime('%Y-%m-%d %H:%M:%S')}")
        A(f"Last updated    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        A(f"Runtime         : {fmt_duration(el)}")
        A(f"Samples logged  : {self.samples}")
        A("")

        A("-- CURRENT " + "-" * 47)
        A(f"  Now             : {val(self.current, ' A')}")
        A(f"  Average         : {val(avg_current, ' A', '{:.2f}')}")
        A(f"  Recent avg (5m) : {val(rec_current, ' A', '{:.2f}')}")
        A(f"  Max             : {val(self.current_max, ' A')}")
        A(f"  Min             : {val(self.current_min, ' A')}")
        A("")

        A("-- VOLTAGE " + "-" * 47)
        A(f"  Initial         : {val(self.initial_voltage, ' V')}")
        A(f"  Now             : {val(self.voltage, ' V')}")
        if self.voltage is not None and self.initial_voltage is not None:
            A(f"  Change          : {self.voltage - self.initial_voltage:+.1f} V")
        A(f"  Max             : {val(self.voltage_max, ' V')}")
        A(f"  Min             : {val(self.voltage_min, ' V')}")
        A("")

        A("-- STATE OF CHARGE " + "-" * 39)
        A(f"  Initial         : {val(self.initial_soc, ' %', '{:.0f}')}")
        A(f"  Now             : {val(self.soc, ' %', '{:.0f}')}")
        A(f"  Gained          : {val(gained, ' %', '{:+.0f}')}")
        A(f"  Avg time per 1% : {fmt_duration(avg_pct)}")
        A(f"  Last 1% took    : {fmt_duration(last_pct)}")
        if eta is not None:
            done_at = datetime.now() + timedelta(seconds=eta)
            A(f"  Est. to 100%    : {fmt_duration(eta)}  (~{done_at.strftime('%H:%M')})")
        else:
            A("  Est. to 100%    : -- (need more SOC changes)")
        A("")

        A("-- ENERGY DELIVERED " + "-" * 38)
        A(f"  Amp-hours       : {val(self.amp_hours, ' Ah', '{:.3f}')}")
        A(f"  Watt-hours      : {val(self.watt_hours, ' Wh', '{:.2f}')}")
        A(f"  Power now       : {val((self.current * self.voltage) if (self.current is not None and self.voltage is not None) else None, ' W')}")
        A(f"  Avg power       : {val(avg_power, ' W')}")
        A(f"  Peak power      : {val(self.power_max, ' W')}")
        A("")

        A("-- TEMPERATURES " + "-" * 42)
        A(f"  Cell 1 / 2 / 3  : {val(self.temp1, '', '{:.0f}')} / "
          f"{val(self.temp2, '', '{:.0f}')} / {val(self.temp3, '', '{:.0f}')} C")
        A(f"  Initial max     : {val(self.initial_temp_max, ' C', '{:.0f}')}")
        A(f"  Peak max        : {val(self.temp_max_seen, ' C', '{:.0f}')}")
        A("")

        if self.mirrors and self.current is not None:
            A("-- CURRENT MIRROR CHECK " + "-" * 34)
            for mid, mval in self.mirrors.items():
                flag = "ok" if abs(mval - self.current) < 0.05 else "MISMATCH"
                A(f"  {fmt_id(mid):<12} : {mval:.1f} A  [{flag}]")
            A("")

        A(f"CSV data: {os.path.basename(self.csv_path)}")
        A("=" * 58)

        tmp = self.report_path + ".tmp"
        with open(tmp, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, self.report_path)   # atomic, so partial reads never happen


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("interface", nargs="?", default="can0",
                    help="CAN interface (default: can0)")
    ap.add_argument("--dir", default=".",
                    help="directory for log files (default: current dir)")
    args = ap.parse_args()

    session = SolarSession(args.dir)

    print(f"Listening on {args.interface}")
    print(f"Report : {session.report_path}")
    print(f"CSV    : {session.csv_path}")
    print("\nCheck the report anytime with:")
    print(f"  watch -n 2 cat {session.report_path}")
    print("\nCtrl+C to stop.\n")

    try:
        bus = can.interface.Bus(channel=args.interface, bustype="socketcan")
    except Exception as e:
        print(f"Failed to open {args.interface}: {e}")
        print("Bring the interface up first, e.g.:")
        print(f"  sudo ip link set {args.interface} up type can bitrate 250000")
        sys.exit(1)

    last_report = 0.0
    last_sample = 0.0

    while True:
        msg = bus.recv(timeout=1.0)
        if msg is not None:
            session.handle_frame(msg)

        now = time.monotonic()

        if now - last_sample >= SAMPLE_INTERVAL:
            last_sample = now
            session.sample()

        if now - last_report >= REPORT_INTERVAL:
            last_report = now
            session.write_report()

            # brief one-line status on stdout too
            c = session.current
            v = session.voltage
            s = session.soc
            print(f"\r{fmt_duration(session.elapsed())}  "
                  f"{'--' if c is None else f'{c:.1f}A'}  "
                  f"{'--' if v is None else f'{v:.1f}V'}  "
                  f"{'--' if s is None else f'{s}%'}  "
                  f"{session.amp_hours:.3f}Ah  {session.watt_hours:.1f}Wh   ",
                  end="", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")