"""Camera capture backends and the shot trigger.

Three backends share one tiny interface so the rest of the system never cares
where frames come from:

    * ``Picamera2Backend`` -- the real Raspberry Pi Global Shutter cameras,
      run in external-trigger / short-exposure mode and paired with a GPIO IR
      strobe.  Imported lazily so the package works on a laptop with no Pi libs.
    * ``OpenCVBackend``     -- any UVC / USB camera via cv2.VideoCapture, for
      bench testing.
    * ``FileBackend``       -- replay recorded frames or images.

On the Pi the two cameras and the strobe are driven from a shared hardware
trigger so the N strobe pulses are simultaneous in both cameras; that shared
timing is what makes the k-th blob in camera A correspond to the k-th blob in
camera B (see tracking.build_track).
"""

from __future__ import annotations

import glob
import time
from dataclasses import dataclass
from typing import Iterator, Protocol

import numpy as np

try:
    import cv2
except Exception:                       # pragma: no cover
    cv2 = None


class CaptureBackend(Protocol):
    def read(self) -> np.ndarray: ...
    def close(self) -> None: ...


# --------------------------------------------------------------------------
@dataclass
class StrobeController:
    """Drives the IR LED strobe.  On a Pi this toggles a GPIO; everywhere else
    it is a no-op stub so code paths stay identical.  The MOSFET-driven LED
    array fires ``pulses`` flashes of ``pulse_width_us`` spaced ``interval_us``
    apart, inside one camera exposure window."""
    pulses: int = 5
    interval_us: float = 1300.0         # keep in sync with config.StrobeConfig
    pulse_width_us: float = 12.0
    gpio_pin: int = 18

    def __post_init__(self):
        self._gpio = None
        try:                            # pragma: no cover - hardware only
            from gpiozero import LED
            self._gpio = LED(self.gpio_pin)
        except Exception:
            self._gpio = None

    def fire(self) -> None:             # pragma: no cover - hardware only
        if self._gpio is None:
            return
        for _ in range(self.pulses):
            self._gpio.on()
            _busy_wait_us(self.pulse_width_us)
            self._gpio.off()
            _busy_wait_us(self.interval_us - self.pulse_width_us)


def _busy_wait_us(us: float) -> None:   # pragma: no cover
    end = time.perf_counter() + us * 1e-6
    while time.perf_counter() < end:
        pass


# --------------------------------------------------------------------------
class Picamera2Backend:                 # pragma: no cover - needs a Pi
    """Raspberry Pi Global Shutter camera in short-exposure mode."""

    def __init__(self, camera_num: int = 0, exposure_us: int = 4000,
                 size=(1456, 1088), gain: float = 8.0):
        from picamera2 import Picamera2
        self.picam = Picamera2(camera_num)
        cfg = self.picam.create_still_configuration(
            main={"size": size, "format": "R8"},
            controls={"ExposureTime": exposure_us, "AnalogueGain": gain,
                      "FrameDurationLimits": (exposure_us + 200,
                                              exposure_us + 200)})
        self.picam.configure(cfg)
        self.picam.start()

    def read(self) -> np.ndarray:
        return self.picam.capture_array()

    def close(self) -> None:
        self.picam.stop()


class OpenCVBackend:
    """Any UVC camera; for bench tests, not for fast balls."""

    def __init__(self, index: int = 0, width=1280, height=720, fps=60):
        if cv2 is None:
            raise RuntimeError("opencv not available")
        self.cap = cv2.VideoCapture(index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> np.ndarray:
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("camera read failed")
        return frame

    def close(self) -> None:
        self.cap.release()


class FileBackend:
    """Replay a list of image files or pre-loaded arrays."""

    def __init__(self, frames):
        if isinstance(frames, str):
            paths = sorted(glob.glob(frames))
            if cv2 is None:
                raise RuntimeError("opencv needed to load image files")
            self._frames = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in paths]
        else:
            self._frames = list(frames)
        self._i = 0

    def read(self) -> np.ndarray:
        if self._i >= len(self._frames):
            raise StopIteration
        f = self._frames[self._i]
        self._i += 1
        return f

    def close(self) -> None:
        self._frames = []


def iter_frames(backend: CaptureBackend, n: int) -> Iterator[np.ndarray]:
    for _ in range(n):
        yield backend.read()
