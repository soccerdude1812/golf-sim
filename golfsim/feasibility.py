"""Tracking-feasibility calculator.

This module turns the hand-wavy question "can a $500 two-camera rig actually
track a golf ball?" into hard numbers.  Given a camera/lens/lighting/geometry
configuration and a ball speed, it computes:

  * how long the ball stays inside the measured launch corridor,
  * how many *samples* (strobe pulses or frames) you get inside it,
  * how far the ball moves between samples, in metres and in pixels,
  * the motion blur smear during a single exposure/pulse, in pixels,
  * the resulting ball-speed resolution.

The headline real-world fact it encodes: a golf ball off a driver travels at
~70 m/s.  At 60 fps full-frame it moves ~1.2 m *per frame*, so a naive video
approach gets ~1 image inside a 1.5 m corridor -- useless.  The fix used by
working DIY launch monitors (e.g. PiTrac) is a strobe: pulse an IR light
several times during one exposure so a single global-shutter frame contains
several sharp, time-stamped ball images.  This calculator shows that approach
clears the bar while a plain webcam does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import BALL_DIAMETER_M, MPH_PER_MS


@dataclass
class RigConfig:
    name: str
    sensor_w_px: int
    sensor_h_px: int
    pixel_pitch_um: float        # sensor pixel size
    focal_mm: float              # lens focal length
    fps: float                   # sensor frame rate at the used resolution
    exposure_us: float           # rolling/global exposure OR strobe-pulse width
    strobe_pulses_per_frame: int # 1 == ordinary frame; >1 == strobed exposure
    strobe_interval_us: float    # time between strobe pulses within a frame
    distance_to_corridor_m: float
    corridor_len_m: float        # length of the launch corridor both cams see
    centroid_err_px: float = 0.3 # sub-pixel localisation error (1 sigma)

    def focal_px(self) -> float:
        return (self.focal_mm * 1e-3) / (self.pixel_pitch_um * 1e-6)

    def hfov_deg(self) -> float:
        import math
        return math.degrees(2 * math.atan((self.sensor_w_px / 2) / self.focal_px()))

    def m_per_px_at_corridor(self) -> float:
        """Ground-sampling distance: metres on the ball plane per pixel."""
        return self.distance_to_corridor_m / self.focal_px()


@dataclass
class FeasibilityReport:
    rig: str
    ball_speed_ms: float
    samples_in_corridor: float
    sample_dt_s: float
    travel_per_sample_m: float
    travel_per_sample_px: float
    blur_px: float
    ball_diameter_px: float
    speed_resolution_ms: float
    speed_resolution_pct: float
    ok_samples: bool
    ok_blur: bool
    ok_ball_size: bool

    @property
    def feasible(self) -> bool:
        return self.ok_samples and self.ok_blur and self.ok_ball_size

    def summary(self) -> str:
        flag = lambda b: "PASS" if b else "FAIL"
        return (
            f"[{self.rig}] ball {self.ball_speed_ms * MPH_PER_MS:.0f} mph\n"
            f"  samples in corridor : {self.samples_in_corridor:.1f}   "
            f"(need >=3)            {flag(self.ok_samples)}\n"
            f"  travel / sample     : {self.travel_per_sample_m*100:.1f} cm  "
            f"= {self.travel_per_sample_px:.0f} px\n"
            f"  motion blur / pulse : {self.blur_px:.1f} px   "
            f"(need < ~ball/3)      {flag(self.ok_blur)}\n"
            f"  ball diameter       : {self.ball_diameter_px:.0f} px  "
            f"(need >=6)            {flag(self.ok_ball_size)}\n"
            f"  speed resolution    : +/-{self.speed_resolution_ms:.2f} m/s "
            f"({self.speed_resolution_pct:.2f}%)\n"
            f"  ==> {'FEASIBLE' if self.feasible else 'NOT FEASIBLE'}"
        )


def evaluate(rig: RigConfig, ball_speed_ms: float,
             ball_distance_for_size_m: float | None = None) -> FeasibilityReport:
    fpx = rig.focal_px()
    gsd = rig.m_per_px_at_corridor()       # metres per pixel on the ball plane

    # --- sampling -----------------------------------------------------------
    # Honest model: with a strobe you get `strobe_pulses_per_frame` sharp ball
    # images *per frame the ball is visible in*.  The ball is visible in
    # n_frames = time_in_corridor * fps frames (>=1 -- you always catch it in
    # at least one frame if the trigger is timed).  Without a strobe each frame
    # gives a single (smeared) image.
    time_in_corridor = rig.corridor_len_m / ball_speed_ms
    n_frames_seen = max(1.0, time_in_corridor * rig.fps)
    if rig.strobe_pulses_per_frame > 1:
        sample_dt = rig.strobe_interval_us * 1e-6
        samples = rig.strobe_pulses_per_frame * n_frames_seen
    else:
        sample_dt = 1.0 / rig.fps
        samples = time_in_corridor / sample_dt + 1.0

    travel_per_sample_m = ball_speed_ms * sample_dt
    travel_per_sample_px = travel_per_sample_m / gsd

    # --- motion blur during a single pulse/exposure -------------------------
    blur_m = ball_speed_ms * (rig.exposure_us * 1e-6)
    blur_px = blur_m / gsd

    # --- ball apparent size -------------------------------------------------
    dist = ball_distance_for_size_m or rig.distance_to_corridor_m
    ball_diam_px = BALL_DIAMETER_M * fpx / dist

    # --- speed resolution ---------------------------------------------------
    # speed = (px displacement * gsd) / dt ; error dominated by the two
    # endpoint centroid errors added in quadrature, scaled across the whole
    # measured baseline of (samples-1) intervals.
    import math
    n_int = max(samples - 1.0, 1.0)
    disp_err_px = math.sqrt(2.0) * rig.centroid_err_px
    total_disp_px = travel_per_sample_px * n_int
    rel = disp_err_px / total_disp_px if total_disp_px > 0 else 1.0
    speed_res_ms = rel * ball_speed_ms

    ok_samples = samples >= 3.0
    ok_blur = blur_px < ball_diam_px / 3.0
    ok_ball = ball_diam_px >= 6.0

    return FeasibilityReport(
        rig=rig.name, ball_speed_ms=ball_speed_ms,
        samples_in_corridor=samples, sample_dt_s=sample_dt,
        travel_per_sample_m=travel_per_sample_m,
        travel_per_sample_px=travel_per_sample_px,
        blur_px=blur_px, ball_diameter_px=ball_diam_px,
        speed_resolution_ms=speed_res_ms,
        speed_resolution_pct=100.0 * speed_res_ms / ball_speed_ms,
        ok_samples=ok_samples, ok_blur=ok_blur, ok_ball_size=ok_ball,
    )


# --- Reference rig presets used in the docs and tests --------------------

def pi_global_shutter_strobed() -> RigConfig:
    """The recommended build: Raspberry Pi Global Shutter camera (Sony IMX296,
    1456x1088, 3.45 um pixels) + 6 mm CS lens, 1.0 m from a 1.2 m corridor,
    with a 4-pulse IR strobe (12 us pulses, 900 us apart) per exposure."""
    return RigConfig(
        name="Pi GS + 6mm + IR strobe",
        sensor_w_px=1456, sensor_h_px=1088, pixel_pitch_um=3.45,
        focal_mm=6.0, fps=60.0, exposure_us=12.0,
        strobe_pulses_per_frame=5, strobe_interval_us=1300.0,
        distance_to_corridor_m=1.25, corridor_len_m=0.6, centroid_err_px=0.3,
    )


def plain_webcam_60fps() -> RigConfig:
    """A typical 1080p/60 rolling-shutter webcam with NO strobe -- included to
    show, quantitatively, why it does not work for a driver."""
    return RigConfig(
        name="1080p60 webcam, no strobe",
        sensor_w_px=1920, sensor_h_px=1080, pixel_pitch_um=2.9,
        focal_mm=3.6, fps=60.0, exposure_us=4000.0,
        strobe_pulses_per_frame=1, strobe_interval_us=0.0,
        distance_to_corridor_m=1.25, corridor_len_m=0.6, centroid_err_px=0.5,
    )
