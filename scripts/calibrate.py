#!/usr/bin/env python3
"""Calibrate the two-camera rig from chessboard images and save it to JSON.

Expected layout (PNG/JPG, grayscale or color):
    <dir>/cam_a/*.png          intrinsic views for camera A (face-on)
    <dir>/cam_b/*.png          intrinsic views for camera B (behind-high)
    <dir>/stereo/a_*.png       shared views, camera A   (sorted -> paired)
    <dir>/stereo/b_*.png       shared views, camera B

Note: this produces the *relative* stereo pose.  Anchoring it to the world
frame (ball = origin, X down the target line) needs one extra view of the
board placed flat on the hitting mat with a known origin/orientation; see
docs/CALIBRATION.md.  For a quick start you can also just use the verified
default geometry in golfsim.config.RigConfig (no calibration needed for the
synthetic demo).
"""
import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from golfsim.calibration import (calibrate_intrinsics, calibrate_stereo,
                                 cameras_from_world_poses, save_rig)
import numpy as np


def _load(globpat):
    return [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in sorted(glob.glob(globpat))]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--pattern", default="9x6", help="inner corners, cols x rows")
    ap.add_argument("--square", type=float, default=0.025, help="square size (m)")
    ap.add_argument("--strobe-interval-us", type=float, default=1300.0)
    ap.add_argument("--out", default="calibration_data/rig.json")
    args = ap.parse_args()

    cols, rows = (int(x) for x in args.pattern.lower().split("x"))
    d = Path(args.dir)

    print("Calibrating intrinsics A...")
    ia = calibrate_intrinsics(_load(str(d / "cam_a" / "*")), (cols, rows), args.square)
    print(f"  RMS {ia.rms_px:.3f} px")
    print("Calibrating intrinsics B...")
    ib = calibrate_intrinsics(_load(str(d / "cam_b" / "*")), (cols, rows), args.square)
    print(f"  RMS {ib.rms_px:.3f} px")

    print("Stereo calibration...")
    R, T, rms = calibrate_stereo(_load(str(d / "stereo" / "a_*")),
                                 _load(str(d / "stereo" / "b_*")), ia, ib,
                                 (cols, rows), args.square)
    print(f"  stereo RMS {rms:.3f} px")

    # Camera A is the world reference here (R=I, t=0); B is placed relative to
    # it.  Re-anchor to the ball origin per docs/CALIBRATION.md for absolute
    # world coordinates.
    cam_a, cam_b = cameras_from_world_poses(
        ia.K, ia.dist, np.eye(3), np.zeros(3), ia.image_size,
        ib.K, ib.dist, R, T, ib.image_size)
    save_rig(args.out, cam_a, cam_b, args.strobe_interval_us * 1e-6)
    print(f"Saved rig -> {args.out}")
    print("NOTE: this rig uses camera A as the origin.  Ball SPEED will be "
          "correct as-is, but launch/azimuth ANGLES are relative to camera A "
          "until you anchor the rig to the ball/target-line world frame "
          "(docs/CALIBRATION.md, step 4).  run_live.py will warn until then.")


if __name__ == "__main__":
    main()
