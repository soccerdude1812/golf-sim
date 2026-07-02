"""Validate the flight model against REAL measured launch-monitor data.

Trackman PGA/LPGA Tour averages are real human swings measured by professional
launch monitors. We feed the measured launch conditions into our model and
require the predicted carry, apex height AND descent angle to track the
*measured* values across the whole bag -- a model that only matches carry can
still fly the wrong shape (too flat / too ballooned).

The five aero constants were least-squares fit to all 14 rows (carry + apex +
descent simultaneously).  Generalisation is verified by a reproducible
hold-out refit (``scripts/fit_aero.py --holdout``): fitting with 6 clubs held
out predicts them with 4.0 yd carry / 1.0 yd apex / 1.5 deg descent MAE --
i.e. the functional form captures the physics rather than memorising the
table.
"""
import os

import pytest

from golfsim.constants import ms_from_mph
from golfsim.flight_model import LaunchConditions, simulate

from golfsim.tourdata import TOUR_AVERAGES

# (club, ball_speed_mph, launch_deg, spin_rpm, carry_yd, height_yd, land_deg)
REAL = [(r.club, r.ball_speed_mph, r.launch_deg, r.spin_rpm,
         r.carry_yd, r.height_yd, r.land_angle_deg) for r in TOUR_AVERAGES]


@pytest.mark.parametrize("club,bs,la,spin,carry,height,land", REAL)
def test_each_club_within_tolerance(club, bs, la, spin, carry, height, land):
    r = simulate(LaunchConditions(ms_from_mph(bs), la, 0.0, spin, 0.0))
    # carry within 10 yd, apex within 4 yd, descent within 6 deg of measured
    assert abs(r.carry_yards - carry) <= 10.0, \
        f"{club}: carry {r.carry_yards:.1f} vs meas {carry}"
    assert abs(r.apex_yards - height) <= 4.0, \
        f"{club}: apex {r.apex_yards:.1f} vs meas {height}"
    assert abs(r.descent_angle_deg - land) <= 6.0, \
        f"{club}: descent {r.descent_angle_deg:.1f} vs meas {land}"


@pytest.mark.skipif(not os.environ.get("GOLFSIM_SLOW_TESTS"),
                    reason="hold-out refit takes ~1 min and needs scipy; "
                           "set GOLFSIM_SLOW_TESTS=1 to run")
def test_holdout_refit_generalises():
    """Machine-enforced version of the generalisation claim: refit the five
    constants with 6 clubs held out and require the unseen clubs to still
    predict well.  Guards against a future re-fit that overfits the table
    (the fast per-club assertions above validate on the fit data itself)."""
    pytest.importorskip("scipy")
    import subprocess
    import sys
    from pathlib import Path
    out = subprocess.run(
        [sys.executable,
         str(Path(__file__).resolve().parent.parent / "scripts" / "fit_aero.py"),
         "--holdout"],
        capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr
    line = [l for l in out.stdout.splitlines() if l.startswith("held-out:")][0]
    # "held-out: carry MAE X.X yd (max Y.Y) | apex MAE ..."
    carry_mae = float(line.split("carry MAE")[1].split("yd")[0])
    assert carry_mae < 6.0, line


def test_whole_bag_mean_errors_small():
    rs = [(simulate(LaunchConditions(ms_from_mph(bs), la, 0, spin, 0)),
           carry, height, land)
          for _, bs, la, spin, carry, height, land in REAL]
    n = len(rs)
    carry_mae = sum(abs(r.carry_yards - c) for r, c, _, _ in rs) / n
    apex_mae = sum(abs(r.apex_yards - h) for r, _, h, _ in rs) / n
    desc_mae = sum(abs(r.descent_angle_deg - d) for r, _, _, d in rs) / n
    assert carry_mae < 6.0, f"carry MAE {carry_mae:.1f} yd too high"
    assert apex_mae < 2.0, f"apex MAE {apex_mae:.1f} yd too high"
    assert desc_mae < 3.0, f"descent MAE {desc_mae:.1f} deg too high"
