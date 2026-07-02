# Camera placement — where to put the two cameras, and why

You asked for "one behind the swing, one facing the person." That instinct is
right for *watching* a swing, but for **measuring ball speed** a pure
down‑the‑line camera has a fatal geometric flaw. This page explains the flaw,
the fix, and gives the exact, code‑verified positions.

All coordinates use the project world frame (metres):

- **X** — down the target line (direction the ball is hit)
- **Y** — lateral; the frame is right‑handed (Y = Z × X), so **+Y points
  LEFT of the target line** — the side a right‑handed golfer stands on. Both
  cameras below sit at *negative* Y, across the ball from the golfer.
  (User‑facing outputs — azimuth, side spin, offline — still follow the golf
  convention "positive = right"; the code flips the sign internally.)
- **Z** — up
- **origin** — the ball at rest on the mat

## Why a *pure* down‑the‑line camera fails for speed

A camera behind the golfer looking straight down the target line sees the ball
flying almost **directly away from it**. The five strobe images of the ball
then land almost on top of each other in the image — they *merge into one
blob*, and you can't measure how far the ball moved.

This isn't hand‑waving; it's computed from the actual code geometry (6 mm
lens, 160 mph ball, 1300 µs strobe interval; camera positions as below, the
down‑the‑line camera at (−1.0, 0, 0.3)). Minimum separation between
consecutive strobe images vs the ball's image size:

| camera aim | min. separation | ball diameter | camera→ball | result |
|------------|----------------:|--------------:|------------:|--------|
| pure down‑the‑line | **45 px** | 61 px | 1.2 m | **images overlap — unusable** |
| behind‑high, angled (default) | 65 px | 33 px | 2.2 m | separated ✓ |
| broadside face‑on (default) | 126 px | 58 px | 1.3 m | separated ✓ |

The governing quantity is **(ball speed × strobe interval) ÷ ball diameter**
*projected onto the camera*. Looking down the flight line collapses that
projection toward zero. Looking *across* the flight line maximises it.

## The fix — both cameras see the ball move *across* their view

We keep your two vantage points but **angle the behind camera off the target
line** so it still sees lateral/vertical motion:

### Camera A — FACE‑ON (side), the primary measurement camera
To the side of the ball, roughly perpendicular to the flight line, slightly
raised and aimed at the launch corridor. The ball crosses its whole field of
view, giving maximum strobe‑image separation. This camera carries **ball speed
and vertical launch angle**.

```
center ≈ (0.20, −1.25, 0.28) m     aim at (0.20, 0.0, 0.06) m
```
(1.25 m to the side, 28 cm high, looking horizontally across the corridor.)

### Camera B — BEHIND‑HIGH (down‑the‑line‑ish), the second stereo view
Behind the golfer and **mounted high — above the top of the backswing**, offset
to the side so its optical axis sits well off the flight line (~27° in plan
view; ~58° in 3‑D once the height is included). The height is a safety
requirement, not just an optical one: a camera behind the golfer at chest
height sits exactly where the club travels at the top of the backswing. It
still frames the swing and resolves **launch direction (push/pull)** while
keeping the strobe images separated enough to triangulate.

```
center ≈ (−1.0, −0.6, 1.85) m    aim at (0.20, 0.0, 0.06) m
```
(1 m behind, 0.6 m to the side, ~1.85 m high — a true 3‑D distance of ~2.2 m
from the corridor — on a tall stand or wall/ceiling bracket, looking down
toward the ball. At 2.2 m the ball is ~33 px across: less resolution than the
face‑on camera, but far above the ≥6 px detection floor, and this camera only
needs to localise the blob centroid, not resolve spin.)

These are the defaults in `golfsim/config.py` and are the geometry every test
runs against. The angle between the two optical axes at the corridor is **66°**
— close to the ideal 90° for well‑conditioned triangulation (the code rejects
near‑parallel geometry that would amplify pixel noise into 3‑D error).

```
       (top view, +X = down range →)
                              net
   golfer ────●──────────────────────  ║
            (ball)   ↘ launch corridor  ║
                       ┊  (first ~0.5 m measured)
        B ╲            ┊
   behind‑high ╲       ┊
                ╲      ┊
                 ╲    ┌┴┐
                  ╲   │ │  A  face‑on (to the side, ~1.25 m)
                      └─┘
```

## Why this still satisfies "behind the swing + facing the player"

- **Camera B** is *behind* the golfer and captures the down‑the‑line swing
  view you wanted — we only raised and angled it so it can also do science.
- **Camera A** faces the player from the side (a face‑on/side view), the
  classic angle for seeing impact and launch.

You keep both human‑useful viewpoints **and** get a geometry that actually
measures the ball.

## Placement checklist for your room

1. Both cameras must see the **first ~0.3–0.5 m of flight** in front of the
   tee (the strobe burst happens here, before the net).
2. Keep the **face‑on camera roughly 1.0–1.4 m** from the corridor with the
   6 mm lens so the ball is ~50–75 px across (it's the primary measurement
   camera). The behind‑high camera can sit farther — the default is ~2.2 m,
   giving a ~33 px ball, still ample for centroiding. All 5 flashes staying
   in frame is verified for 95–183 mph in `tests/test_pipeline_synthetic.py`
   and the feasibility tool.
3. Mount them **rigidly** — any shift after calibration directly biases 3‑D
   positions. Tripods are fine if they don't get bumped between sessions.
4. Aim both at the **same point** (`corridor_center`). The further the two
   optical axes are from parallel (target ~60–90°), the better the depth
   accuracy.
5. Re‑run [`CALIBRATION.md`](CALIBRATION.md) whenever you move a camera.

You can change any of these positions in `RigConfig`; `stereo_angle_deg()`
reports the resulting triangulation conditioning, and the synthetic demo lets
you confirm a new layout recovers a known shot before you trust it.
