"""Sign-convention regression tests.

The world frame is right-handed (X downrange, Z up, so +Y = LEFT of the
target line), while every user-facing signed quantity follows the golf /
launch-monitor convention "positive = right of the target line".  These tests
pin that mapping down: a mirror regression here would silently flip every
push/pull and fade/draw readout on real hardware.
"""

import numpy as np
import pytest

from golfsim.constants import ms_from_mph
from golfsim.flight_model import LaunchConditions, simulate
from golfsim.geometry import Camera, intrinsics_from_fov
from golfsim.launch import launch_from_velocity
from golfsim.spin import spin_from_marker_track
from golfsim.tracking import VelocityFit


def test_positive_azimuth_is_push_right():
    lc = LaunchConditions(ms_from_mph(150), 12.0, 5.0, 2500, 0.0)
    v = lc.velocity_vector()
    assert v[1] < 0, "+azimuth (right) must map to -Y (world left = +Y)"
    r = simulate(lc)
    assert r.offline_m > 0, "a push right must land offline right (+)"


def test_positive_side_spin_is_fade_right():
    fade = simulate(LaunchConditions(ms_from_mph(150), 12.0, 0.0, 2500, 1500))
    draw = simulate(LaunchConditions(ms_from_mph(150), 12.0, 0.0, 2500, -1500))
    assert fade.offline_m > 0, "+side spin must curve the ball right"
    assert draw.offline_m < 0, "-side spin must curve the ball left"


def test_backspin_axis_gives_lift():
    lc = LaunchConditions(ms_from_mph(150), 12.0, 0.0, 3000, 0.0)
    w = lc.spin_vector()
    v = lc.velocity_vector()
    magnus = np.cross(w / np.linalg.norm(w), v / np.linalg.norm(v))
    assert magnus[2] > 0, "pure backspin must produce upward Magnus force"


def test_launch_from_velocity_azimuth_sign_roundtrip():
    for az_true in (-4.0, -1.0, 0.0, 2.0, 6.0):
        lc = LaunchConditions(ms_from_mph(150), 12.0, az_true, 2500, 0.0)
        fit = VelocityFit(position0=np.zeros(3), velocity0=lc.velocity_vector(),
                          accel=np.zeros(3), rms_residual_m=0.0)
        lp = launch_from_velocity(fit)
        assert lp.azimuth_deg == pytest.approx(az_true, abs=1e-9)


def test_spin_from_marker_track_recovers_rate():
    omega = 300.0                       # rad/s ~ 2865 rpm
    dt = 1.3e-3
    offs = [(20 * np.cos(0.3 + omega * dt * k),
             20 * np.sin(0.3 + omega * dt * k)) for k in range(5)]
    est = spin_from_marker_track(offs, dt)
    assert est.measured
    assert est.back_spin_rpm == pytest.approx(omega * 60 / (2 * np.pi), rel=1e-9)
    assert est.side_spin_rpm == 0.0


def test_camera_is_upright():
    """look_at must build an upright OpenCV-convention camera: a higher world
    point appears HIGHER in the image (smaller v), and for the face-on camera
    on the -Y side, downrange (+X) motion moves image-RIGHT (larger u)."""
    K = intrinsics_from_fov(1456, 1088, focal_mm=6.0, pixel_pitch_um=3.45)
    cam = Camera.from_pose(K, (0.2, -1.25, 0.28), (0.2, 0, 0.06), 1456, 1088)
    mid = cam.project([[0.2, 0.0, 0.06]])[0]
    hi = cam.project([[0.2, 0.0, 0.18]])[0]
    dn = cam.project([[0.5, 0.0, 0.06]])[0]
    assert hi[1] < mid[1]
    assert dn[0] > mid[0]
