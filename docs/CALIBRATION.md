# Calibration

Triangulation is only as good as the camera calibration. This is the one step
where care directly buys accuracy: a 1 % error in the calibrated camera
geometry is a 1 % error in ball speed and distance.

You need two things:
1. **Intrinsics** per camera — focal length, principal point, lens distortion.
2. **Extrinsics** — where each camera sits in the world frame (ball = origin,
   X down the target line).

## What you need

- A printed **chessboard**, e.g. 9×6 *inner* corners, glued flat to stiff
  board. Measure one square precisely (e.g. 25.0 mm) — this sets your scale.
- Good, even lighting (visible light is fine for calibration; the IR strobe is
  only for shots).

## Step 1 — intrinsics (per camera)

Capture ~15–20 stills of the chessboard per camera, tilted and shifted to fill
the frame and the corners. Put them in:

```
calib/cam_a/*.png      # face-on (side) camera
calib/cam_b/*.png      # behind-high camera
```

## Step 2 — stereo extrinsics

Hold the board so **both** cameras see it at once; capture ~15 synchronized
pairs across the corridor volume:

```
calib/stereo/a_000.png  calib/stereo/b_000.png
calib/stereo/a_001.png  calib/stereo/b_001.png
...
```
(Sorted filenames are paired, so name them consistently.)

## Step 3 — run it

```bash
python scripts/calibrate.py calib --pattern 9x6 --square 0.025 \
       --out calibration_data/rig.json
```

This recovers each camera's `K`/distortion and the **relative** pose of camera
B w.r.t. camera A, then writes `rig.json`. Check the printed RMS values:

- intrinsic RMS **< ~0.5 px** is good.
- stereo RMS **< ~1 px** is good. If higher, recapture with sharper, more
  varied board views.

## Step 4 — anchor to the world frame (ball = origin)

`stereoCalibrate` gives geometry *relative to camera A*. To get **absolute**
launch angles and a sensible target line you anchor it to the room:

1. Lay the chessboard flat on the hitting mat with a known corner at the ball
   position and one edge along the target line (so each corner has known
   world coordinates, Z = 0 on the mat).
2. Capture one view from camera A and detect the corners
   (`cv2.findChessboardCorners`).
3. Call `golfsim.calibration.set_world_from_board(K_a, dist_a, corners,
   corner_world_positions, R, T)` — it solvePnPs camera A's world pose and
   composes the stereo result — then `cameras_from_world_poses(...)` +
   `save_rig(...)`.

Until you do this, `run_live.py` prints a warning: an un-anchored rig
measures ball *speed* correctly but reports launch/azimuth angles in camera
A's coordinates, not relative to the target line.

## Shortcut — use the verified default geometry

For a first light / bench test you don't strictly need calibration: the
`RigConfig` defaults in `golfsim/config.py` are a fully specified, test‑verified
geometry. If you physically place the cameras at those coordinates
(±a centimetre), the synthetic‑validated pipeline will already give sensible
numbers. Calibrate when you want best absolute accuracy or move a camera.

```python
from golfsim.config import RigConfig
cam_a, cam_b = RigConfig().geometry.cameras()   # no calibration files needed
```

## Keeping calibration valid

- **Don't move the cameras** after calibrating. Bumped tripod → recalibrate.
- Re‑check monthly or after transport with a single chessboard pair and the
  reported reprojection error.
- Temperature/focus drift on cheap lenses is real; if speeds look off by a
  consistent few percent, recalibrate before blaming the algorithm.
