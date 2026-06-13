#!/usr/bin/env python3
"""Validate the ball-flight model against REAL measured launch-monitor data.

These are aggregated Trackman PGA/LPGA Tour averages -- i.e. real human swings
measured by professional radar/camera launch monitors, with the *measured*
carry as ground truth.  We feed the measured launch conditions (ball speed,
launch angle, spin) into our model and compare its predicted carry to the
measured carry.

IMPORTANT honesty note: the model's 3 aerodynamic constants were tuned on the
DRIVER and 7-IRON rows (marked `tuned`).  Every other row is genuinely
out-of-sample (`held-out`) and is the real test of whether the physics
generalises across the bag.

Sources:
  Trackman PGA/LPGA Tour Averages (canonical set), as reproduced widely, e.g.
  https://www.trackman.com/blog/golf/introducing-updated-tour-averages
  https://golf.com/instruction/driving/this-is-how-far-pga-and-lpga-tour-players-hit-it-with-every-club/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from golfsim.constants import ms_from_mph
from golfsim.flight_model import LaunchConditions, simulate

# club, ball_speed_mph, launch_deg, spin_rpm, measured_carry_yd, split
PGA = [
    ("Driver",   167, 10.9, 2686, 275, "tuned"),
    ("3-wood",   158,  9.2, 3655, 243, "held-out"),
    ("5-wood",   152,  9.4, 4350, 230, "held-out"),
    ("Hybrid",   146, 10.2, 4437, 225, "held-out"),
    ("3-iron",   142, 10.4, 4630, 212, "held-out"),
    ("4-iron",   137, 11.0, 4836, 203, "held-out"),
    ("5-iron",   132, 12.1, 5361, 194, "held-out"),
    ("6-iron",   127, 14.1, 6231, 183, "held-out"),
    ("7-iron",   120, 16.3, 7097, 172, "tuned"),
    ("8-iron",   115, 18.1, 7998, 160, "held-out"),
    ("9-iron",   109, 20.4, 8647, 148, "held-out"),
    ("PW",       102, 24.2, 9304, 136, "held-out"),
]
LPGA = [
    ("LPGA Driver", 140, 13.2, 2611, 218, "held-out"),
    ("LPGA 7-iron", 104, 19.0, 6699, 141, "held-out"),
]


def run(table, title):
    print(f"\n{title}")
    print(f"{'club':12s} {'ball':>5s} {'launch':>6s} {'spin':>5s} "
          f"{'meas':>5s} {'pred':>6s} {'err':>6s} {'err%':>6s}  split")
    print("-" * 72)
    errs, held_errs = [], []
    for club, bs, la, spin, carry, split in table:
        r = simulate(LaunchConditions(ms_from_mph(bs), la, 0.0, spin, 0.0))
        pred = r.carry_yards
        err = pred - carry
        errs.append(abs(err))
        if split == "held-out":
            held_errs.append(abs(err))
        print(f"{club:12s} {bs:5d} {la:6.1f} {spin:5d} {carry:5d} "
              f"{pred:6.1f} {err:+6.1f} {100*err/carry:+5.1f}%  {split}")
    mae = sum(errs) / len(errs)
    held_mae = sum(held_errs) / len(held_errs) if held_errs else float("nan")
    print("-" * 72)
    print(f"MAE all: {mae:.1f} yd   |   MAE held-out only: {held_mae:.1f} yd")
    return errs, held_errs


def main():
    a, ah = run(PGA, "=== Trackman PGA Tour averages (real measured swings) ===")
    b, bh = run(LPGA, "=== Trackman LPGA Tour averages (real measured swings) ===")
    all_err = a + b
    held = ah + bh
    print("\n" + "=" * 72)
    print(f"OVERALL  MAE = {sum(all_err)/len(all_err):.1f} yd over "
          f"{len(all_err)} real data points")
    print(f"HELD-OUT MAE = {sum(held)/len(held):.1f} yd over "
          f"{len(held)} clubs the model was NOT tuned on")
    print("=" * 72)


if __name__ == "__main__":
    main()
