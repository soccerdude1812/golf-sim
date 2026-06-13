"""Validate the flight model against REAL measured launch-monitor data.

Trackman PGA/LPGA Tour averages are real human swings measured by professional
launch monitors. We feed the measured launch conditions into our model and
require the predicted carry to track the *measured* carry across the whole bag.

Only Driver and 7-iron were used to tune the model; every other club here is
out-of-sample, so this guards generalisation, not curve-fitting.
"""
import pytest

from golfsim.constants import ms_from_mph
from golfsim.flight_model import LaunchConditions, simulate

# club, ball_speed_mph, launch_deg, spin_rpm, measured_carry_yd, tuned?
REAL = [
    ("Driver",      167, 10.9, 2686, 275, True),
    ("3-wood",      158,  9.2, 3655, 243, False),
    ("5-wood",      152,  9.4, 4350, 230, False),
    ("Hybrid",      146, 10.2, 4437, 225, False),
    ("3-iron",      142, 10.4, 4630, 212, False),
    ("4-iron",      137, 11.0, 4836, 203, False),
    ("5-iron",      132, 12.1, 5361, 194, False),
    ("6-iron",      127, 14.1, 6231, 183, False),
    ("7-iron",      120, 16.3, 7097, 172, True),
    ("8-iron",      115, 18.1, 7998, 160, False),
    ("9-iron",      109, 20.4, 8647, 148, False),
    ("PW",          102, 24.2, 9304, 136, False),
    ("LPGA Driver", 140, 13.2, 2611, 218, False),
    ("LPGA 7-iron", 104, 19.0, 6699, 141, False),
]


@pytest.mark.parametrize("club,bs,la,spin,carry,_tuned", REAL)
def test_each_club_within_tolerance(club, bs, la, spin, carry, _tuned):
    pred = simulate(LaunchConditions(ms_from_mph(bs), la, 0.0, spin, 0.0)).carry_yards
    # every real club must predict within 10 yd / ~5% of the measured carry
    assert abs(pred - carry) <= 10.0, f"{club}: pred {pred:.1f} vs meas {carry}"


def test_held_out_mean_error_small():
    held = [(bs, la, spin, carry) for _, bs, la, spin, carry, tuned in REAL if not tuned]
    errs = [abs(simulate(LaunchConditions(ms_from_mph(bs), la, 0, spin, 0)).carry_yards - c)
            for bs, la, spin, c in held]
    mae = sum(errs) / len(errs)
    assert mae < 6.0, f"held-out MAE {mae:.1f} yd too high"
