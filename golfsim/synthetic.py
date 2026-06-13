"""Synthetic shot generator for end-to-end verification.

Given known launch conditions this:
  * integrates the true 3-D ball path through the measurement corridor,
  * samples it at the strobe instants,
  * projects those 3-D points into both calibrated cameras,
  * renders IR-strobe-style frames (bright ball disks on a dark background,
    with shot noise, optional motion blur and false specular blobs).

Running detection + triangulation + the launch fit on these frames and
comparing the recovered launch parameters with the known inputs is the core
self-test of the whole pipeline (see tests/test_pipeline_synthetic.py).  It is
"synthetic ground truth": it cannot prove a real lens is sharp, but it does
prove the geometry, pairing, triangulation and velocity maths are correct and
quantifies their noise sensitivity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import BALL_RADIUS_M
from .flight_model import LaunchConditions, _accel
from .geometry import Camera


@dataclass
class SyntheticShot:
    times: np.ndarray                # (N,) strobe times
    points_world: np.ndarray         # (N,3) true 3-D positions
    px_a: np.ndarray                 # (N,2) true projection in camera A
    px_b: np.ndarray                 # (N,2) true projection in camera B
    frames_a: list                   # rendered images (or empty)
    frames_b: list
    launch: LaunchConditions


def _integrate_corridor(launch: LaunchConditions, times: np.ndarray) -> np.ndarray:
    """RK4-integrate the true trajectory and sample it at ``times``."""
    p = np.zeros(3)
    v = launch.velocity_vector()
    omega = launch.spin_vector()
    dt = 1e-4
    out = []
    ti = 0
    t = 0.0
    sample_times = list(times)
    max_t = sample_times[-1] + dt
    # record exactly at sample instants by stepping in fine dt and snapshotting
    next_idx = 0
    while next_idx < len(sample_times) and t <= max_t + dt:
        if t >= sample_times[next_idx] - 1e-9:
            out.append(p.copy())
            next_idx += 1
            continue
        k1 = _accel(v, omega)
        p2 = p + 0.5 * dt * v
        v2 = v + 0.5 * dt * k1
        k2 = _accel(v2, omega)
        p3 = p + 0.5 * dt * v2
        v3 = v + 0.5 * dt * k2
        k3 = _accel(v3, omega)
        p4 = p + dt * v3
        v4 = v + dt * k3
        k4 = _accel(v4, omega)
        p = p + (dt / 6.0) * (v + 2 * v2 + 2 * v3 + v4)
        v = v + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        t += dt
    while len(out) < len(sample_times):
        out.append(p.copy())
    return np.array(out)


def _render(cam: Camera, pixels: np.ndarray, points_world: np.ndarray,
            cam_center: np.ndarray, rng: np.random.Generator,
            noise_sigma: float, false_blobs: int) -> np.ndarray:
    """Render strobed ball disks into a single uint8 frame."""
    img = np.zeros((cam.height, cam.width), dtype=np.float32)
    fpx = cam.K[0, 0]
    for (u, v), Pw in zip(pixels, points_world):
        if not np.isfinite(u):
            continue
        depth = np.linalg.norm(Pw - cam_center)
        r = max(2.0, BALL_RADIUS_M * fpx / max(depth, 1e-3))
        _draw_disk(img, u, v, r, 230.0)
    # background shot noise + a few spurious specular highlights
    img += rng.normal(0, noise_sigma, img.shape)
    for _ in range(false_blobs):
        fu = rng.uniform(0, cam.width)
        fv = rng.uniform(0, cam.height)
        _draw_disk(img, fu, fv, rng.uniform(2, 4), rng.uniform(60, 120))
    return np.clip(img, 0, 255).astype(np.uint8)


def _draw_disk(img, cu, cv, r, value):
    h, w = img.shape
    x0, x1 = int(max(0, cu - r - 1)), int(min(w, cu + r + 2))
    y0, y1 = int(max(0, cv - r - 1)), int(min(h, cv + r + 2))
    if x0 >= x1 or y0 >= y1:
        return
    ys, xs = np.mgrid[y0:y1, x0:x1]
    d2 = (xs - cu) ** 2 + (ys - cv) ** 2
    # soft-edged disk for sub-pixel-friendly centroids
    edge = np.clip(r - np.sqrt(d2) + 0.5, 0, 1)
    img[y0:y1, x0:x1] = np.maximum(img[y0:y1, x0:x1], value * edge)


def generate_shot(cam_a: Camera, cam_b: Camera, launch: LaunchConditions,
                  strobe_interval_s: float, n_pulses: int = 5,
                  render: bool = True, noise_sigma: float = 2.0,
                  false_blobs: int = 3, pixel_jitter_px: float = 0.0,
                  seed: int = 0) -> SyntheticShot:
    """Produce a synthetic shot observed by the two cameras.

    ``pixel_jitter_px`` adds Gaussian noise to the *true* projected pixel
    coordinates -- use it (with render=False) to probe how detector
    localisation error propagates to launch-parameter error without paying the
    cost of rendering + re-detecting.
    """
    rng = np.random.default_rng(seed)
    times = np.arange(n_pulses) * strobe_interval_s
    pts = _integrate_corridor(launch, times)

    px_a = cam_a.project(pts)
    px_b = cam_b.project(pts)
    if pixel_jitter_px > 0:
        px_a = px_a + rng.normal(0, pixel_jitter_px, px_a.shape)
        px_b = px_b + rng.normal(0, pixel_jitter_px, px_b.shape)

    frames_a, frames_b = [], []
    if render:
        # one strobed frame per camera containing all pulse positions
        frames_a.append(_render(cam_a, px_a, pts, cam_a.center, rng,
                                noise_sigma, false_blobs))
        frames_b.append(_render(cam_b, px_b, pts, cam_b.center, rng,
                                noise_sigma, false_blobs))

    return SyntheticShot(times=times, points_world=pts, px_a=px_a, px_b=px_b,
                         frames_a=frames_a, frames_b=frames_b, launch=launch)
