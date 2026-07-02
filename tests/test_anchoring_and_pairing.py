"""Tests for world-frame anchoring (set_world_from_board) and the pipeline's
cross-camera mispairing gate.

A mispaired track (one camera's blob order reversed relative to the other)
triangulates garbage with ~100x the normal reprojection error; the pipeline
must recover it (simple reversal) or refuse it (arbitrary scramble) rather
than report a bogus shot.
"""

import numpy as np
import pytest

from golfsim.config import RigConfig
from golfsim.constants import ms_from_mph
from golfsim.flight_model import LaunchConditions
from golfsim.pipeline import process_shot
from golfsim.spin import SpinEstimate
from golfsim.synthetic import generate_shot

cv2 = pytest.importorskip("cv2")

from golfsim.calibration import set_world_from_board  # noqa: E402


def _shot(az=0.0):
    cfg = RigConfig()
    cam_a, cam_b = cfg.geometry.cameras()
    truth = LaunchConditions(ms_from_mph(150.0), 12.0, az, 2600, 0)
    shot = generate_shot(cam_a, cam_b, truth, cfg.strobe.interval_s,
                         n_pulses=cfg.strobe.pulses_per_frame, render=False)
    return cfg, cam_a, cam_b, shot


def test_set_world_from_board_recovers_world_poses():
    cfg = RigConfig()
    cam_a, cam_b = cfg.geometry.cameras()

    # ground-truth stereo pose of B relative to A: X_b = R_ab X_a + T_ab
    R_ab = cam_b.R @ cam_a.R.T
    T_ab = cam_b.t - R_ab @ cam_a.t

    # a 9x6 board lying flat on the mat, one corner at the ball, +X edge
    # down the target line -- exactly the anchoring procedure in the docs
    xs, ys = np.meshgrid(np.arange(9) * 0.025, np.arange(6) * 0.025)
    board_world = np.column_stack([xs.ravel(), ys.ravel(),
                                   np.zeros(xs.size)])
    corners_a = cam_a.project(board_world)
    assert np.all(np.isfinite(corners_a)), "board must be visible in cam A"

    R_a, t_a, R_b, t_b = set_world_from_board(
        cam_a.K, np.zeros(5), corners_a, board_world, R_ab, T_ab)

    assert np.allclose(R_a, cam_a.R, atol=1e-6)
    assert np.allclose(t_a, cam_a.t, atol=1e-6)
    assert np.allclose(R_b, cam_b.R, atol=1e-6)
    assert np.allclose(t_b, cam_b.t, atol=1e-6)


def test_reversed_camera_b_order_is_recovered():
    cfg, cam_a, cam_b, shot = _shot(az=1.5)
    spin = SpinEstimate(2600, 0, measured=True)
    res = process_shot(cam_a, shot.px_a, cam_b, shot.px_b[::-1],
                       cfg.strobe.interval_s, spin=spin)
    assert res.stats.ball_speed_mph == pytest.approx(150.0, abs=0.5)
    assert res.stats.launch_angle_deg == pytest.approx(12.0, abs=0.3)
    assert res.stats.azimuth_deg == pytest.approx(1.5, abs=0.3)
    assert res.stats.mean_reproj_err_px < 1.0


def test_scrambled_pairing_is_refused():
    cfg, cam_a, cam_b, shot = _shot()
    scrambled = shot.px_b[[2, 0, 4, 1, 3]]
    spin = SpinEstimate(2600, 0, measured=True)
    with pytest.raises(ValueError, match="pairing"):
        process_shot(cam_a, shot.px_a, cam_b, scrambled,
                     cfg.strobe.interval_s, spin=spin)
