"""Convert a fitted 3-D launch velocity into golf launch parameters."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import DEG_PER_RAD, MPH_PER_MS
from .tracking import VelocityFit


@dataclass
class LaunchParameters:
    ball_speed_ms: float
    launch_angle_deg: float          # vertical, above horizontal
    azimuth_deg: float               # +right (push), -left (pull)
    velocity_ms: np.ndarray          # raw 3-D vector (world frame)

    # optional, set when a club-head measurement is available
    club_speed_ms: float | None = None
    smash_factor: float | None = None

    @property
    def ball_speed_mph(self) -> float:
        return self.ball_speed_ms * MPH_PER_MS

    @property
    def club_speed_mph(self) -> float | None:
        return None if self.club_speed_ms is None else self.club_speed_ms * MPH_PER_MS


def launch_from_velocity(fit: VelocityFit,
                         club_speed_ms: float | None = None) -> LaunchParameters:
    v = fit.velocity0
    vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
    speed = float(np.linalg.norm(v))
    horiz = float(np.hypot(vx, vy))

    launch_angle = np.degrees(np.arctan2(vz, horiz))
    azimuth = np.degrees(np.arctan2(vy, vx))

    smash = None
    if club_speed_ms and club_speed_ms > 0:
        smash = speed / club_speed_ms

    return LaunchParameters(
        ball_speed_ms=speed,
        launch_angle_deg=float(launch_angle),
        azimuth_deg=float(azimuth),
        velocity_ms=v.copy(),
        club_speed_ms=club_speed_ms,
        smash_factor=smash,
    )
