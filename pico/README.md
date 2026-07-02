# Pico strobe/trigger firmware

`strobe_controller.py` makes a Raspberry Pi Pico the microsecond-accurate
timing conductor for the rig: on a ball strike it opens **both** camera shutters
(one shared XTR line) and fires the IR strobe 5× during that single exposure.

## Why a Pico (not the Pi 5's GPIO)
The flash spacing (1300 µs) and width (12 µs) need tight, jitter-free timing.
A Pico runs this loop bare-metal with nothing else competing; Linux GPIO on the
Pi 5 jitters by milliseconds. The Pi 5 does the vision; the Pico does the clock.

## Flash it
1. Download MicroPython for the Pico (`RPI_PICO` .uf2) from
   https://micropython.org/download/RPI_PICO/
2. Hold **BOOTSEL**, plug the Pico into USB → it mounts as a drive → drop the
   `.uf2` on it. It reboots running MicroPython.
3. Open [Thonny](https://thonny.org/), connect to the Pico, and save
   `strobe_controller.py` onto the Pico **as `main.py`** (so it runs on boot).

## Wiring (matches docs/BUILD.md)
| Pico pin | connects to |
|---|---|
| **GP15** TRIG_IN | impact sensor output (idle low, pulses high on a strike) |
| **GP16** XTR_OUT | both cameras' **XTR** pads, each via a 1.5 kΩ/1.8 kΩ divider (XTR is 1.8 V) |
| **GP17** STROBE | IRLZ44N gate via 220 Ω; 10 kΩ gate→GND pulldown |
| **GP25** | on-board status LED |
| **GND** | common ground with cameras, MOSFET source, and the 12 V supply |

## Bench test before wiring cameras
Jumper **GP15 → 3V3** at power-on to enter **self-test**: the strobe free-runs
~2×/sec with no camera trigger. Point a phone camera at the LED array — phones
see 850 nm, so you can confirm it flashes 5× per burst. Remove the jumper for
normal (strike-triggered) operation.

## Keep in sync with the Pi
`PULSES`, `INTERVAL_US`, and `PULSE_US` here **must equal** `StrobeConfig` in
`golfsim/config.py` (5 / 1300 / 12). The Pi-side pipeline uses `interval_us` as
the timestamp between ball images; if the two disagree, measured speeds scale
wrong. Tune `LAUNCH_DELAY_US` (time from strike to first flash) on the bench so
the first flash catches the ball just clear of the club face.

> Need sub-microsecond determinism? Port `fire_sequence()` to the RP2040 **PIO**
> (a state machine clocks the strobe train independent of the CPU). MicroPython
> `sleep_us` is accurate to a few µs, which is fine here, but PIO is the upgrade
> path if you ever shorten `PULSE_US`.
