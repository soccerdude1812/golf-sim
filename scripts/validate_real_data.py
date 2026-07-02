#!/usr/bin/env python3
"""Validate the ball-flight model against REAL measured launch-monitor data.

These are aggregated Trackman PGA/LPGA Tour averages -- i.e. real human swings
measured by professional radar/camera launch monitors, with the *measured*
carry, max height and land angle as ground truth.  We feed the measured launch
conditions (ball speed, launch angle, spin) into our model and compare its
predicted flight to the measurements.

IMPORTANT honesty note: the model's 5 aerodynamic constants were least-squares
fit to ALL of these rows (carry + apex + descent together).  Generalisation is
verified by a reproducible hold-out refit (scripts/fit_aero.py --holdout):
fitting with 6 clubs held out predicts them with 4.0 yd carry / 1.0 yd apex /
1.5 deg descent MAE, so the functional form captures the physics rather than
memorising the table.  The matching regression gate lives in
tests/test_real_data_validation.py.

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
from golfsim.tourdata import TOUR_AVERAGES

PGA = [r for r in TOUR_AVERAGES if r.tour == "PGA"]
LPGA = [r for r in TOUR_AVERAGES if r.tour == "LPGA"]


def run(table, title):
    print(f"\n{title}")
    print(f"{'club':12s} {'ball':>5s} {'launch':>6s} {'spin':>5s} "
          f"{'carry':>11s} {'apex':>10s} {'descent':>11s}")
    print("-" * 74)
    errs = {"carry": [], "apex": [], "desc": []}
    for row in table:
        r = simulate(LaunchConditions(ms_from_mph(row.ball_speed_mph),
                                      row.launch_deg, 0.0, row.spin_rpm, 0.0))
        errs["carry"].append(abs(r.carry_yards - row.carry_yd))
        errs["apex"].append(abs(r.apex_yards - row.height_yd))
        errs["desc"].append(abs(r.descent_angle_deg - row.land_angle_deg))
        print(f"{row.club:12s} {row.ball_speed_mph:5.0f} {row.launch_deg:6.1f} "
              f"{row.spin_rpm:5.0f} "
              f"{r.carry_yards:5.1f}/{row.carry_yd:3.0f}yd "
              f"{r.apex_yards:4.1f}/{row.height_yd:2.0f}yd "
              f"{r.descent_angle_deg:5.1f}/{row.land_angle_deg:2.0f}deg")
    print("-" * 74)
    print(f"MAE  carry {sum(errs['carry'])/len(table):.1f} yd | "
          f"apex {sum(errs['apex'])/len(table):.1f} yd | "
          f"descent {sum(errs['desc'])/len(table):.1f} deg   (pred/measured)")
    return errs


def main():
    a = run(PGA, "=== Trackman PGA Tour averages (real measured swings) ===")
    b = run(LPGA, "=== Trackman LPGA Tour averages (real measured swings) ===")
    n = len(PGA) + len(LPGA)
    print("\n" + "=" * 74)
    print(f"OVERALL over {n} real data points:  "
          f"carry MAE {(sum(a['carry'])+sum(b['carry']))/n:.1f} yd,  "
          f"apex MAE {(sum(a['apex'])+sum(b['apex']))/n:.1f} yd,  "
          f"descent MAE {(sum(a['desc'])+sum(b['desc']))/n:.1f} deg")
    print("=" * 74)


if __name__ == "__main__":
    main()
