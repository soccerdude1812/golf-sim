"""Pinhole camera model, projection and stereo triangulation.

World frame convention used throughout the project
--------------------------------------------------
Origin is the ball-at-rest position on the tee/mat.

    X : down the target line (the direction the ball is supposed to fly)
    Y : lateral, completing a right-handed frame (Y = Z x X)
    Z : straight up

A *launch* therefore has a large +X velocity component, +Z gives the
vertical launch angle, and the sign of Y gives push (right) / pull (left).

A camera is modelled as a pinhole with intrinsic matrix K and a world->camera
rigid transform (R, t):  x_cam = R @ X_world + t.  The optical axis is the
camera +Z axis; image x grows to the right, image y grows downward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


def look_at(center, target, world_up=(0.0, 0.0, 1.0)):
    """Build a world->camera rotation R for a camera at ``center`` looking at
    ``target``.  Returns (R, t) with t = -R @ center.

    The camera optical axis (camera +Z) points from center toward target.
    """
    center = np.asarray(center, dtype=float)
    target = np.asarray(target, dtype=float)
    world_up = np.asarray(world_up, dtype=float)

    z_c = target - center
    n = np.linalg.norm(z_c)
    if n < 1e-12:
        raise ValueError("camera center and target coincide")
    z_c = z_c / n

    x_c = np.cross(world_up, z_c)
    if np.linalg.norm(x_c) < 1e-9:
        # Looking straight up/down: pick an arbitrary up.
        world_up = np.array([1.0, 0.0, 0.0])
        x_c = np.cross(world_up, z_c)
    x_c = x_c / np.linalg.norm(x_c)

    y_c = np.cross(z_c, x_c)  # already unit length

    R = np.vstack([x_c, y_c, z_c])      # rows are camera axes in world coords
    t = -R @ center
    return R, t


def intrinsics_from_fov(width_px, height_px, hfov_deg=None, focal_mm=None,
                        pixel_pitch_um=None):
    """Build a pinhole intrinsic matrix K.

    Provide either a horizontal field of view (``hfov_deg``) or a physical
    lens focal length + sensor pixel pitch (``focal_mm`` and
    ``pixel_pitch_um``).  Principal point is the image centre.
    """
    if focal_mm is not None and pixel_pitch_um is not None:
        fx = fy = (focal_mm * 1e-3) / (pixel_pitch_um * 1e-6)
    elif hfov_deg is not None:
        fx = fy = (width_px / 2.0) / np.tan(np.radians(hfov_deg) / 2.0)
    else:
        raise ValueError("specify hfov_deg or (focal_mm and pixel_pitch_um)")
    cx = (width_px - 1) / 2.0
    cy = (height_px - 1) / 2.0
    return np.array([[fx, 0.0, cx],
                     [0.0, fy, cy],
                     [0.0, 0.0, 1.0]], dtype=float)


@dataclass
class Camera:
    """A calibrated pinhole camera."""
    K: np.ndarray
    R: np.ndarray                       # world -> camera rotation (3x3)
    t: np.ndarray                       # world -> camera translation (3,)
    width: int
    height: int
    dist: np.ndarray = field(default_factory=lambda: np.zeros(5))
    name: str = "cam"

    @classmethod
    def from_pose(cls, K, center, target, width, height,
                  world_up=(0.0, 0.0, 1.0), dist=None, name="cam"):
        R, t = look_at(center, target, world_up)
        return cls(K=np.asarray(K, float), R=R, t=t,
                   width=int(width), height=int(height),
                   dist=np.zeros(5) if dist is None else np.asarray(dist, float),
                   name=name)

    @property
    def center(self) -> np.ndarray:
        """Camera centre in world coordinates: C = -R^T t."""
        return -self.R.T @ self.t

    @property
    def P(self) -> np.ndarray:
        """3x4 projection matrix P = K [R | t]."""
        Rt = np.hstack([self.R, self.t.reshape(3, 1)])
        return self.K @ Rt

    def project(self, points_world) -> np.ndarray:
        """Project Nx3 world points to Nx2 pixels (ideal pinhole, no
        distortion).  Points behind the camera get NaN."""
        pts = np.atleast_2d(np.asarray(points_world, dtype=float))
        cam = (self.R @ pts.T + self.t.reshape(3, 1)).T   # N x 3 in cam frame
        z = cam[:, 2]
        uv = np.full((pts.shape[0], 2), np.nan)
        good = z > 1e-9
        x = cam[good, 0] / z[good]
        y = cam[good, 1] / z[good]
        fx, fy = self.K[0, 0], self.K[1, 1]
        cx, cy = self.K[0, 2], self.K[1, 2]
        uv[good, 0] = fx * x + cx
        uv[good, 1] = fy * y + cy
        return uv

    def ray(self, pixel) -> tuple[np.ndarray, np.ndarray]:
        """Back-project a pixel to a world-space ray (origin, unit direction)."""
        u, v = float(pixel[0]), float(pixel[1])
        Kinv = np.linalg.inv(self.K)
        d_cam = Kinv @ np.array([u, v, 1.0])
        d_world = self.R.T @ d_cam
        d_world = d_world / np.linalg.norm(d_world)
        return self.center, d_world


def triangulate_point(cam_a: Camera, px_a, cam_b: Camera, px_b) -> np.ndarray:
    """Linear DLT triangulation of a single world point from two views.

    Solves the homogeneous system A X = 0 built from the two projection
    matrices and returns the inhomogeneous 3D point.
    """
    Pa, Pb = cam_a.P, cam_b.P
    ua, va = float(px_a[0]), float(px_a[1])
    ub, vb = float(px_b[0]), float(px_b[1])
    A = np.vstack([
        ua * Pa[2] - Pa[0],
        va * Pa[2] - Pa[1],
        ub * Pb[2] - Pb[0],
        vb * Pb[2] - Pb[1],
    ])
    _, _, Vt = np.linalg.svd(A)
    X = Vt[-1]
    return X[:3] / X[3]


def triangulate_points(cam_a: Camera, px_a, cam_b: Camera, px_b) -> np.ndarray:
    """Vectorised wrapper: Nx2, Nx2 pixel arrays -> Nx3 world points."""
    px_a = np.atleast_2d(np.asarray(px_a, float))
    px_b = np.atleast_2d(np.asarray(px_b, float))
    out = np.empty((px_a.shape[0], 3))
    for i in range(px_a.shape[0]):
        out[i] = triangulate_point(cam_a, px_a[i], cam_b, px_b[i])
    return out


def reprojection_error(cam: Camera, points_world, pixels) -> np.ndarray:
    """Per-point pixel reprojection error magnitude."""
    proj = cam.project(points_world)
    return np.linalg.norm(proj - np.asarray(pixels, float), axis=1)
