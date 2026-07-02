"""End-to-end shot pipeline: 2-D detections -> launch params -> flight -> stats.

The pipeline is deliberately decoupled from the camera *source*.  It accepts
the per-camera ordered blob lists (from live capture, recorded files, or the
synthetic generator) plus the calibrated cameras and strobe timing, and runs
the whole chain.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .flight_model import LaunchConditions, simulate
from .geometry import Camera
from .launch import launch_from_velocity, LaunchParameters
from .spin import estimate_spin_empirical, SpinEstimate
from .stats import build_stats, ShotStats
from .tracking import build_track, fit_launch_velocity, Track3D, VelocityFit


@dataclass
class ShotResult:
    stats: ShotStats
    track: Track3D
    fit: VelocityFit
    launch: LaunchParameters


def process_shot(cam_a: Camera, blobs_a, cam_b: Camera, blobs_b,
                 strobe_interval_s: float,
                 spin: SpinEstimate | None = None,
                 club_speed_ms: float | None = None,
                 club: str = "driver",
                 roll_factor: float = 0.0,
                 max_reproj_px: float | None = 5.0) -> ShotResult:
    """Run the full chain for one shot.

    ``blobs_a`` / ``blobs_b`` : ordered Nx2 pixel arrays, paired by strobe pulse.
    ``spin`` : a measured SpinEstimate, or None to fall back to the empirical
    estimate from launch angle + ball speed.
    ``max_reproj_px`` : consistency gate.  A cross-camera mispairing (one
    camera's blob order reversed relative to the other) triangulates garbage
    with a reprojection error ~100x normal; if the mean error exceeds this
    threshold the pairing is retried with camera B reversed, and if it is
    still exceeded a ValueError is raised rather than reporting a bogus shot.
    Pass None to disable the gate.
    """
    track = build_track(cam_a, blobs_a, cam_b, blobs_b, strobe_interval_s)
    if max_reproj_px is not None and \
            float(np.mean(track.reproj_err_px)) > max_reproj_px:
        rev = build_track(cam_a, blobs_a, cam_b,
                          np.asarray(blobs_b, float)[::-1], strobe_interval_s)
        if float(np.mean(rev.reproj_err_px)) < \
                float(np.mean(track.reproj_err_px)):
            track = rev
        if float(np.mean(track.reproj_err_px)) > max_reproj_px:
            raise ValueError(
                f"blob pairing inconsistent: mean reprojection error "
                f"{float(np.mean(track.reproj_err_px)):.1f} px > "
                f"{max_reproj_px} px -- check camera sync/calibration")
    fit = fit_launch_velocity(track)
    if fit.velocity0[0] < 0.0:
        # The ball always flies downrange (+X).  A negative vx means the blob
        # order was reversed in BOTH cameras (the detector's principal-axis
        # sign is arbitrary when no reference pixel is given): time-reverse
        # the track and refit.
        track = Track3D(times=track.times,
                        points=track.points[::-1].copy(),
                        reproj_err_px=track.reproj_err_px[::-1].copy())
        fit = fit_launch_velocity(track)
    launch = launch_from_velocity(fit, club_speed_ms=club_speed_ms)

    if spin is None:
        spin = estimate_spin_empirical(launch.ball_speed_ms,
                                       launch.launch_angle_deg, club=club)

    conditions = LaunchConditions(
        ball_speed_ms=launch.ball_speed_ms,
        launch_angle_deg=launch.launch_angle_deg,
        azimuth_deg=launch.azimuth_deg,
        back_spin_rpm=spin.back_spin_rpm,
        side_spin_rpm=spin.side_spin_rpm,
    )
    flight = simulate(conditions, roll_factor=roll_factor)

    stats = build_stats(launch, spin, flight,
                        fit_rms_m=fit.rms_residual_m,
                        mean_reproj_px=float(np.mean(track.reproj_err_px)))
    return ShotResult(stats=stats, track=track, fit=fit, launch=launch)
