# Build guide — exactly what to buy and how to set it up

This is the complete hardware shopping list and physical build for the
two-camera launch monitor. Everything here matches the geometry and timing the
software already expects (`golfsim/config.py`), and the whole thing comes in
**≈ $370**, under the $500 / two-camera budget.

> Design in one sentence: two hardware-synchronised global-shutter cameras stare
> at the first ~0.3 m of ball flight; a microcontroller fires both shutters and
> a 5-pulse IR strobe at the same instant, so each frame holds 5 sharp,
> time-stamped ball images that triangulate to a 3-D launch.

---

## 1. Shopping list (buy exactly this)

### Core compute & cameras
| # | Item | Qty | ~$ ea | ~$ | Why / notes |
|---|------|----:|------:|---:|-------------|
| 1 | **Raspberry Pi 5 (8 GB)** | 1 | 80 | 80 | Has **two** 22-pin CSI ports → drives both cameras, no 2nd Pi needed |
| 2 | Active Cooler for Pi 5 | 1 | 7 | 7 | sustained vision load |
| 3 | Official 27 W USB-C PSU | 1 | 12 | 12 | Pi 5 needs the 5 A supply |
| 4 | microSD 64 GB A2 | 1 | 9 | 9 | OS + capture buffer |
| 5 | **Raspberry Pi Global Shutter Camera (IMX296)** | **2** | 50 | 100 | the two cameras — global shutter is mandatory |
| 6 | **Raspberry Pi 6 mm CS-mount lens** | 2 | 25 | 50 | GS camera ships **without** a lens; 6 mm ≈ 45° HFOV matches the code |
| 7 | Pi 5 camera cable, **22-pin → 15-pin**, 300 mm | 2 | 6 | 13 | Pi 5 port is 22-pin; camera is 15-pin. Adafruit 5819 / equiv. |

### Lighting, timing & trigger (the "strobe brain")
| # | Item | Qty | ~$ ea | ~$ | Why / notes |
|---|------|----:|------:|---:|-------------|
| 8 | **Raspberry Pi Pico** (or Pico H) | 1 | 5 | 5 | deterministic PIO timing for shutter + strobe (Linux GPIO jitters) |
| 9 | **850 nm IR LED array** (≥ 8 × 1 W, with heatsink) | 1 | 25 | 25 | the strobe light; 850 nm is invisible to the golfer, visible to IMX296 |
| 10 | 12 V 2 A power supply (for the LED array) | 1 | 9 | 9 | LEDs run off 12 V in series strings |
| 11 | Logic-level N-MOSFET **IRLZ44N** (+1 spare) | 2 | 1.5 | 3 | switches the LED array from a Pico pin |
| 12 | Piezo impact sensor **or** electret mic module | 1 | 4 | 4 | starts the capture at the strike |
| 13 | Resistors/proto/level-shift kit (1.5 kΩ, 1.8 kΩ, 220 Ω, perfboard) | 1 | 8 | 8 | XTR is 1.8 V → needs a divider; gate resistor; LED current limits |
| 14 | Dupont/JST jumper wires | 1 | 8 | 8 | wiring |

### Mounting
| # | Item | Qty | ~$ ea | ~$ | Why / notes |
|---|------|----:|------:|---:|-------------|
| 15 | Mini tripod or ball-head camera mount | 2 | 12 | 24 | rigid, repeatable aiming (or 3-D print brackets, free) |

**Subtotal ≈ $370.** Leaves ~$130 of the $500 budget.

### Optional but recommended
- **2× 850 nm band-pass filter** (CS-thread or stick-on, ~$10 ea). Makes the
  strobe images pop against room light — strongly recommended if you can't dim
  the room. Without it, hit in moderate/low ambient light.
- **Marked range balls** (or just draw a bold dot/line with a Sharpie). Needed
  if you want *measured* spin rather than estimated.
- A second Raspberry Pi 5 (~$80) if you later want the PiTrac-style
  one-Pi-per-camera split for more capture headroom. **Not needed to start.**

### Already assumed present (not in budget)
- **Hitting net** (you have one), **mat**, **balls**. The measurement happens
  in the first ~0.3 m *before* the net, so the net never blocks it.

---

## 2. Physical layout (positions are exact — they match the code)

World frame: ball at rest = origin; **+X** down the target line; **+Z** up;
units metres. These are the defaults in `golfsim/config.py`, already verified to
keep all 5 strobe images in-frame and separated from 95→183 mph.

```
TOP VIEW                                   SIDE VIEW (looking along -Y)
   +X (target) →                              +Z
                                               │   ◯ ← ball flight (first ~0.3 m)
  ●ball ··· launch corridor ···  ║net          │  ◯
   │            ↑ both cams aim here            │ ◯        ┌─┐ B (behind-high, ~1 m up)
   │         (0.20, 0, 0.06)                    │◯  ●ball  └─┘
   │                                            └──────────────── +X
   B  ╲                          A
behind-high╲                   face-on (side)
   (-0.75,-0.50,1.05)         (0.20,-1.25,0.28)
```

- **Camera A — FACE-ON (side):** centre **(0.20, −1.25, 0.28) m**, aimed at
  **(0.20, 0, 0.06)**. ~1.25 m to the side, 28 cm high, looking horizontally
  across the ball line. This is the primary speed/launch-angle camera.
- **Camera B — BEHIND-HIGH:** centre **(−0.75, −0.50, 1.05) m**, same aim point.
  ~0.75 m behind, 0.5 m to the side, ~1 m up, looking down toward the ball.
  Resolves push/pull and frames the swing.

Translate to your room: put a tee at the origin, point +X at the net, measure
the two camera centres with a tape, and aim both at a marker ~20 cm in front of
the tee, ~6 cm off the mat. Why **not** straight down the line:
[`CAMERA_PLACEMENT.md`](CAMERA_PLACEMENT.md). Mount everything **rigidly** —
post-calibration movement = measurement error.

---

## 3. Wiring

### 3a. Cameras → Pi 5
- Camera A → Pi 5 port **CAM0**, Camera B → **CAM1**, via the 22→15-pin cables.
- Keep cables away from the 12 V LED wiring (noise).

### 3b. Strobe power stage
```
12V (+) ──[ IR LED array ]──┬── Drain (IRLZ44N)
                            │
                       Source ── GND (common with Pico GND and 12V GND)
Pico GPIO (strobe) ──[220Ω]── Gate
                       Gate ──[10kΩ]── GND   (pulldown so it can't float on)
```
Size the LED strings/series resistors for the array's forward voltage at your
pulse current per its datasheet. Brief 12 µs pulses keep average power (and
eye-safety margin) low.

### 3c. Camera external trigger (XTR) — hardware sync
Both cameras expose **only when the Pico tells them to**, at the same instant.
Per the [Raspberry Pi GS external-trigger docs](https://www.raspberrypi.com/documentation/accessories/camera.html#external-trigger-on-the-global-shutter-camera):
- Solder a wire to each camera's **XTR** and **GND** pads.
- XTR is a **1.8 V** input → feed it through a divider from the Pico's 3.3 V pin:
  `Pico GPIO ──[1.5kΩ]── XTR ──[1.8kΩ]── GND` (per camera).
- One Pico "shutter" pin drives **both** cameras' XTR (through their own
  dividers) so they start together. Exposure length = the low-pulse width.
- ⚠️ If your camera board has transistor **Q2** fitted, **remove R11** on that
  board or external-trigger mode won't engage (noted in the RPi docs).

### 3d. Impact trigger → Pico
- Piezo disc taped near the mat (or electret mic module) → a Pico input pin.
- A strike spikes the input; the Pico debounces and starts the capture sequence.

---

## 4. What the Pico does (the timing sequence)

The Pico is the real-time sequencer; the Pi 5 just grabs and processes frames.
On each detected strike:

```
1. (impact spike on input pin)
2. assert XTR low on BOTH cameras  ──► exposure window opens (~8 ms)
3. inside that window, pulse the strobe MOSFET 5×:
       12 µs ON, then 1300 µs gap   (matches StrobeConfig in the code)
4. release XTR  ──► both cameras read out one frame each,
                    each containing the same 5 ball positions
5. Pi 5 pulls both frames over CSI and runs the pipeline
```

Because both shutters and the strobe share one clock, flash *k* in camera A is
simultaneous with flash *k* in camera B — which is exactly the assumption
`tracking.build_track()` relies on to pair them. Strobe interval/pulse count
live in `golfsim/config.py` (`StrobeConfig`) — keep the Pico firmware and that
config in step.

---

## 5. Software bring-up (on the Pi 5)

```bash
# 1. Flash Raspberry Pi OS (64-bit, Bookworm) to the microSD, boot, update
sudo apt update && sudo apt full-upgrade -y

# 2. Both IMX296 cameras should enumerate (after wiring):
rpicam-hello --list-cameras        # expect cam0 and cam1, both imx296

# 3. Get the code + deps
git clone <your-fork-or-this-repo> golf-sim && cd golf-sim
sudo apt install -y python3-picamera2 python3-opencv python3-numpy
pip install -e .                   # or: pip install -r requirements.txt

# 4. Sanity check the math with no hardware:
python scripts/run_demo.py
python -m pytest -q                # 45 tests should pass

# 5. Calibrate the rig (chessboard) -> calibration_data/rig.json
python scripts/calibrate.py calib --pattern 9x6 --square 0.025
#    (full workflow: docs/CALIBRATION.md)

# 6. Go live:
python scripts/run_live.py --rig calibration_data/rig.json --trigger sound
```

Flash the Pico with the strobe/trigger firmware (a short PIO/MicroPython
program implementing §4 — pin assignments to match your wiring). You can start
with `--trigger manual` and a bench LED to confirm the capture+detect path
before wiring the impact sensor.

---

## 6. Bring-up checklist (do these in order)

1. **Cameras enumerate** — `rpicam-hello --list-cameras` shows two imx296.
2. **Focus & frame** — with the room lit, `rpicam-still` from each; adjust each
   lens so a ball on the mat is sharp and both cameras see the corridor.
3. **Strobe fires** — scope or phone-camera (phones see 850 nm) the LED array;
   confirm 5 pulses per trigger.
4. **External trigger works** — frames only appear when the Pico pulses XTR;
   exposure tracks the pulse width.
5. **Dark-frame test** — in shooting light, a strobed frame shows bright ball
   blobs on a near-black background (add the band-pass filter if it's washed out).
6. **Detection** — `BallDetector` finds 5 blobs in each camera for a rolled/tossed
   ball; counts match across cameras.
7. **Calibrate** — intrinsic RMS < ~0.5 px, stereo RMS < ~1 px.
8. **First real shot** — numbers land in a sane range; reprojection error < ~1.5 px.

---

## 7. Two honest gotchas

- **Ambient light vs the strobe.** The sensor integrates the whole ~8 ms window,
  so bright room light can swamp the 12 µs flashes. Fixes, cheapest first: dim
  the room → add the 850 nm band-pass filters → shorten the exposure window.
- **Spin needs a marked ball.** Without a trackable mark the system *estimates*
  spin (and flags it). Draw a bold dot/line on the ball for measured spin; carry
  accuracy depends on it.
