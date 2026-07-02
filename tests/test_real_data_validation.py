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
import pytest

from golfsim.constants import ms_from_mph
from golfsim.flight_model import LaunchConditions, simulate

# club, ball_speed_mph, launch_deg, spin_rpm,
#   measured carry_yd, max_height_yd, land_angle_deg   (Trackman tour averages)
REAL = [
    ("Driver",      167, 10.9, 2686, 275, 32, 38),
    ("3-wood",      158,  9.2, 3655, 243, 30, 43),
    ("5-wood",      152,  9.4, 4350, 230, 31, 47),
    ("Hybrid",      146, 10.2, 4437, 225, 29, 47),
    ("3-iron",      142, 10.4, 4630, 212, 27, 46),
    ("4-iron",      137, 11.0, 4836, 203, 28, 48),
    ("5-iron",      132, 12.1, 5361, 194, 31, 49),
    ("6-iron",      127, 14.1, 6231, 183, 30, 50),
    ("7-iron",      120, 16.3, 7097, 172, 32, 50),
    ("8-iron",      115, 18.1, 7998, 160, 31, 50),
    ("9-iron",      109, 20.4, 8647, 148, 30, 51),
    ("PW",          102, 24.2, 9304, 136, 29, 52),
    ("LPGA Driver", 140, 13.2, 2611, 218, 25, 37),
    ("LPGA 7-iron", 104, 19.0, 6699, 141, 26, 47),
]


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
