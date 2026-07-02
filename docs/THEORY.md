# Theory & measurement method — and why it works in real life

This document is the cross‑check: it walks the full measurement chain, states
the timing/optics budget in numbers, and points at the test that verifies each
step. Nothing here is asserted without either a calculation or a runnable test.

## 1. The core problem and the strobe solution

A golf ball off a driver leaves at **~70 m/s (157 mph)**; tour players reach
**~75 m/s (167 mph)** and long‑drivers **~82 m/s (183 mph)**
([source](https://www.upyourclub.com/driver-ball-speed-chart/)). Two facts
follow:

- At 60 fps the ball moves **~1.2 m between frames** — ordinary video gives you
  *one* image of the ball in the launch zone. Useless for a velocity.
- During even a 4 ms webcam exposure the ball moves **~30 cm** — a giant
  streak, not a point.

Commercial camera monitors solve this with thousands‑of‑fps sensors costing
more than a car. The budget solution, proven by
[PiTrac](https://hackaday.io/project/195042-pitrac-the-diy-golf-launch-monitor),
inverts the problem: **keep the frame rate modest, but light the ball with a
very short, repeated flash.** A global‑shutter camera opens its shutter once;
inside that window an IR LED **strobes 5 times, ~1.3 ms apart, ~12 µs each**.
The result is a single frame holding **5 sharp, time‑stamped ball images**.

Two cameras share one strobe, so flash *k* in camera A is simultaneous with
flash *k* in camera B. That shared timing is the whole trick for pairing.

## 2. Optics & timing budget (the verification)

With the Pi Global Shutter camera (3.45 µm pixels, 1456×1088), a 6 mm lens
(45° HFOV), the face‑on camera ~1.25 m from the ball (the behind‑high camera
sits ~2.2 m out), and a 5‑pulse / 1.3 ms strobe:

| quantity | formula | value @167 mph | requirement | result |
|----------|---------|---------------:|-------------|--------|
| ground sampling | distance ÷ focal_px | 0.72 mm/px | — | — |
| samples per shot | pulses × frames seen | **5** | ≥ 3 for a fit | ✓ |
| travel per pulse | v × interval | 9.7 cm = 135 px | > ball (separable) | ✓ |
| motion blur | v × pulse width | 0.9 mm = **1.2 px** | < ball/3 | ✓ |
| ball size | diameter × focal_px ÷ dist | 59 px | ≥ 6 px | ✓ |
| speed resolution | √2·σ_centroid ÷ baseline | **±0.08 %** | < 1 % | ✓ |

These are produced by `golfsim/feasibility.py` and asserted in
`tests/test_feasibility.py` across 70–183 mph. The same tool shows a 1080p60
webcam failing on samples (~1.5) and blur (~300 px). Full table:
[`FEASIBILITY.md`](FEASIBILITY.md).

**Strobe interval choice.** Images separate when `v × interval > ball
diameter` (projected). With a 42.7 mm ball, 1.3 ms separates everything down to
~95 mph; that's why the default interval is 1300 µs, not the 800 µs you might
naively pick. Distance cancels out of this ratio — moving the camera doesn't
help; the interval does.

## 3. From pixels to a 3‑D track

1. **Detect** (`detection.py`). Threshold the bright strobe blobs, take
   intensity‑weighted sub‑pixel centroids, then reject false positives with a
   **size filter** (specular highlights are tiny) and a **RANSAC line** (the
   real ball images are collinear). Order survivors along the travel axis.
2. **Pair & triangulate** (`tracking.py`, `geometry.py`). Blob *k* in A ↔ blob
   *k* in B (shared strobe). Each pair is triangulated by linear DLT using the
   calibrated projection matrices → a 3‑D point with a known timestamp
   `k × interval`. Reprojection error is reported as a consistency check.
3. **Fit launch velocity** (`tracking.py`). Fit `p(t) = p₀ + v₀t + ½at²` per
   axis by least squares. Using a *constant‑acceleration* model (not constant
   velocity) absorbs gravity and the small aerodynamic deceleration acting over
   the ~5 ms measurement window. `v₀` is the launch velocity.

Verified end‑to‑end in `tests/test_pipeline_synthetic.py`: rendering realistic
frames (noise + spurious blobs) and recovering 160–167 mph shots to **<1 mph,
<0.5°**, with mean reprojection error <1.5 px.

Why the velocity is accurate: over the ~5 ms window the ball decelerates only
~0.1 m/s out of ~75 (drag ≈ 19 m/s² ≈ 2 g at launch). The quadratic fit models
that deceleration explicitly and reports the value *at t₀*, so it isn't a bias.

## 4. Launch parameters (`launch.py`)

From `v₀ = (vx, vy, vz)` in the world frame:

- **ball speed** = ‖v₀‖
- **launch angle** (vertical) = atan2(vz, √(vx²+vy²))
- **launch direction** (push/pull) = atan2(−vy, vx) — the world frame is
  right‑handed (X downrange, Z up) so +Y points *left* of the target line;
  the sign flip reports the golf convention **positive = right**
- **smash factor** = ball speed ÷ clubhead speed *(if clubhead speed is
  measured from the face‑on camera before impact)*

## 5. Spin {#spin}

Spin is the hardest optical measurement on a budget, and the docs say so up
front.

- **Measured** (`spin_from_marker_track`): with a **marked ball** (logo/drawn
  line) the mark's angular advance between strobe images gives spin rate and
  axis directly — the same principle commercial camera monitors and PiTrac
  use. Needs the mark resolved in ≥2 flashes and good IR contrast.
- **Estimated** (`estimate_spin_empirical`): with no trackable mark, backspin
  is estimated from launch angle + ball speed + club type. This is a
  *plausibility estimate, not a measurement*, and every output flags it
  `(estimated)`. Because carry depends strongly on spin, trust carry only when
  spin is measured.

## 6. Ball flight (`flight_model.py`)

Initial conditions feed an RK4 integration of the 3‑D equations of motion:

```
F = −½ρ Cd A |v| v        (drag)
  + ½ρ Cl A |v|² (ŵ × v̂)  (Magnus / lift)
  + (0, 0, −mg)            (gravity)
```

with the conforming‑ball constants (45.93 g, 42.67 mm) and air density
1.225 kg/m³. `Cl` is a smooth saturating function of the spin ratio
`S = rω/|v|`; `Cd` rises with spin and falls with speed (a Reynolds‑number
proxy — a golf ball past the drag crisis has lower Cd at driver speed than at
wedge speed). The five tuning constants are least‑squares fit to the Trackman
tour‑average table on **carry, apex height and descent angle simultaneously**
(a carry‑only fit can still fly the wrong *shape*). Spin decays exponentially
in flight. Outputs: carry, total (optional roll), apex, descent angle, flight
time, landing speed, offline.

Validated against all 14 Trackman PGA/LPGA tour‑average rows in
`tests/test_real_data_validation.py` (run `scripts/validate_real_data.py` for
the full table):

| metric | mean abs. error | worst club |
|--------|----------------:|-----------:|
| carry | 4.1 yd (~2 %) | 8.6 yd |
| apex height | 1.1 yd | 2.4 yd |
| descent angle | 2.1° | 4.6° |

A hold‑out cross‑check (refit with 6 clubs held out) predicts the unseen
clubs with 4.0 yd carry / 1.0 yd apex / 1.5° descent MAE, so the form
generalises rather than memorises — reproduce it yourself with
`scripts/fit_aero.py --holdout`. Driver apex
(~100 ft) matches the tour norm; driver *descent* is the model's weakest
point (42.4° vs the measured 38°), traded off in the fit for accuracy across
the rest of the bag.

## 7. End‑to‑end error budget

| source | effect on ball speed | mitigation |
|--------|----------------------|-----------|
| centroid localisation (~0.3 px) | <0.2 % (5‑sample baseline) | sub‑pixel centroid, more pulses |
| calibration error | scales 3‑D distances | careful chessboard calib, low RMS |
| strobe interval jitter | direct on speed | drive from a stable oscillator/PWM |
| motion blur (1.2 px) | biases centroid slightly | keep pulse ≤ ~15 µs |
| spin (if estimated) | large on **carry**, none on speed | use marked balls |

Ball speed, launch angle and direction are robust. Carry inherits the spin
uncertainty. This is the same accuracy ordering you see quoted for entry‑level
commercial monitors.
