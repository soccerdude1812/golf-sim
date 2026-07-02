"""End-to-end verification of the measurement pipeline.

These tests are the project's central claim-check: given a shot with KNOWN
launch parameters, render what the two cameras would see, then run the real
detection + triangulation + velocity-fit + flight chain and assert the
recovered numbers match the truth within tolerance.
"""

import numpy as np
import pytest

from golfsim.config import RigConfig, stereo_angle_deg
from golfsim.constants import ms_from_mph
from golfsim.detection import BallDetector
from golfsim.flight_model import LaunchConditions, simulate
from golfsim.pipeline import process_shot
from golfsim.spin import SpinEstimate
from golfsim.synthetic import generate_shot


def _rig():
    cfg = RigConfig()
    cam_a, cam_b = cfg.geometry.cameras()
    return cfg, cam_a, cam_b


def test_stereo_geometry_well_conditioned():
    cfg, _, _ = _rig()
    ang = stereo_angle_deg(cfg.geometry)
    # the requested DTL + face-on layout should be near-orthogonal
    assert 60.0 < ang < 120.0


@pytest.mark.parametrize("bs_mph,launch_deg,az_deg", [
    (167.0, 11.0, 0.0),
    (150.0, 14.0, 2.0),
    (120.0, 18.0, -3.0),
    (95.0, 24.0, 1.5),
])
def test_recover_launch_from_pixel_truth(bs_mph, launch_deg, az_deg):
    """Triangulation + fit on noise-free projected pixels must be near-exact."""
    cfg, cam_a, cam_b = _rig()
    truth = LaunchConditions(ms_from_mph(bs_mph), launch_deg, az_deg, 2600, 0)
    shot = generate_shot(cam_a, cam_b, truth, cfg.strobe.interval_s,
                         n_pulses=cfg.strobe.pulses_per_frame, render=False)

    spin = SpinEstimate(2600, 0, measured=True)
    res = process_shot(cam_a, shot.px_a, cam_b, shot.px_b,
                       cfg.strobe.interval_s, spin=spin)

    assert res.stats.ball_speed_mph == pytest.approx(bs_mph, abs=0.5)
    assert res.stats.launch_angle_deg == pytest.approx(launch_deg, abs=0.3)
    assert res.stats.azimuth_deg == pytest.approx(az_deg, abs=0.3)


def test_recover_launch_from_rendered_images():
    """Full chain incl. rendering + blob detection on strobed frames."""
    cfg, cam_a, cam_b = _rig()
    truth = LaunchConditions(ms_from_mph(160.0), 12.0, 1.0, 2600, 0)
    shot = generate_shot(cam_a, cam_b, truth, cfg.strobe.interval_s,
                         n_pulses=cfg.strobe.pulses_per_frame, render=True,
                         noise_sigma=2.0, false_blobs=2, seed=7)

    det = BallDetector(min_radius_px=3, max_radius_px=120, thresh=90)
    blobs_a = det.detect_ordered(shot.frames_a[0])
    blobs_b = det.detect_ordered(shot.frames_b[0])

    # the detector must find exactly the strobe pulses in each camera
    assert len(blobs_a) == cfg.strobe.pulses_per_frame
    assert len(blobs_b) == cfg.strobe.pulses_per_frame

    px_a = np.array([b.uv for b in blobs_a])
    px_b = np.array([b.uv for b in blobs_b])

    spin = SpinEstimate(2600, 0, measured=True)
    res = process_shot(cam_a, px_a, cam_b, px_b, cfg.strobe.interval_s,
                       spin=spin)

    # within ~1 mph / 0.5 deg even after pixel discretisation + noise
    assert res.stats.ball_speed_mph == pytest.approx(160.0, abs=1.5)
    assert res.stats.launch_angle_deg == pytest.approx(12.0, abs=0.6)
    assert res.stats.azimuth_deg == pytest.approx(1.0, abs=0.6)
    # carry should land in a sane driver range
    assert 230 < res.stats.carry_yards < 290
    # reprojection error confirms a consistent triangulation
    assert res.stats.mean_reproj_err_px < 1.5


def test_noise_sensitivity_speed_resolution():
    """Sub-pixel jitter of 0.3 px should keep ball-speed error well under 1%."""
    cfg, cam_a, cam_b = _rig()
    truth = LaunchConditions(ms_from_mph(167.0), 11.0, 0.0, 2600, 0)
    errs = []
    for seed in range(20):
        shot = generate_shot(cam_a, cam_b, truth, cfg.strobe.interval_s,
                             n_pulses=cfg.strobe.pulses_per_frame,
                             render=False, pixel_jitter_px=0.3, seed=seed)
        spin = SpinEstimate(2600, 0, measured=True)
        res = process_shot(cam_a, shot.px_a, cam_b, shot.px_b,
                           cfg.strobe.interval_s, spin=spin)
        errs.append(abs(res.stats.ball_speed_mph - 167.0))
    assert np.mean(errs) < 1.67          # < 1% of 167 mph on average
