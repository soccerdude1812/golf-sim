"""Spin estimation.

Spin is by far the hardest quantity to measure optically on a budget, and you
should treat these numbers as the least reliable part of the system.  Two
strategies are provided:

1. ``spin_from_marker_track`` -- the *measured* path.  If the ball carries a
   high-contrast mark (a drawn dot, an alignment logo, or a dimple-pattern
   feature) that can be located in several strobed images, the rotation of the
   mark between pulses gives the spin rate and axis directly.  This is what
   PiTrac and commercial camera monitors do.  It needs the mark to be visible
   and resolved -- realistically a marked range ball and good IR contrast.

2. ``estimate_spin_empirical`` -- the *fallback*.  When no mark is tracked we
   estimate backspin from a spin-loft / ball-speed regression.  This is only a
   plausibility estimate, NOT a measurement, and is clearly flagged as such in
   the output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import RPM_PER_RADS


@dataclass
class SpinEstimate:
    back_spin_rpm: float
    side_spin_rpm: float
    measured: bool                  # True if from marker tracking, else estimate
    note: str = ""


def spin_from_marker_track(marker_offsets_px, strobe_interval_s,
                           side_axis_tilt_deg=0.0) -> SpinEstimate:
    """Estimate spin from the angular travel of a surface mark.

    ``marker_offsets_px`` is a sequence of (du, dv) vectors giving the mark's
    position relative to the ball centre in each strobed image.  The angle of
    that vector advances by omega*dt between pulses; we average the per-pulse
    angular increments.  This is exact when the spin axis points along the
    camera's optical axis and degrades as the axis tilts away -- so measure
    from the camera that faces the spin axis (the face-on camera for
    backspin-dominated shots).  The rate measurement itself has no sign or
    axis: ``side_axis_tilt_deg`` is an INPUT you supply (e.g. from the
    mark's lateral drift across pulses), not something derived from the
    offsets; positive tilt = fade/slice component (ball curves right),
    matching ``LaunchConditions.side_spin_rpm``.
    """
    offs = np.atleast_2d(np.asarray(marker_offsets_px, float))
    if offs.shape[0] < 2:
        raise ValueError("need >=2 marker observations")
    angles = np.unwrap(np.arctan2(offs[:, 1], offs[:, 0]))
    d_angle = np.diff(angles)
    omega = float(np.mean(d_angle) / strobe_interval_s)   # rad/s (in image)
    total_rpm = abs(omega) * RPM_PER_RADS

    tilt = np.radians(side_axis_tilt_deg)
    back = total_rpm * np.cos(tilt)
    side = total_rpm * np.sin(tilt)
    return SpinEstimate(back_spin_rpm=back, side_spin_rpm=side,
                        measured=True,
                        note="spin from tracked surface marker")


def estimate_spin_empirical(ball_speed_ms, launch_angle_deg,
                            club: str = "driver") -> SpinEstimate:
    """Fallback backspin estimate from launch angle and speed.

    Uses the well-known observation that backspin rises with dynamic loft /
    launch angle and falls with ball speed.  Coefficients are rough averages
    across club types; values are clamped to sane ranges.
    """
    from .constants import MPH_PER_MS
    bs = ball_speed_ms * MPH_PER_MS

    # Backspin rises roughly linearly with dynamic loft (launch angle).  These
    # (offset, slope-per-degree) pairs are tuned so typical launches land near
    # published averages: driver ~2700 rpm @ 11 deg, mid-iron ~6500 @ 16 deg.
    offset, per_deg = {
        "driver": (1200.0, 135.0),
        "iron":   (1500.0, 320.0),
        "wedge":  (2000.0, 250.0),
    }.get(club, (1200.0, 150.0))
    spin = offset + per_deg * max(launch_angle_deg, 1.0)
    # weak speed correction: a faster ball at the same launch spins a touch less
    spin *= (150.0 / max(bs, 60.0)) ** 0.15
    spin = float(np.clip(spin, 1500.0, 12000.0))
    return SpinEstimate(back_spin_rpm=spin, side_spin_rpm=0.0,
                        measured=False,
                        note="EMPIRICAL ESTIMATE (no marker tracked) -- "
                             "treat as approximate")
