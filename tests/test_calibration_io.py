"""Round-trip test for saving/loading a calibrated rig (no OpenCV needed)."""

import numpy as np

from golfsim.calibration import save_rig, load_rig
from golfsim.config import RigConfig


def test_rig_save_load_roundtrip(tmp_path):
    cam_a, cam_b = RigConfig().geometry.cameras()
    path = tmp_path / "rig.json"
    save_rig(str(path), cam_a, cam_b, strobe_interval_s=1300e-6)

    a2, b2, dt = load_rig(str(path))
    assert dt == 1300e-6
    for orig, loaded in ((cam_a, a2), (cam_b, b2)):
        assert np.allclose(orig.K, loaded.K)
        assert np.allclose(orig.R, loaded.R)
        assert np.allclose(orig.t, loaded.t)
        assert orig.width == loaded.width and orig.height == loaded.height
        assert orig.name == loaded.name


def test_loaded_rig_triangulates_same(tmp_path):
    cfg = RigConfig()
    cam_a, cam_b = cfg.geometry.cameras()
    path = tmp_path / "rig.json"
    save_rig(str(path), cam_a, cam_b, cfg.strobe.interval_s)
    a2, b2, _ = load_rig(str(path))

    p = np.array([[0.25, 0.03, 0.08]])
    from golfsim.geometry import triangulate_points
    rec0 = triangulate_points(cam_a, cam_a.project(p), cam_b, cam_b.project(p))
    rec1 = triangulate_points(a2, a2.project(p), b2, b2.project(p))
    assert np.allclose(rec0, rec1, atol=1e-9)
