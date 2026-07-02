#!/usr/bin/env python3
"""Run a synthetic shot end-to-end and print the stat sheet.

This is the fastest way to see the whole system work without any hardware:
it fabricates a shot with known launch parameters, renders what the two
cameras would see (strobed IR frames), then runs the real detection ->
triangulation -> launch-fit -> flight pipeline and prints the result next to
the ground truth.

    python scripts/run_demo.py --ball-speed 167 --launch 11 --azimuth 1 --spin 2700
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from golfsim.config import RigConfig, stereo_angle_deg
from golfsim.constants import ms_from_mph
from golfsim.detection import BallDetector
from golfsim.flight_model import LaunchConditions
from golfsim.pipeline import process_shot
from golfsim.spin import SpinEstimate
from golfsim.synthetic import generate_shot


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ball-speed", type=float, default=167.0, help="mph")
    ap.add_argument("--launch", type=float, default=11.0, help="deg")
    ap.add_argument("--azimuth", type=float, default=1.0, help="deg (+right)")
    ap.add_argument("--spin", type=float, default=2700.0, help="rpm backspin")
    ap.add_argument("--side-spin", type=float, default=0.0, help="rpm (+right)")
    ap.add_argument("--noise", type=float, default=2.0, help="image noise sigma")
    ap.add_argument("--measure-spin", action="store_true",
                    help="feed true spin to the pipeline (else it is estimated)")
    ap.add_argument("--plot", metavar="PNG",
                    help="save a side/top trajectory drawing (truth vs "
                         "recovered) to this file; requires matplotlib")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    cfg = RigConfig()
    cam_a, cam_b = cfg.geometry.cameras()
    print(f"Rig: stereo angle {stereo_angle_deg(cfg.geometry):.0f} deg, "
          f"strobe {cfg.strobe.pulses_per_frame} pulses @ "
          f"{cfg.strobe.interval_us:.0f} us\n")

    truth = LaunchConditions(ms_from_mph(args.ball_speed), args.launch,
                             args.azimuth, args.spin, args.side_spin)
    shot = generate_shot(cam_a, cam_b, truth, cfg.strobe.interval_s,
                         n_pulses=cfg.strobe.pulses_per_frame, render=True,
                         noise_sigma=args.noise, false_blobs=3, seed=args.seed)

    det = BallDetector(min_radius_px=3, max_radius_px=150, thresh=90)
    # order strobe images by distance from the projected tee position
    tee_a = cam_a.project([[0.0, 0.0, 0.0]])[0]
    tee_b = cam_b.project([[0.0, 0.0, 0.0]])[0]
    blobs_a = det.detect_ordered(shot.frames_a[0], reference_uv=tee_a)
    blobs_b = det.detect_ordered(shot.frames_b[0], reference_uv=tee_b)
    print(f"Detected {len(blobs_a)} / {len(blobs_b)} strobe images "
          f"(face-on / behind-high)")
    if len(blobs_a) != len(blobs_b):
        print("  ! mismatched blob counts -- cannot pair; aborting")
        return

    px_a = np.array([b.uv for b in blobs_a])
    px_b = np.array([b.uv for b in blobs_b])

    spin = SpinEstimate(args.spin, args.side_spin, measured=True) \
        if args.measure_spin else None
    res = process_shot(cam_a, px_a, cam_b, px_b, cfg.strobe.interval_s,
                       spin=spin)

    print("\n" + res.stats.pretty())
    print("\n--- ground truth (for comparison) ---")
    print(f" ball speed {args.ball_speed:.1f} mph | launch {args.launch:.1f} "
          f"deg | dir {args.azimuth:.1f} deg | spin {args.spin:.0f} rpm")
    err = abs(res.stats.ball_speed_mph - args.ball_speed)
    print(f" recovered ball-speed error: {err:.2f} mph "
          f"({100*err/args.ball_speed:.2f}%)")

    if args.plot:
        from golfsim.flight_model import simulate
        _plot_trajectories(simulate(truth), res, args.plot)


def _plot_trajectories(truth_flight, res, out_path):
    """Side + top view of the simulated flight: ground truth launch vs the
    flight simulated from the RECOVERED launch parameters, plus the measured
    strobe track.  World +Y is left of the target line, so the top view plots
    -Y ("offline right") upward to match the stat sheet's R/L convention."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from golfsim.constants import YARDS_PER_M
    from golfsim.flight_model import simulate

    t_traj = truth_flight.trajectory * YARDS_PER_M
    # re-simulate from the recovered launch for the drawn comparison
    rec = simulate(LaunchConditions(
        ball_speed_ms=res.launch.ball_speed_ms,
        launch_angle_deg=res.launch.launch_angle_deg,
        azimuth_deg=res.launch.azimuth_deg,
        back_spin_rpm=res.stats.back_spin_rpm,
        side_spin_rpm=res.stats.side_spin_rpm))
    r_traj = rec.trajectory * YARDS_PER_M

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.plot(t_traj[:, 0], t_traj[:, 2] * 3, label="ground truth", lw=2)
    ax1.plot(r_traj[:, 0], r_traj[:, 2] * 3, "--", label="recovered", lw=2)
    ax1.set_ylabel("height (ft)")
    ax1.set_title(f"side view — carry {rec.carry_yards:.0f} yd, "
                  f"apex {rec.apex_m*3.2808:.0f} ft, "
                  f"descent {rec.descent_angle_deg:.0f}°")
    ax1.legend(); ax1.grid(alpha=0.3)

    ax2.plot(t_traj[:, 0], -t_traj[:, 1], label="ground truth", lw=2)
    ax2.plot(r_traj[:, 0], -r_traj[:, 1], "--", label="recovered", lw=2)
    ax2.axhline(0, color="#888", lw=0.8, ls=":")
    ax2.set_xlabel("carry (yd)")
    ax2.set_ylabel("offline (yd, + = right)")
    ax2.set_title(f"top view — offline {rec.offline_yards:+.1f} yd "
                  f"({'R' if rec.offline_yards >= 0 else 'L'})")
    ax2.legend(); ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"\ntrajectory drawing -> {out_path}")


if __name__ == "__main__":
    main()
