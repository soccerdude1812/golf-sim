"""Unit tests for the camera model and stereo triangulation."""

import numpy as np
import pytest

from golfsim.geometry import (Camera, intrinsics_from_fov, look_at,
                              triangulate_point, triangulate_points)


def _make_pair():
    K = intrinsics_from_fov(1456, 1088, focal_mm=6.0, pixel_pitch_um=3.45)
    a = Camera.from_pose(K, (0.2, -1.25, 0.28), (0.2, 0, 0.06), 1456, 1088)
    b = Camera.from_pose(K, (-0.75, -0.5, 1.05), (0.2, 0, 0.06), 1456, 1088)
    return a, b


def test_camera_center_recovered():
    K = intrinsics_from_fov(1456, 1088, focal_mm=6.0, pixel_pitch_um=3.45)
    center = np.array([0.3, -1.0, 0.4])
    cam = Camera.from_pose(K, center, (0.2, 0, 0.05), 1456, 1088)
    assert np.allclose(cam.center, center, atol=1e-9)


def test_look_at_points_at_target():
    R, t = look_at((0, -1, 0), (0, 0, 0))
    # optical axis (camera +Z, third row of R) should point +Y toward target
    assert np.allclose(R[2], [0, 1, 0], atol=1e-9)


def test_project_principal_point():
    K = intrinsics_from_fov(1456, 1088, focal_mm=6.0, pixel_pitch_um=3.45)
    cam = Camera.from_pose(K, (0, -1, 0), (0, 0, 0), 1456, 1088)
    # a point straight along the optical axis projects to the principal point
    px = cam.project([[0, 0, 0]])[0]
    assert px == pytest.approx([(1456 - 1) / 2, (1088 - 1) / 2], abs=1e-6)


def test_triangulation_roundtrip():
    a, b = _make_pair()
    rng = np.random.default_rng(0)
    pts = rng.uniform([-0.1, -0.2, -0.1], [0.6, 0.2, 0.3], size=(50, 3))
    pa = a.project(pts)
    pb = b.project(pts)
    rec = triangulate_points(a, pa, b, pb)
    assert np.allclose(rec, pts, atol=1e-6)


def test_triangulation_noise_bounded():
    a, b = _make_pair()
    rng = np.random.default_rng(1)
    p = np.array([0.25, 0.03, 0.08])
    errs = []
    for _ in range(200):
        pa = a.project([p])[0] + rng.normal(0, 0.3, 2)
        pb = b.project([p])[0] + rng.normal(0, 0.3, 2)
        rec = triangulate_point(a, pa, b, pb)
        errs.append(np.linalg.norm(rec - p))
    # 0.3 px localisation -> sub-millimetre 3-D error at this geometry/scale
    assert np.mean(errs) < 2e-3
