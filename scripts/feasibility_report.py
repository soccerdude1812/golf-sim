#!/usr/bin/env python3
"""Print the tracking-feasibility report for the recommended rig vs a webcam,
across the full range of golf ball speeds.  This is the quantitative answer to
"will these cameras actually track the ball?"."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from golfsim.constants import ms_from_mph
from golfsim.feasibility import (evaluate, pi_global_shutter_strobed,
                                 plain_webcam_60fps)

SPEEDS_MPH = [70, 95, 130, 167, 183]   # wedge -> tour driver -> long drive


def main():
    for rig in (pi_global_shutter_strobed(), plain_webcam_60fps()):
        print("#" * 60)
        print(f"# {rig.name}")
        print(f"#   HFOV {rig.hfov_deg():.0f} deg | "
              f"ground sampling {rig.m_per_px_at_corridor()*1000:.2f} mm/px | "
              f"{rig.strobe_pulses_per_frame} pulse(s)/frame")
        print("#" * 60)
        for mph in SPEEDS_MPH:
            print(evaluate(rig, ms_from_mph(mph)).summary())
            print()


if __name__ == "__main__":
    main()
