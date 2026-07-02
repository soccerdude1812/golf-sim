"""strobe_controller.py -- Raspberry Pi Pico firmware for the golfsim rig.

The Pico is the real-time "conductor": on a detected ball strike it opens both
camera shutters (one shared external-trigger line) and fires the IR strobe a
fixed number of times during that single exposure.  Because both cameras see
the exact same flashes at the exact same instants, flash k in camera A pairs
with flash k in camera B -- the assumption golfsim.tracking.build_track relies
on.

THESE CONSTANTS MUST MATCH golfsim/config.py (StrobeConfig):
    pulses_per_frame = 5
    interval_us      = 1300
    pulse_width_us   = 12
If you change them here, change them there too (and recalibrate timing).

Wiring (see docs/BUILD.md):
    GP15  TRIG_IN   <- impact sensor (piezo/mic comparator), idle low, pulses high
    GP16  XTR_OUT   -> both cameras' XTR pads, EACH via a 1.5k/1.8k divider to 1.8V
    GP17  STROBE    -> IRLZ44N gate (via 220R), 10k gate->GND pulldown
    GP25  on-board LED = status

Flash: hold BOOTSEL, plug in USB, copy a MicroPython .uf2, then save this file
as main.py on the Pico (e.g. with Thonny).  See pico/README.md.
"""

from machine import Pin
import time

# ---- timing (keep in sync with golfsim/config.py) -----------------------
PULSES = 5
INTERVAL_US = 1300       # spacing between flashes
PULSE_US = 12            # flash on-time (sets motion blur; keep small)

# Delay from strike detection to the first flash, so the ball has left the
# club face and is in clear air (~0.05 m out at wedge speed, ~0.12 m at tour
# driver speed).  Tune on the bench.
LAUNCH_DELAY_US = 1500

# Exposure window = a little padding around the whole strobe train.
EXPOSURE_PAD_US = 400
EXPOSURE_US = LAUNCH_DELAY_US + (PULSES - 1) * INTERVAL_US + PULSE_US + EXPOSURE_PAD_US

REARM_MS = 400           # ignore further triggers for this long after a shot

# ---- pins ---------------------------------------------------------------
trig = Pin(15, Pin.IN, Pin.PULL_DOWN)
xtr = Pin(16, Pin.OUT, value=1)      # XTR idle HIGH; exposure happens on LOW
strobe = Pin(17, Pin.OUT, value=0)
status = Pin(25, Pin.OUT, value=0)


def fire_sequence():
    """One shot: open both shutters and fire the strobe train.

    The XTR low time (= sensor exposure) is exactly EXPOSURE_US: launch
    delay + 4 full intervals + the last 12 us pulse + the padding.  No
    trailing full-interval sleep after the final flash -- that would
    silently stretch the exposure (and the ambient-light integration) by
    another ~1.3 ms beyond the printed figure.
    """
    status.on()
    xtr.low()                         # both cameras begin exposing
    time.sleep_us(LAUNCH_DELAY_US)    # let the ball get clear of the club
    for k in range(PULSES):
        strobe.high()
        time.sleep_us(PULSE_US)
        strobe.low()
        if k < PULSES - 1:
            time.sleep_us(INTERVAL_US - PULSE_US)
    time.sleep_us(EXPOSURE_PAD_US)
    xtr.high()                        # end exposure -> cameras read out
    status.off()


def self_test():
    """Free-run the strobe ~2x/sec with NO camera trigger -- bench check that
    the LED array flashes 5x (view with a phone camera; it sees 850 nm)."""
    while True:
        for _ in range(PULSES):
            strobe.high(); time.sleep_us(PULSE_US)
            strobe.low(); time.sleep_us(INTERVAL_US - PULSE_US)
        status.toggle()
        time.sleep_ms(500)


def main():
    # Hold TRIG high at boot to enter self-test (e.g. jumper GP15->3V3).
    if trig.value():
        self_test()
        return
    print("golfsim strobe controller ready; exposure window =", EXPOSURE_US, "us")
    while True:
        if trig.value():                      # rising edge = strike
            fire_sequence()
            time.sleep_ms(REARM_MS)            # debounce / re-arm
        time.sleep_us(50)


if __name__ == "__main__":
    main()
