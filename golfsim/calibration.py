"""Camera calibration: intrinsics from a chessboard and stereo extrinsics,
plus save/load of the calibrated rig.

Real-world workflow
-------------------
1. Print a chessboard (e.g. 9x6 inner corners, known square size) and mount it
   rigidly.  Capture ~15-20 views per camera covering the corridor volume.
2. ``calibrate_intrinsics`` recovers each camera's K and lens distortion.
3. Hold the board so BOTH cameras see it; ``calibrate_stereo`` recovers the
   relative pose, which is then anchored to the world frame (ball = origin,
   X down the target line) with ``set_world_from_board``.

The result is two ``geometry.Camera`` objects expressed in the world frame --
exactly what the pipeline consumes.  Distortion is corrected by undistorting
detected ball pixels before triangulation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .geometry import Camera

try:
    import cv2
except Exception:                       # pragma: no cover
    cv2 = None


@dataclass
class IntrinsicResult:
    K: np.ndarray
    dist: np.ndarray
    rms_px: float
    image_size: tuple


def _object_grid(cols: int, rows: int, square_m: float) -> np.ndarray:
    grid = np.zeros((rows * cols, 3), np.float32)
    grid[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    return grid * square_m


def calibrate_intrinsics(images, pattern=(9, 6), square_m=0.025) -> IntrinsicResult:
    """Recover K and distortion from chessboard ``images`` (gray arrays)."""
    if cv2 is None:
        raise RuntimeError("opencv required for calibration")
    cols, rows = pattern
    objp = _object_grid(cols, rows, square_m)
    objpoints, imgpoints = [], []
    size = None
    for img in images:
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        size = gray.shape[::-1]
        ok, corners = cv2.findChessboardCorners(gray, (cols, rows))
        if not ok:
            continue
        corners = cv2.cornerSubPix(
            gray, corners, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        objpoints.append(objp)
        imgpoints.append(corners)
    if len(objpoints) < 5:
        raise ValueError(f"only {len(objpoints)} usable views; need >=5")
    rms, K, dist, _, _ = cv2.calibrateCamera(objpoints, imgpoints, size,
                                             None, None)
    return IntrinsicResult(K=K, dist=dist.ravel(), rms_px=float(rms),
                           image_size=size)


def calibrate_stereo(images_a, images_b, intr_a: IntrinsicResult,
                     intr_b: IntrinsicResult, pattern=(9, 6),
                     square_m=0.025):
    """Recover the rigid transform (R, T) of camera B relative to camera A
    from synchronized chessboard views.  Returns (R, T, rms)."""
    if cv2 is None:
        raise RuntimeError("opencv required for calibration")
    cols, rows = pattern
    objp = _object_grid(cols, rows, square_m)
    objpoints, ipa, ipb = [], [], []
    for ia, ib in zip(images_a, images_b):
        ga = ia if ia.ndim == 2 else cv2.cvtColor(ia, cv2.COLOR_BGR2GRAY)
        gb = ib if ib.ndim == 2 else cv2.cvtColor(ib, cv2.COLOR_BGR2GRAY)
        oka, ca = cv2.findChessboardCorners(ga, (cols, rows))
        okb, cb = cv2.findChessboardCorners(gb, (cols, rows))
        if not (oka and okb):
            continue
        objpoints.append(objp)
        ipa.append(ca)
        ipb.append(cb)
    if len(objpoints) < 5:
        raise ValueError("need >=5 shared chessboard views for stereo")
    flags = cv2.CALIB_FIX_INTRINSIC
    rms, *_, R, T, _, _ = cv2.stereoCalibrate(
        objpoints, ipa, ipb, intr_a.K, intr_a.dist, intr_b.K, intr_b.dist,
        intr_a.image_size, flags=flags)
    return R, T.ravel(), float(rms)


def set_world_from_board(K_a, dist_a, image_points_a, object_points_world,
                         R_ab, T_ab):
    """Anchor a stereo pair (camera A = reference) to the ball/target world
    frame from ONE view of the chessboard lying on the hitting mat.

    Lay the board flat so its corners have KNOWN world coordinates: e.g. the
    origin corner at the ball position, one edge pointing down the target
    line (+X), Z = 0 on the mat.  Capture a single view from camera A, detect
    the corners, and pass:

    ``image_points_a``       Nx2 detected corner pixels in camera A
    ``object_points_world``  Nx3 corner positions in WORLD metres (same order)
    ``R_ab``, ``T_ab``       the stereo result from ``calibrate_stereo``
                             (pose of camera B relative to camera A)

    solvePnP recovers the world->cameraA pose; composing with the stereo
    transform places camera B too.  Returns (R_a, t_a, R_b, t_b), the
    world->camera transforms to feed ``cameras_from_world_poses``.
    """
    if cv2 is None:
        raise RuntimeError("opencv required for anchoring")
    obj = np.asarray(object_points_world, np.float32).reshape(-1, 3)
    img = np.asarray(image_points_a, np.float32).reshape(-1, 1, 2)
    ok, rvec, tvec = cv2.solvePnP(obj, img, np.asarray(K_a, float),
                                  np.asarray(dist_a, float))
    if not ok:
        raise ValueError("solvePnP failed on the anchoring view")
    R_a, _ = cv2.Rodrigues(rvec)
    t_a = tvec.ravel()
    R_ab = np.asarray(R_ab, float)
    T_ab = np.asarray(T_ab, float).ravel()
    R_b = R_ab @ R_a                  # X_b = R_ab X_a + T_ab, X_a = R_a X_w + t_a
    t_b = R_ab @ t_a + T_ab
    return R_a, t_a, R_b, t_b


def cameras_from_world_poses(K_a, dist_a, R_a, t_a, size_a,
                             K_b, dist_b, R_b, t_b, size_b):
    """Build the two world-frame ``Camera`` objects from explicit world->cam
    rotations/translations (e.g. after anchoring stereo to the ball origin)."""
    a = Camera(K=np.asarray(K_a, float), R=np.asarray(R_a, float),
               t=np.asarray(t_a, float), width=size_a[0], height=size_a[1],
               dist=np.asarray(dist_a, float), name="FaceOn")
    b = Camera(K=np.asarray(K_b, float), R=np.asarray(R_b, float),
               t=np.asarray(t_b, float), width=size_b[0], height=size_b[1],
               dist=np.asarray(dist_b, float), name="BehindHigh")
    return a, b


def save_rig(path: str, cam_a: Camera, cam_b: Camera,
             strobe_interval_s: float) -> None:
    """Persist a calibrated rig to JSON."""
    def cam_dict(c: Camera) -> dict:
        return {"name": c.name, "K": c.K.tolist(), "R": c.R.tolist(),
                "t": c.t.tolist(), "dist": c.dist.tolist(),
                "width": c.width, "height": c.height}
    with open(path, "w") as f:
        json.dump({"cam_a": cam_dict(cam_a), "cam_b": cam_dict(cam_b),
                   "strobe_interval_s": strobe_interval_s}, f, indent=2)


def load_rig(path: str):
    """Load a calibrated rig saved by ``save_rig``."""
    with open(path) as f:
        d = json.load(f)

    def to_cam(cd: dict) -> Camera:
        return Camera(K=np.array(cd["K"]), R=np.array(cd["R"]),
                      t=np.array(cd["t"]), width=cd["width"],
                      height=cd["height"], dist=np.array(cd["dist"]),
                      name=cd["name"])
    return to_cam(d["cam_a"]), to_cam(d["cam_b"]), d["strobe_interval_s"]
