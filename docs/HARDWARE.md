# Hardware — bill of materials (≈ $370, two cameras, < $500)

> For the **definitive, buy-this shopping list + wiring + step-by-step bring-up**,
> see [`BUILD.md`](BUILD.md). This page is the rationale behind the part choices.
> (BUILD.md adds a $5 Raspberry Pi Pico as a deterministic shutter/strobe
> sequencer — preferred over driving the strobe from the Pi's Linux GPIO.)


This is a concrete, buy‑this list for a two‑camera optical launch monitor. It
is modelled on the proven open‑source
[PiTrac](https://hackaday.io/project/195042-pitrac-the-diy-golf-launch-monitor)
design, simplified onto a **single Raspberry Pi 5** (which has *two* MIPI CSI
camera ports, so it drives both cameras without a second computer).

## The cameras (the important part)

We use **two Raspberry Pi Global Shutter cameras (Sony IMX296)**. Three
properties make this sensor the right choice for a fast golf ball, and a
typical webcam the wrong one:

1. **Global shutter.** Every pixel is exposed at the same instant. A
   *rolling*‑shutter webcam exposes row‑by‑row, so a ball crossing the frame
   in a couple of milliseconds is sheared into a diagonal smear — its position
   is ambiguous. Global shutter freezes the ball cleanly.
2. **Short exposure (down to ~30 µs / ~12 µs usable with the strobe).** At a
   12 µs strobe pulse a 167 mph ball moves **0.9 mm ≈ 1.2 px** — effectively
   no motion blur (see [`FEASIBILITY.md`](FEASIBILITY.md)).
3. **External trigger + NIR sensitivity.** The sensor has an external‑trigger
   pin so both cameras and the strobe fire together, and enough 850 nm
   sensitivity to use an *invisible* IR strobe.

| spec | value |
|------|-------|
| sensor | Sony IMX296, 1.58 MP, **global shutter** |
| resolution | 1456 × 1088 |
| pixel pitch | 3.45 µm |
| max frame rate | 60 fps full‑frame (hundreds of fps at small ROI) |
| min exposure | ~30 µs (camera) — strobe pulse sets the effective value |

Sources: Raspberry Pi GS camera product page; Arducam / InnoMaker IMX296
listings; [Tom's Hardware review](https://www.tomshardware.com/reviews/raspberry-pi-global-shutter-camera-review-high-speed-captures).

## Bill of materials

| # | item | qty | ~unit | ~cost | notes |
|---|------|-----|------:|------:|-------|
| 1 | Raspberry Pi 5 (8 GB) | 1 | $80 | **$80** | dual CSI ports drive both cameras |
| 2 | Active cooler for Pi 5 | 1 | $10 | **$10** | sustained CV load |
| 3 | 27 W USB‑C PSU | 1 | $12 | **$12** | official |
| 4 | microSD 64 GB (A2) | 1 | $10 | **$10** | OS + capture buffer |
| 5 | **Raspberry Pi Global Shutter Camera (IMX296)** | **2** | $50 | **$100** | the two cameras |
| 6 | 6 mm CS‑mount lens (≈ 45° HFOV) | 2 | $30 | **$60** | matches the geometry in code; M12 lens kits also fine |
| 7 | Pi 5 camera cable (22‑pin ↔ 15‑pin) | 2 | $4 | **$8** | Pi 5 uses the narrow connector |
| 8 | 850 nm IR LED array (8–12 × 1 W) | 1 | $20 | **$20** | the strobe light |
| 9 | Logic‑level N‑MOSFET (IRLZ44N) + driver parts | 1 | $10 | **$10** | pulses the LEDs from a GPIO |
| 10 | Piezo/mic impact trigger + comparator parts | 1 | $8 | **$8** | starts the exposure at impact (or use software trigger) |
| 11 | Mini tripods / ball‑head mounts | 2 | $15 | **$30** | or 3‑D printed brackets (free) |
| 12 | Protoboard, wiring, connectors | 1 | $15 | **$15** | |
| | | | | **≈ $363** | |

**Total ≈ $363**, leaving ~$140 of the $500 budget for a hitting net, nicer
lenses, or a second Raspberry Pi if you prefer the PiTrac‑style
one‑Pi‑per‑camera split for extra capture headroom.

### Already assumed present (not counted)
- **Hitting net** to stop the ball (you stated you have one). The launch is
  measured in the first ~0.3 m, *before* the net, so the net never occludes
  the measurement.
- **Hitting mat** and **balls**. For optical spin measurement use **marked
  range balls** (a clear logo or a drawn line) — see
  [`THEORY.md`](THEORY.md#spin).

## Lighting & IR notes (read before buying)

- The strobe must be **bright and brief**. The IR LED array is pulsed by the
  MOSFET for ~12 µs, 5 times per exposure, ~1.3 ms apart. Brief high‑current
  pulses keep average power (and eye‑safety margin) low while delivering a lot
  of instantaneous light — that's what freezes the ball.
- **850 nm is invisible** to the golfer but visible to the IMX296. Verify your
  lens passes NIR; some lenses include an IR‑cut coating. If in doubt, the
  monochrome IMX296 variant + an 850 nm band‑pass over the lens gives the best
  ball‑to‑background contrast.
- **Eye safety:** keep total average IR power low (short duty cycle), don't
  stare into the array, and aim it at the hitting zone, not the golfer's face.
  Treat the LED datasheet's exposure limits as hard constraints.

## Compute layout

The Raspberry Pi 5 exposes two camera connectors (`cam0`, `cam1`). `libcamera`
/ `picamera2` can run both IMX296 modules at once. A shared hardware trigger
line (one GPIO → strobe MOSFET, and the strobe sync → both cameras' XTR pins)
guarantees the two cameras see the *same* flashes at the *same* instants,
which is what makes cross‑camera blob pairing trivial and robust.

If you outgrow a single Pi's bandwidth, fall back to the PiTrac arrangement:
two Raspberry Pi units (one per camera) on the same network, each running the
capture/detection half and one aggregating the result — the `golfsim` code is
agnostic to which machine produces the per‑camera blobs.
