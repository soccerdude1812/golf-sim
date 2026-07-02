"""Physical constants for golf ball flight and the measurement rig.

All SI units unless noted. Sources for the ball constants are the standard
USGA / R&A conforming-ball specification and widely used golf aerodynamics
literature (Bearman & Harvey, Smits & Smith, WSU Sports Science Lab data).
"""

from __future__ import annotations

import math

# --- Golf ball (USGA / R&A conforming maximums) ---------------------------
BALL_MASS_KG: float = 0.04593          # max conforming mass = 45.93 g
BALL_DIAMETER_M: float = 0.042672      # min conforming diameter = 1.680 in
BALL_RADIUS_M: float = BALL_DIAMETER_M / 2.0
BALL_AREA_M2: float = math.pi * BALL_RADIUS_M ** 2   # cross-sectional area

# --- Environment ----------------------------------------------------------
AIR_DENSITY_KGM3: float = 1.225        # ISA sea level, 15 C
GRAVITY_MS2: float = 9.80665

# --- Unit conversions -----------------------------------------------------
MPH_PER_MS: float = 2.2369362921       # 1 m/s in mph
MS_PER_MPH: float = 1.0 / MPH_PER_MS
YARDS_PER_M: float = 1.0936132983
M_PER_YARD: float = 1.0 / YARDS_PER_M
FEET_PER_M: float = 3.280839895
# --- Coordinate convention ------------------------------------------------
# The world frame is right-handed with X down the target line and Z up, so
# +Y points LEFT of the target line.  Golf convention reports lateral
# quantities (azimuth, side spin, offline) positive-RIGHT.  Multiply a
# golf-convention "rightward" value by this to get its world-Y component
# (and vice versa -- the factor is its own inverse).  Every world<->golf
# lateral sign flip in the codebase goes through this constant.
WORLD_Y_PER_GOLF_RIGHT: float = -1.0

RPM_PER_RADS: float = 60.0 / (2.0 * math.pi)
RADS_PER_RPM: float = 1.0 / RPM_PER_RADS
DEG_PER_RAD: float = 180.0 / math.pi
RAD_PER_DEG: float = math.pi / 180.0


def mph(v_ms: float) -> float:
    """m/s -> mph."""
    return v_ms * MPH_PER_MS


def ms_from_mph(v_mph: float) -> float:
    """mph -> m/s."""
    return v_mph * MS_PER_MPH


def yards(d_m: float) -> float:
    """metres -> yards."""
    return d_m * YARDS_PER_M


def rpm(omega_rads: float) -> float:
    """rad/s -> rpm."""
    return omega_rads * RPM_PER_RADS


def rads_from_rpm(v_rpm: float) -> float:
    """rpm -> rad/s."""
    return v_rpm * RADS_PER_RPM
