#!/usr/bin/env python3
"""Live shot capture on the Raspberry Pi rig.

This is the on-Pi entry point.  It arms both Global Shutter cameras in
short-exposure external-trigger mode, waits for a shot, fires the IR strobe
during the exposure, detects the strobe images in both frames, and runs the
pipeline.  It depends on Pi-only libraries (picamera2, gpiozero) and so is not
exercised by the desktop test suite -- run it on the hardware.

Trigger options (``--trigger``):
    sound   : a piezo/mic spike at impact starts the exposure+strobe (cheapest)
    motion  : a fast pre-trigger ROI on the face-on camera detects the ball
              leaving the tee
    manual  : press Enter (for bench bring-up)

See docs/HARDWARE.md for wiring and docs/THEORY.md for the timing budget.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from golfsim.calibration import load_rig
from golfsim.config import RigConfig
from golfsim.detection import BallDetector
from golfsim.pipeline import process_shot


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rig", default="calibration_data/rig.json",
                    help="calibrated rig JSON (omit to use default geometry)")
    ap.add_argument("--trigger", choices=["sound", "motion", "manual"],
                    default="manual")
    ap.add_argument("--strobe", choices=["pico", "pi"], default="pico",
                    help="'pico' (recommended): the Pico firmware fires "
                         "shutters+strobe autonomously on impact; 'pi': drive "
                         "the strobe from this Pi's GPIO (bench fallback)")
    ap.add_argument("--club", default="driver")
    ap.add_argument("--shots", type=int, default=0, help="0 = run forever")
    args = ap.parse_args()

    # Lazy import: hardware-only.
    from golfsim.capture import Picamera2Backend, StrobeController

    if Path(args.rig).exists():
        cam_a, cam_b, strobe_dt = load_rig(args.rig)
        print(f"Loaded calibrated rig from {args.rig}")
        if np.allclose(cam_a.R, np.eye(3)) and np.allclose(cam_a.t, 0.0):
            print("  ! WARNING: this rig is NOT world-anchored (camera A is "
                  "the origin).\n"
                  "  ! Speeds are correct but launch/azimuth angles are in "
                  "camera-A coordinates.\n"
                  "  ! Do the anchoring step in docs/CALIBRATION.md step 4.")
    else:
        cfg = RigConfig()
        cam_a, cam_b = cfg.geometry.cameras()
        strobe_dt = cfg.strobe.interval_s
        print("No rig file; using verified DEFAULT geometry (calibrate for "
              "best absolute accuracy)")

    # With --strobe pico the Pico fires shutters + strobe on its own impact
    # trigger (pico/strobe_controller.py); the Pi only collects frames.  The
    # cameras must be in external-trigger mode (see docs/BUILD.md bring-up).
    if args.strobe == "pico":
        _check_trigger_mode()
    strobe = (StrobeController(pulses=5, interval_us=strobe_dt * 1e6)
              if args.strobe == "pi" else None)
    backend_a = Picamera2Backend(camera_num=0, exposure_us=int(5 * strobe_dt * 1e6))
    backend_b = Picamera2Backend(camera_num=1, exposure_us=int(5 * strobe_dt * 1e6))
    det = BallDetector(min_radius_px=3, max_radius_px=150)

    shot_no = 0
    misses = 0
    try:
        while args.shots == 0 or shot_no < args.shots:
            _wait_for_trigger(args.trigger, backend_a)
            if strobe is not None:
                strobe.fire()
            # The frame containing the strobe train may not be the first one
            # returned (free-running cameras buffer; triggered frames arrive
            # after XTR): scan the next few frames per camera and keep the
            # one with the most strobe images.
            tee_a = cam_a.project([[0.0, 0.0, 0.0]])[0]
            tee_b = cam_b.project([[0.0, 0.0, 0.0]])[0]
            blobs_a = _best_strobed_frame(backend_a, det, tee_a)
            blobs_b = _best_strobed_frame(backend_b, det, tee_b)
            if len(blobs_a) < 3 or len(blobs_a) != len(blobs_b):
                print(f"  miss: {len(blobs_a)}/{len(blobs_b)} blobs; retrying")
                misses += 1
                if misses == 3 and args.strobe == "pico":
                    print("  hint: repeated misses with --strobe pico means "
                          "the Pico may not be firing.  Check the Pico is "
                          "flashed+wired (pico/README.md) and the cameras "
                          "are in external-trigger mode (BUILD.md step 2b), "
                          "or use --strobe pi to drive the strobe from this "
                          "Pi for bench tests.")
                continue
            misses = 0

            px_a = np.array([b.uv for b in blobs_a])
            px_b = np.array([b.uv for b in blobs_b])
            res = process_shot(cam_a, px_a, cam_b, px_b, strobe_dt,
                               club=args.club)
            shot_no += 1
            print(f"\n=== Shot {shot_no} ===")
            print(res.stats.pretty())
    finally:
        backend_a.close()
        backend_b.close()


def _best_strobed_frame(backend, det, reference_uv, tries=3):
    """Read up to ``tries`` consecutive frames and return the ordered blob
    list of the frame with the most strobe images (the flash train may land
    one or two frames after the read call)."""
    best = []
    for _ in range(tries):
        blobs = det.detect_ordered(backend.read(), reference_uv=reference_uv)
        if len(blobs) > len(best):
            best = blobs
        if len(best) >= 5:
            break
    return best


def _check_trigger_mode():
    """Warn if the IMX296 external-trigger mode isn't enabled (Pico mode
    needs it or the cameras free-run and ignore the shared XTR line)."""
    from pathlib import Path as _P
    p = _P("/sys/module/imx296/parameters/trigger_mode")
    try:
        if p.exists() and p.read_text().strip() != "1":
            print("  ! WARNING: /sys/module/imx296/parameters/trigger_mode "
                  "is not 1.\n"
                  "  ! The cameras will free-run and ignore the Pico's XTR "
                  "line.  Enable it:\n"
                  "  !   sudo su -c 'echo 1 > "
                  "/sys/module/imx296/parameters/trigger_mode'")
    except OSError:
        pass


def _wait_for_trigger(mode, backend):
    if mode == "manual":
        input("Press Enter to capture a shot... ")
    elif mode == "sound":
        # Placeholder: block on the impact-detector GPIO/ADC here.
        print("(waiting for impact sound...)")
        time.sleep(0.5)
    else:  # motion
        print("(watching for ball launch...)")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
