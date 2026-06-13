# golfsim — a two‑camera DIY golf launch monitor & simulator

`golfsim` turns **two sub‑$60 cameras and an IR strobe** into a working golf
launch monitor. A calibrated stereo pair watches the first ~0.3 m of ball
flight, measures the ball's initial 3‑D velocity, and an aerodynamic model
turns that launch (plus spin) into the full stat sheet: **ball speed, launch
angle, launch direction, spin, smash factor, carry, total, apex, descent
angle, flight time and offline**.

The whole rig costs **≈ $380** (full bill of materials in
[`docs/HARDWARE.md`](docs/HARDWARE.md)) — comfortably under the $500 budget,
using a maximum of two cameras.

> **The key idea (and why a cheap webcam can't do this).** A driver launches
> the ball at ~70 m/s (157 mph). At 60 fps that's **1.2 m of travel between
> frames** — you'd get one blurred streak, not a track. Instead of impossible
> "thousands of fps", we copy the approach proven by the open‑source
> [PiTrac](https://hackaday.io/project/195042-pitrac-the-diy-golf-launch-monitor)
> project: a **global‑shutter camera with a short exposure, lit by a
> synchronised IR strobe that pulses 5× per frame.** One frame then contains 5
> sharp, time‑stamped images of the ball. Both cameras share the strobe, so
> the k‑th flash in one camera pairs with the k‑th flash in the other for
> triangulation. The numbers behind this are verified in
> [`docs/FEASIBILITY.md`](docs/FEASIBILITY.md).

## Does it actually work? (verified, not asserted)

Everything in this repo is checked by a runnable test suite. The headline
self‑test renders *what the two real cameras would see* for a shot with known
launch parameters, then runs the real detection → triangulation → fit → flight
pipeline and compares:

```
$ python scripts/run_demo.py --ball-speed 167 --launch 11 --azimuth 1 --spin 2700
Rig: stereo angle 63 deg, strobe 5 pulses @ 1300 us
Detected 5 / 5 strobe images (face-on / behind-high)

================  SHOT  ================
 Ball speed     :  167.0 mph
 Launch angle   :   11.0 deg
 Launch dir     :    1.0 deg R
 Back spin      :   2643 rpm  (estimated)
 Carry          :  270.6 yd
 Apex           :   78.5 ft
 Descent angle  :   38.x deg
 ...
 recovered ball-speed error: 0.01 mph (0.00%)
```

```
$ python -m pytest -q
28 passed
```

- **Ball speed / launch angle / direction**: recovered to <1 mph / <0.5° even
  with image noise and spurious reflections (`tests/test_pipeline_synthetic.py`).
- **Flight model**: reproduces published driver/iron carry distances to within
  ~15 yd (`tests/test_flight_model.py`).
- **Tracking feasibility**: the recommended rig passes at every golf speed; a
  1080p60 webcam provably fails (`tests/test_feasibility.py`).

## Quick start (no hardware needed)

```bash
pip install -r requirements.txt
python -m pytest -q                 # run the verification suite
python scripts/run_demo.py          # synthetic shot through the full pipeline
python scripts/feasibility_report.py# the "can the cameras track it?" numbers
```

## On the real rig

1. Build the hardware — [`docs/HARDWARE.md`](docs/HARDWARE.md).
2. Place the two cameras — [`docs/CAMERA_PLACEMENT.md`](docs/CAMERA_PLACEMENT.md).
3. Calibrate — [`docs/CALIBRATION.md`](docs/CALIBRATION.md):
   `python scripts/calibrate.py <chessboard_dir>`
4. Hit shots — `python scripts/run_live.py --rig calibration_data/rig.json`

## How it works

| stage | module | what it does |
|-------|--------|--------------|
| capture | `golfsim/capture.py` | Pi Global Shutter cameras + IR strobe (or file/synthetic) |
| detect | `golfsim/detection.py` | sub‑pixel bright‑blob detection, size + collinearity rejection |
| triangulate | `golfsim/geometry.py`, `tracking.py` | DLT stereo → timed 3‑D track |
| launch | `golfsim/launch.py` | constant‑accel velocity fit → speed, launch, direction |
| spin | `golfsim/spin.py` | marker‑tracked (measured) or empirical (estimated) |
| flight | `golfsim/flight_model.py` | RK4 with drag + Magnus → carry/total/apex/… |
| report | `golfsim/stats.py` | the stat sheet |

The measurement method, timing budget and error analysis are in
[`docs/THEORY.md`](docs/THEORY.md).

## Honest limitations

- **Spin is the weak point.** Optically measuring spin on a budget needs a
  marked ball and good IR contrast (`spin_from_marker_track`); without a
  trackable mark the system falls back to an *estimate* from launch
  conditions, and clearly labels it as such. Carry depends on spin, so treat
  carry as "good" only when spin is actually measured.
- **Clubhead speed / smash factor** require tracking the club in the face‑on
  camera before impact; supported by the data model but lower accuracy than
  ball speed.
- Results are validated in simulation with realistic camera parameters and
  noise. That proves the maths and the optics budget; a physical build still
  needs the calibration and lighting done well (see the docs).

## Repository layout

```
golfsim/     core library (importable, fully tested)
scripts/     run_demo, feasibility_report, calibrate, run_live
tests/       28 tests: geometry, flight model, feasibility, full pipeline
docs/        HARDWARE, CAMERA_PLACEMENT, THEORY, CALIBRATION, FEASIBILITY
```
