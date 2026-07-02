"""golfsim -- a two-camera DIY golf launch monitor / simulator.

A calibrated stereo pair of Raspberry Pi Global Shutter cameras, lit by a
synchronised IR strobe, measures the ball's initial 3-D velocity in the first
~1.2 m of flight.  An aerodynamic model then turns that launch (plus spin) into
carry, total distance, apex and the rest of the stat sheet.

Public surface:
    constants        -- units and physical constants
    geometry         -- pinhole camera model + stereo triangulation
    flight_model     -- aerodynamic trajectory simulation
    feasibility      -- "can these cameras track the ball?" calculator
    config           -- rig geometry / camera placement / strobe timing
    detection        -- ball-blob detection
    tracking         -- 3-D track assembly + launch-velocity fit
    launch           -- launch parameters from velocity
    spin             -- spin measurement / estimate
    pipeline         -- process_shot(): the whole chain
    stats            -- ShotStats stat sheet
    synthetic        -- synthetic shots for verification
    capture          -- camera backends + strobe controller
"""

from .constants import mph, ms_from_mph, yards, rpm, rads_from_rpm  # noqa: F401
from .flight_model import LaunchConditions, simulate, FlightResult  # noqa: F401
from .pipeline import process_shot, ShotResult  # noqa: F401

__version__ = "0.1.0"
