"""Trackman PGA/LPGA tour-average launch data -- the single source of truth.

Real human swings measured by professional launch monitors, as reproduced
widely, e.g.:
  https://www.trackman.com/blog/golf/introducing-updated-tour-averages
  https://golf.com/instruction/driving/this-is-how-far-pga-and-lpga-tour-players-hit-it-with-every-club/

Consumed by scripts/fit_aero.py (fits the aero constants to it),
scripts/validate_real_data.py (prints model-vs-measured), and
tests/test_real_data_validation.py (regression gate).  Edit HERE only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TourRow:
    club: str
    ball_speed_mph: float
    launch_deg: float
    spin_rpm: float
    carry_yd: float                 # measured carry
    height_yd: float                # measured max height
    land_angle_deg: float           # measured descent angle
    tour: str = "PGA"
    holdout: bool = False           # held out by scripts/fit_aero.py --holdout


TOUR_AVERAGES: list[TourRow] = [
    TourRow("Driver",  167, 10.9, 2686, 275, 32, 38),
    TourRow("3-wood",  158,  9.2, 3655, 243, 30, 43, holdout=True),
    TourRow("5-wood",  152,  9.4, 4350, 230, 31, 47),
    TourRow("Hybrid",  146, 10.2, 4437, 225, 29, 47, holdout=True),
    TourRow("3-iron",  142, 10.4, 4630, 212, 27, 46),
    TourRow("4-iron",  137, 11.0, 4836, 203, 28, 48, holdout=True),
    TourRow("5-iron",  132, 12.1, 5361, 194, 31, 49),
    TourRow("6-iron",  127, 14.1, 6231, 183, 30, 50, holdout=True),
    TourRow("7-iron",  120, 16.3, 7097, 172, 32, 50),
    TourRow("8-iron",  115, 18.1, 7998, 160, 31, 50, holdout=True),
    TourRow("9-iron",  109, 20.4, 8647, 148, 30, 51),
    TourRow("PW",      102, 24.2, 9304, 136, 29, 52),
    TourRow("LPGA Driver", 140, 13.2, 2611, 218, 25, 37, tour="LPGA"),
    TourRow("LPGA 7-iron", 104, 19.0, 6699, 141, 26, 47, tour="LPGA",
            holdout=True),
]
