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

# club, ball mph, launch deg, spin rpm,
#   measured carry yd, max height yd, land angle deg, hold out?
TABLE = [
    ("Driver",      167, 10.9, 2686, 275, 32, 38, False),
    ("3-wood",      158,  9.2, 3655, 243, 30, 43, True),
    ("5-wood",      152,  9.4, 4350, 230, 31, 47, False),
    ("Hybrid",      146, 10.2, 4437, 225, 29, 47, True),
    ("3-iron",      142, 10.4, 4630, 212, 27, 46, False),
    ("4-iron",      137, 11.0, 4836, 203, 28, 48, True),
    ("5-iron",      132, 12.1, 5361, 194, 31, 49, False),
    ("6-iron",      127, 14.1, 6231, 183, 30, 50, True),
    ("7-iron",      120, 16.3, 7097, 172, 32, 50, False),
    ("8-iron",      115, 18.1, 7998, 160, 31, 50, True),
    ("9-iron",      109, 20.4, 8647, 148, 30, 51, False),
    ("PW",          102, 24.2, 9304, 136, 29, 52, False),
    ("LPGA Driver", 140, 13.2, 2611, 218, 25, 37, False),
    ("LPGA 7-iron", 104, 19.0, 6699, 141, 26, 47, True),
]

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
    for club, bs, la, spin, carry, height, land, _ in rows:
        w = ROW_WEIGHT.get(club, 1.0)
        r = simulate_row(bs, la, spin)
        out += [w * W_CARRY * (r.carry_yards - carry),
                w * W_APEX * (r.apex_yards - height),
                w * W_DESC * (r.descent_angle_deg - land)]
    return np.array(out)


def report(rows, label):
    errs = {"carry": [], "apex": [], "desc": []}
    for club, bs, la, spin, carry, height, land, _ in rows:
        r = simulate_row(bs, la, spin)
        errs["carry"].append(abs(r.carry_yards - carry))
        errs["apex"].append(abs(r.apex_yards - height))
        errs["desc"].append(abs(r.descent_angle_deg - land))
        print(f"  {club:12s} carry {r.carry_yards:6.1f}/{carry:3d} yd   "
              f"apex {r.apex_yards:4.1f}/{height:2d} yd   "
              f"descent {r.descent_angle_deg:4.1f}/{land:2d} deg")
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

    fit_rows = [r for r in TABLE if not (args.holdout and r[-1])]
    held_rows = [r for r in TABLE if args.holdout and r[-1]]

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
