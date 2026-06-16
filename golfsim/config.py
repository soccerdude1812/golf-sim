"""Rig configuration: world geometry, camera placement and strobe timing.

This is the single source of truth that ties the physical build to the code.
Distances are metres, angles degrees, in the world frame defined in
``geometry`` (X down the target line, Y lateral, Z up; origin at the ball).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import Camera, intrinsics_from_fov


# --- Sensor / lens presets ------------------------------------------------
IMX296_W, IMX296_H = 1456, 1088         # Raspberry Pi Global Shutter sensor
IMX296_PITCH_UM = 3.45


@dataclass
class CameraPlacement:
    name: str
    center_m: tuple                     # camera position in world frame
    target_m: tuple                     # point it is aimed at
    focal_mm: float = 6.0
    width: int = IMX296_W
    height: int = IMX296_H
    pixel_pitch_um: float = IMX296_PITCH_UM

    def to_camera(self) -> Camera:
        K = intrinsics_from_fov(self.width, self.height,
                                focal_mm=self.focal_mm,
                                pixel_pitch_um=self.pixel_pitch_um)
        return Camera.from_pose(K, self.center_m, self.target_m,
                                self.width, self.height, name=self.name)


@dataclass
class RigGeometry:
    """The two-camera layout requested: one *down-the-line* camera behind the
    golfer and one *face-on* camera to the side.  Both are aimed at the launch
    corridor centre ~0.7 m in front of the ball, where they overlap.

    Coordinates assume a right-handed golfer hitting toward +X.  Adjust the
    centres to match your room; keep both cameras aimed at ``corridor_center``.
    """
    corridor_center_m: tuple = (0.20, 0.0, 0.06)
    corridor_len_m: float = 0.6         # the measured 5-pulse burst (~0.2-0.4 m)

    # FACE-ON / side camera: broadside to the flight line, ~1.25 m to the side
    # and slightly raised.  The ball *crosses* this view, giving the largest
    # strobe-image separation -> it is the primary source of ball speed and
    # vertical launch angle.
    face_on: CameraPlacement = field(default_factory=lambda: CameraPlacement(
        name="FaceOn",
        center_m=(0.20, -1.25, 0.28),
        target_m=(0.20, 0.0, 0.06),
        focal_mm=6.0,
    ))
    # BEHIND-HIGH (down-the-line-ish) camera: behind the golfer, mounted HIGH
    # (~1.85 m, above the top of the backswing -- a camera here at chest height
    # would be in the path of the club) and offset ~40 deg off the flight line.
    # A *pure* down-the-line camera fails (the ball recedes from it and the
    # strobe images merge -- see docs/CAMERA_PLACEMENT.md); the quarter angle
    # keeps the pulses separated while still framing the swing and resolving
    # push/pull.  Mount on a tall stand, shelf, or ceiling/wall bracket.
    down_the_line: CameraPlacement = field(default_factory=lambda: CameraPlacement(
        name="BehindHigh",
        center_m=(-1.0, -0.6, 1.85),
        target_m=(0.20, 0.0, 0.06),
        focal_mm=6.0,
    ))

    def cameras(self) -> tuple[Camera, Camera]:
        return self.down_the_line.to_camera(), self.face_on.to_camera()


@dataclass
class StrobeConfig:
    pulses_per_frame: int = 5
    interval_us: float = 1300.0         # >= ball_diameter / ball_speed so the
    pulse_width_us: float = 12.0        # strobe images stay separated to ~95 mph

    @property
    def interval_s(self) -> float:
        return self.interval_us * 1e-6


@dataclass
class RigConfig:
    geometry: RigGeometry = field(default_factory=RigGeometry)
    strobe: StrobeConfig = field(default_factory=StrobeConfig)


def stereo_angle_deg(rig: RigGeometry) -> float:
    """Angle between the two camera optical axes at the corridor centre -- a
    proxy for triangulation conditioning (near 90 deg is ideal)."""
    a, b = rig.cameras()
    c = np.asarray(rig.corridor_center_m)
    da = c - a.center
    db = c - b.center
    cos = np.dot(da, db) / (np.linalg.norm(da) * np.linalg.norm(db))
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))
