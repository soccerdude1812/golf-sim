"""Ball detection in a single camera image.

For the recommended rig the ball is lit by an IR strobe and appears as one or
more bright, near-circular blobs on a dark background.  A single strobed frame
can contain several blobs (one per pulse); an ordinary frame contains one.

The detector returns sub-pixel blob centroids ordered along the dominant line
of travel, which -- because both cameras share the same strobe -- lets us pair
the k-th blob in one camera with the k-th blob in the other.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import cv2
except Exception:                       # pragma: no cover - cv2 optional
    cv2 = None


@dataclass
class Blob:
    u: float                            # sub-pixel column
    v: float                            # sub-pixel row
    radius_px: float
    area_px: float
    brightness: float

    @property
    def uv(self) -> np.ndarray:
        return np.array([self.u, self.v])


@dataclass
class BallDetector:
    """Bright-blob detector tuned for IR-strobed ball images.

    Parameters
    ----------
    min_radius_px, max_radius_px : accepted blob radius range.
    thresh : absolute brightness threshold (0-255).  If None an adaptive
        Otsu-like threshold (mean + k*std) is used.
    background : optional reference frame subtracted before thresholding.
    """
    min_radius_px: float = 3.0
    max_radius_px: float = 120.0
    thresh: float | None = None
    thresh_k: float = 4.0
    background: np.ndarray | None = None

    def _to_gray(self, frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 3:
            if cv2 is not None:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return frame.mean(axis=2)
        return frame

    def detect(self, frame: np.ndarray) -> list[Blob]:
        gray = self._to_gray(frame).astype(np.float32)
        if self.background is not None:
            bg = self._to_gray(self.background).astype(np.float32)
            gray = np.clip(gray - bg, 0, None)

        if self.thresh is not None:
            t = float(self.thresh)
        else:
            t = float(gray.mean() + self.thresh_k * gray.std())
        mask = (gray > t).astype(np.uint8)

        if cv2 is not None:
            return self._detect_cv2(gray, mask)
        return self._detect_numpy(gray, mask)

    # -- OpenCV path (used on the Pi / desktop) -----------------------------
    def _detect_cv2(self, gray: np.ndarray, mask: np.ndarray) -> list[Blob]:
        n, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8)
        blobs: list[Blob] = []
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            radius = 0.25 * (w + h)
            if not (self.min_radius_px <= radius <= self.max_radius_px):
                continue
            # circularity gate: area should fill a decent fraction of bbox.
            if area < 0.45 * w * h:
                continue
            cu, cv_ = self._intensity_centroid(gray, labels, i)
            bright = float(gray[labels == i].mean())
            blobs.append(Blob(cu, cv_, radius, float(area), bright))
        return blobs

    @staticmethod
    def _intensity_centroid(gray, labels, idx):
        ys, xs = np.where(labels == idx)
        w = gray[ys, xs]
        wsum = w.sum()
        if wsum <= 0:
            return float(xs.mean()), float(ys.mean())
        return float((xs * w).sum() / wsum), float((ys * w).sum() / wsum)

    # -- pure-numpy fallback (used in CI / when cv2 absent) -----------------
    def _detect_numpy(self, gray: np.ndarray, mask: np.ndarray) -> list[Blob]:
        labels = _label_numpy(mask)
        blobs: list[Blob] = []
        for idx in range(1, labels.max() + 1):
            ys, xs = np.where(labels == idx)
            if xs.size == 0:
                continue
            w = xs.max() - xs.min() + 1
            h = ys.max() - ys.min() + 1
            radius = 0.25 * (w + h)
            area = xs.size
            if not (self.min_radius_px <= radius <= self.max_radius_px):
                continue
            if area < 0.45 * w * h:
                continue
            wts = gray[ys, xs]
            wsum = wts.sum()
            cu = float((xs * wts).sum() / wsum)
            cv_ = float((ys * wts).sum() / wsum)
            blobs.append(Blob(cu, cv_, radius, float(area),
                              float(wts.mean())))
        return blobs

    def detect_ordered(self, frame: np.ndarray, size_ratio: float = 0.4,
                       line_tol_px: float | None = None,
                       reference_uv=None) -> list[Blob]:
        """Detect blobs, reject spurious ones, and order the surviving ball
        images along their direction of travel.

        Two rejection stages clean up real-world false positives (specular
        highlights off the mat/club, reflections):
          1. *size* -- strobe images of one ball are all about the same size,
             so drop any blob much smaller than the largest.
          2. *collinearity* -- the ball flies in a near-straight line, so its
             strobe images are collinear in the image.  A RANSAC line keeps the
             largest collinear inlier set and discards off-line blobs.

        ``reference_uv`` should be the projected tee/ball-at-rest pixel (from
        the calibrated camera: ``cam.project([[0,0,0]])[0]``).  The ball flies
        AWAY from the tee, so ordering by distance from it gives an
        unambiguous time order.  Without it we fall back to ordering along
        the principal axis, whose direction (sign) is arbitrary -- the
        pipeline then relies on its flies-downrange check to fix a reversed
        track.
        """
        blobs = self.detect(frame)
        if len(blobs) <= 1:
            return blobs
        blobs = self._filter_by_size(blobs, size_ratio)
        if len(blobs) >= 3:
            blobs = self._ransac_line(blobs, line_tol_px)
        pts = np.array([b.uv for b in blobs])
        if reference_uv is not None:
            ref = np.asarray(reference_uv, float)
            order = np.argsort(np.linalg.norm(pts - ref, axis=1))
        else:
            centred = pts - pts.mean(axis=0)
            _, _, vt = np.linalg.svd(centred, full_matrices=False)
            axis = vt[0]
            order = np.argsort(centred @ axis)
        return [blobs[i] for i in order]

    @staticmethod
    def _filter_by_size(blobs: list[Blob], size_ratio: float) -> list[Blob]:
        amax = max(b.area_px for b in blobs)
        return [b for b in blobs if b.area_px >= size_ratio * amax]

    @staticmethod
    def _ransac_line(blobs: list[Blob], tol_px: float | None) -> list[Blob]:
        pts = np.array([b.uv for b in blobs])
        med_r = float(np.median([b.radius_px for b in blobs]))
        tol = tol_px if tol_px is not None else max(2.0, 0.4 * med_r)
        best: list[int] = []
        n = len(blobs)
        for i in range(n):
            for j in range(i + 1, n):
                d = pts[j] - pts[i]
                norm = np.linalg.norm(d)
                if norm < 1e-6:
                    continue
                nrm = np.array([-d[1], d[0]]) / norm   # line normal
                dist = np.abs((pts - pts[i]) @ nrm)
                inliers = list(np.where(dist <= tol)[0])
                if len(inliers) > len(best):
                    best = inliers
        return [blobs[i] for i in best] if len(best) >= 3 else blobs


def _label_numpy(mask: np.ndarray) -> np.ndarray:
    """Tiny 8-connected component labeller (BFS) for the cv2-free fallback."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    cur = 0
    stack: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and labels[y, x] == 0:
                cur += 1
                stack.append((y, x))
                labels[y, x] = cur
                while stack:
                    cy, cx = stack.pop()
                    y0, y1 = max(0, cy - 1), min(h, cy + 2)
                    x0, x1 = max(0, cx - 1), min(w, cx + 2)
                    for ny in range(y0, y1):
                        for nx in range(x0, x1):
                            if mask[ny, nx] and labels[ny, nx] == 0:
                                labels[ny, nx] = cur
                                stack.append((ny, nx))
    return labels
