"""Assemble the full shot stat sheet from measured + simulated quantities."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .constants import FEET_PER_M, MPH_PER_MS
from .flight_model import FlightResult
from .launch import LaunchParameters
from .spin import SpinEstimate


@dataclass
class ShotStats:
    # --- measured launch ---
    ball_speed_mph: float
    launch_angle_deg: float
    azimuth_deg: float
    back_spin_rpm: float
    side_spin_rpm: float
    spin_measured: bool
    club_speed_mph: float | None
    smash_factor: float | None
    # --- simulated flight ---
    carry_yards: float
    total_yards: float
    apex_ft: float
    descent_angle_deg: float
    flight_time_s: float
    offline_yards: float
    landing_speed_mph: float
    # --- quality / provenance ---
    fit_rms_residual_mm: float
    mean_reproj_err_px: float
    notes: str = ""

    def pretty(self) -> str:
        side = "R" if self.azimuth_deg >= 0 else "L"
        off_side = "R" if self.offline_yards >= 0 else "L"
        club = f"{self.club_speed_mph:5.1f}" if self.club_speed_mph else "  n/a"
        smash = f"{self.smash_factor:4.2f}" if self.smash_factor else " n/a"
        spin_tag = "" if self.spin_measured else "  (estimated)"
        return (
            "================  SHOT  ================\n"
            f" Ball speed     : {self.ball_speed_mph:6.1f} mph\n"
            f" Club speed     : {club} mph     Smash: {smash}\n"
            f" Launch angle   : {self.launch_angle_deg:6.1f} deg\n"
            f" Launch dir     : {abs(self.azimuth_deg):6.1f} deg {side}\n"
            f" Back spin      : {self.back_spin_rpm:6.0f} rpm{spin_tag}\n"
            f" Side spin      : {abs(self.side_spin_rpm):6.0f} rpm "
            f"{'R' if self.side_spin_rpm>=0 else 'L'}\n"
            "----------------------------------------\n"
            f" Carry          : {self.carry_yards:6.1f} yd\n"
            f" Total          : {self.total_yards:6.1f} yd\n"
            f" Apex           : {self.apex_ft:6.1f} ft\n"
            f" Descent angle  : {self.descent_angle_deg:6.1f} deg\n"
            f" Flight time    : {self.flight_time_s:6.1f} s\n"
            f" Offline        : {abs(self.offline_yards):6.1f} yd {off_side}\n"
            "----------------------------------------\n"
            f" fit residual   : {self.fit_rms_residual_mm:6.2f} mm   "
            f"reproj err: {self.mean_reproj_err_px:.2f} px\n"
            "========================================"
        )

    def to_dict(self) -> dict:
        return asdict(self)


def build_stats(launch: LaunchParameters, spin: SpinEstimate,
                flight: FlightResult, fit_rms_m: float,
                mean_reproj_px: float, notes: str = "") -> ShotStats:
    return ShotStats(
        ball_speed_mph=launch.ball_speed_mph,
        launch_angle_deg=launch.launch_angle_deg,
        azimuth_deg=launch.azimuth_deg,
        back_spin_rpm=spin.back_spin_rpm,
        side_spin_rpm=spin.side_spin_rpm,
        spin_measured=spin.measured,
        club_speed_mph=launch.club_speed_mph,
        smash_factor=launch.smash_factor,
        carry_yards=flight.carry_yards,
        total_yards=flight.total_yards,
        apex_ft=flight.apex_m * FEET_PER_M,
        descent_angle_deg=flight.descent_angle_deg,
        flight_time_s=flight.flight_time_s,
        offline_yards=flight.offline_yards,
        landing_speed_mph=flight.landing_speed_ms * MPH_PER_MS,
        fit_rms_residual_mm=fit_rms_m * 1000.0,
        mean_reproj_err_px=mean_reproj_px,
        notes=(notes + ("" if spin.measured else " " + spin.note)).strip(),
    )
