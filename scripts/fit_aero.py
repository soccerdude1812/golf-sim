#!/usr/bin/env python3
"""Fit (or re-fit) the flight model's five aerodynamic constants.

Least-squares fits (CD0, CD_SPIN, CD_RE, CL_GAIN, CL_HALF) so that simulated
carry, apex height AND descent angle match the Trackman PGA/LPGA tour-average
table.  This is the script that produced the constants in
golfsim/flight_model.py -- rerun it to reproduce them, or point ``TABLE`` at
your own measured shots to calibrate the model to your ball/conditions.

    python scripts/fit_aero.py             # fit on all 14 rows
    python scripts/fit_aero.py --holdout   # fit on 8 rows, report the error
                                           # on the 6 held-out rows
                                           # (the generalisation check quoted
                                           # in docs/THEORY.md)

Requires scipy (not needed by the library itself): pip install scipy
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import golfsim.flight_model as fm
from golfsim.constants import ms_from_mph
from golfsim.tourdata import TOUR_AVERAGES

# The measured launch table lives in golfsim/tourdata.py (single source of
# truth shared with validate_real_data.py and the regression tests); each
# row's ``holdout`` flag drives --holdout here.
TABLE = TOUR_AVERAGES

# residual weights: 3 yd carry ~ 2 yd apex ~ 2 deg descent ~ "one unit".
# Driver and PW get a nudge so the ends of the bag don't drift.
W_CARRY, W_APEX, W_DESC = 1 / 3.0, 1 / 2.0, 1 / 2.0
ROW_WEIGHT = {"Driver": 1.4, "PW": 1.2}


def set_constants(x):
    fm._CD0, fm._CD_SPIN, fm._CD_RE, fm._CL_GAIN, fm._CL_HALF = x


def simulate_row(bs_mph, la, spin):
    return fm.simulate(fm.LaunchConditions(ms_from_mph(bs_mph), la, 0.0,
                                           spin, 0.0), dt=0.004)


def residuals(x, rows):
    set_constants(x)
    out = []
    for row in rows:
        w = ROW_WEIGHT.get(row.club, 1.0)
        r = simulate_row(row.ball_speed_mph, row.launch_deg, row.spin_rpm)
        out += [w * W_CARRY * (r.carry_yards - row.carry_yd),
                w * W_APEX * (r.apex_yards - row.height_yd),
                w * W_DESC * (r.descent_angle_deg - row.land_angle_deg)]
    return np.array(out)


def report(rows, label):
    errs = {"carry": [], "apex": [], "desc": []}
    for row in rows:
        r = simulate_row(row.ball_speed_mph, row.launch_deg, row.spin_rpm)
        errs["carry"].append(abs(r.carry_yards - row.carry_yd))
        errs["apex"].append(abs(r.apex_yards - row.height_yd))
        errs["desc"].append(abs(r.descent_angle_deg - row.land_angle_deg))
        print(f"  {row.club:12s} carry {r.carry_yards:6.1f}/{row.carry_yd:3.0f} yd   "
              f"apex {r.apex_yards:4.1f}/{row.height_yd:2.0f} yd   "
              f"descent {r.descent_angle_deg:4.1f}/{row.land_angle_deg:2.0f} deg")
    print(f"{label}: carry MAE {np.mean(errs['carry']):.1f} yd "
          f"(max {np.max(errs['carry']):.1f}) | "
          f"apex MAE {np.mean(errs['apex']):.1f} yd | "
          f"descent MAE {np.mean(errs['desc']):.1f} deg\n")


def main():
    try:
        from scipy.optimize import least_squares
    except ImportError:
        sys.exit("scipy is required for fitting: pip install scipy")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", action="store_true",
                    help="fit on the non-held-out rows only and report "
                         "out-of-sample error on the rest")
    args = ap.parse_args()

    fit_rows = [r for r in TABLE if not (args.holdout and r.holdout)]
    held_rows = [r for r in TABLE if args.holdout and r.holdout]

    x0 = np.array([fm._CD0, fm._CD_SPIN, fm._CD_RE, fm._CL_GAIN, fm._CL_HALF])
    lo = np.array([0.02, 0.00, 0.00, 0.10, 0.01])
    hi = np.array([0.35, 0.90, 0.35, 0.90, 0.50])
    sol = least_squares(residuals, x0, bounds=(lo, hi), args=(fit_rows,),
                        xtol=1e-9, ftol=1e-9)
    set_constants(sol.x)

    print("fitted constants (paste into golfsim/flight_model.py):")
    for name, v in zip(("_CD0", "_CD_SPIN", "_CD_RE", "_CL_GAIN", "_CL_HALF"),
                       sol.x):
        print(f"  {name:9s} = {v:.4f}")
    print()
    print(f"fit set ({len(fit_rows)} clubs):")
    report(fit_rows, "fit-set")
    if held_rows:
        print(f"HELD-OUT set ({len(held_rows)} clubs, never seen by the fit):")
        report(held_rows, "held-out")


if __name__ == "__main__":
    main()
