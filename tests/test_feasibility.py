"""The feasibility calculator must say YES to the recommended strobed Pi rig
and NO to a plain webcam, across the golf speed range."""

import pytest

from golfsim.constants import ms_from_mph
from golfsim.feasibility import (evaluate, pi_global_shutter_strobed,
                                 plain_webcam_60fps)


@pytest.mark.parametrize("mph", [95, 130, 167, 183])
def test_recommended_rig_is_feasible(mph):
    rep = evaluate(pi_global_shutter_strobed(), ms_from_mph(mph))
    assert rep.feasible, rep.summary()
    assert rep.samples_in_corridor >= 3
    assert rep.speed_resolution_pct < 1.0


@pytest.mark.parametrize("mph", [95, 167])
def test_plain_webcam_fails(mph):
    rep = evaluate(plain_webcam_60fps(), ms_from_mph(mph))
    assert not rep.feasible
    # it fails specifically on sampling and motion blur, not ball size
    assert (not rep.ok_samples) or (not rep.ok_blur)


def test_blur_scales_with_exposure():
    rig = pi_global_shutter_strobed()
    short = evaluate(rig, ms_from_mph(167))
    rig.exposure_us = 2000.0
    long = evaluate(rig, ms_from_mph(167))
    assert long.blur_px > short.blur_px
