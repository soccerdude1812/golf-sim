"""Validate the aerodynamic flight model against published launch-monitor data.

The carry distances commercial monitors report for standard driver/iron launch
conditions are well known; the model's tuned coefficients must reproduce them
to within a reasonable tolerance (real-world shot-to-shot and equipment spread
is itself +/- several yards).
"""

import numpy as np
import pytest

from golfsim.constants import ms_from_mph
from golfsim.flight_model import (LaunchConditions, simulate, drag_coefficient,
                                  lift_coefficient)


# (name, ball_speed_mph, launch_deg, spin_rpm, expected_carry_yd, tol_yd)
CASES = [
    ("amateur driver", 147, 14.0, 2700, 228, 16),
    ("tour driver",    167, 10.9, 2686, 272, 16),
    ("long driver",    183, 10.0, 2200, 305, 18),
    ("7-iron",         120, 16.3, 7000, 172, 16),
]


@pytest.mark.parametrize("name,bs,la,spin,carry,tol", CASES)
def test_carry_matches_reference(name, bs, la, spin, carry, tol):
    r = simulate(LaunchConditions(ms_from_mph(bs), la, 0.0, spin, 0.0))
    assert r.carry_yards == pytest.approx(carry, abs=tol), \
        f"{name}: got {r.carry_yards:.1f} yd, expected ~{carry}"


def test_descent_and_apex_physical():
    r = simulate(LaunchConditions(ms_from_mph(167), 10.9, 0.0, 2686, 0.0))
    assert 33 < r.descent_angle_deg < 45        # driver descent ~ 38-41 deg
    assert 25 < r.apex_m < 45                    # apex ~ 90-130 ft
    assert 5.5 < r.flight_time_s < 7.5


def test_more_spin_more_lift_and_height():
    base = simulate(LaunchConditions(ms_from_mph(150), 12, 0, 2000, 0))
    spun = simulate(LaunchConditions(ms_from_mph(150), 12, 0, 4000, 0))
    assert spun.apex_m > base.apex_m             # backspin lifts the ball

def test_side_spin_curves_ball():
    straight = simulate(LaunchConditions(ms_from_mph(150), 12, 0, 2500, 0))
    fade = simulate(LaunchConditions(ms_from_mph(150), 12, 0, 2500, 1500))
    assert abs(fade.offline_m) > abs(straight.offline_m)
    assert fade.offline_m > 0                    # +side spin curves right


def test_coefficients_monotonic():
    assert lift_coefficient(0.10) > lift_coefficient(0.02)
    assert drag_coefficient(0.10) > drag_coefficient(0.0)
    assert lift_coefficient(0.0) == 0.0


def test_zero_gravity_sanity():
    # purely a numerical-integration sanity check on the integrator
    r = simulate(LaunchConditions(ms_from_mph(100), 45, 0, 0, 0))
    assert r.carry_m > 0 and np.isfinite(r.carry_m)
