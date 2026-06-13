"""Assemble timed 2-D detections from two cameras into a 3-D launch track and
fit the initial velocity.

Both cameras share one strobe, so the k-th blob seen by camera A corresponds
to the k-th blob seen by camera B (same pulse, same instant).  Each matched
pair is triangulated to a 3-D world point with a known timestamp.  A constant
-acceleration model is then least-squares fit per axis; the velocity at the
first sample is the launch velocity.  A constant-acceleration (rather than
constant-velocity) fit absorbs gravity and the small aerodynamic deceleration
that act over the ~20 ms measurement window.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import Camera, reprojection_error, triangulate_points


@dataclass
class Track3D:
    times: np.ndarray            # (N,) seconds, t=0 at first sample
    points: np.ndarray           # (N,3) world-frame positions (m)
    reproj_err_px: np.ndarray    # (N,) mean reprojection error per point

    def __len__(self) -> int:
        return len(self.times)


@dataclass
class VelocityFit:
    position0: np.ndarray        # (3,) fitted position at t=0
    velocity0: np.ndarray        # (3,) fitted velocity at t=0  (launch vector)
    accel: np.ndarray            # (3,) fitted constant acceleration
    rms_residual_m: float        # fit quality

    @property
    def speed(self) -> float:
        return float(np.linalg.norm(self.velocity0))


def build_track(cam_a: Camera, blobs_a, cam_b: Camera, blobs_b,
                strobe_interval_s: float) -> Track3D:
    """Pair, triangulate and time-stamp the blob sequences.

    ``blobs_a`` / ``blobs_b`` are sequences of pixel coords (Nx2), already
    ordered along the direction of travel (see ``BallDetector.detect_ordered``).
    The two sequences must have equal length (one entry per strobe pulse).
    """
    pa = np.atleast_2d(np.asarray(blobs_a, float))
    pb = np.atleast_2d(np.asarray(blobs_b, float))
    if pa.shape[0] != pb.shape[0]:
        raise ValueError(
            f"camera blob counts differ: {pa.shape[0]} vs {pb.shape[0]}; "
            "cannot pair pulses")
    n = pa.shape[0]
    if n < 3:
        raise ValueError(f"need >=3 paired samples, got {n}")

    pts = triangulate_points(cam_a, pa, cam_b, pb)
    times = np.arange(n) * strobe_interval_s

    err = 0.5 * (reprojection_error(cam_a, pts, pa)
                 + reprojection_error(cam_b, pts, pb))
    return Track3D(times=times, points=pts, reproj_err_px=err)


def fit_launch_velocity(track: Track3D) -> VelocityFit:
    """Least-squares fit of p(t) = p0 + v0 t + 0.5 a t^2 per axis."""
    t = track.times
    A = np.column_stack([np.ones_like(t), t, 0.5 * t ** 2])  # (N,3)
    p0 = np.empty(3)
    v0 = np.empty(3)
    acc = np.empty(3)
    resid_sq = 0.0
    for k in range(3):
        coef, res, *_ = np.linalg.lstsq(A, track.points[:, k], rcond=None)
        p0[k], v0[k], acc[k] = coef
        pred = A @ coef
        resid_sq += float(np.sum((pred - track.points[:, k]) ** 2))
    rms = float(np.sqrt(resid_sq / (len(track) * 3)))
    return VelocityFit(position0=p0, velocity0=v0, accel=acc,
                       rms_residual_m=rms)
