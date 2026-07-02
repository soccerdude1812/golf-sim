"""Aerodynamic golf-ball flight simulation.

Given the launch conditions (ball speed, launch angle, azimuth, back/side
spin) this integrates the 3-D equations of motion including gravity, drag and
the Magnus (lift) force, and reports carry, total distance, apex, descent
angle and flight time.

Forces
------
    F_drag  = -0.5 * rho * Cd * A * |v| * v
    F_magnus=  0.5 * rho * Cl * A * |v|^2 * (w_hat x v_hat)
    F_grav  =  (0, 0, -m g)

Cl is a function of the spin ratio S = r*omega / |v|; Cd depends on both S
and (through a Reynolds-number proxy) on speed -- a golf ball past the drag
crisis has lower Cd at driver speed than at wedge speed.  The functional
forms are smooth empirical fits; the five tuning constants are calibrated
against the Trackman PGA/LPGA tour-average table (carry, apex height AND
descent angle simultaneously -- see tests/test_real_data_validation.py).
They can be re-fit against your own measured data.

Coordinate convention: world frame is right-handed with X down the target
line and Z up, so +Y points LEFT of the target line.  All user-facing signed
quantities (azimuth_deg, side_spin_rpm, offline_m) follow the golf/launch-
monitor convention "positive = right of the target line"; the mapping to the
world frame (a minus sign on Y) happens inside this module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import (
    AIR_DENSITY_KGM3, BALL_AREA_M2, BALL_MASS_KG, BALL_RADIUS_M, GRAVITY_MS2,
    RAD_PER_DEG, WORLD_Y_PER_GOLF_RIGHT, YARDS_PER_M, rads_from_rpm,
)

# Empirical aerodynamic coefficient model -- least-squares fit to the
# Trackman PGA/LPGA tour-average table (carry + apex + descent angle for 14
# clubs, tests/test_real_data_validation.py).  Golf balls operate past the
# drag crisis, where Cd falls slowly with Reynolds number (speed) and rises
# with spin; Cl saturates with spin (Magnus force).
_CD0 = 0.0673         # base drag coefficient
_CD_SPIN = 0.1314     # extra drag induced by spin (spin ratio S)
_CD_RE = 0.1887       # Reynolds-proxy term: scales with (_V_REF / speed)
_V_REF = 40.0         # m/s reference speed for the Reynolds proxy
_CD_MAX = 0.50        # sub-critical sphere Cd (below the drag crisis).  The
                      # tour-data fit only covers ~45-82 m/s; below ~17 m/s
                      # the cap governs, so short-game (chip/putt) carry is
                      # physically plausible but not Trackman-validated.
_CL_GAIN = 0.4360     # lift gain
_CL_HALF = 0.1793     # spin ratio at half-max lift


def drag_coefficient(spin_ratio: float, speed_ms: float = _V_REF) -> float:
    cd = _CD0 + _CD_SPIN * spin_ratio + _CD_RE * (_V_REF / max(speed_ms, 1.0))
    return min(cd, _CD_MAX)


def lift_coefficient(spin_ratio: float) -> float:
    s = max(spin_ratio, 0.0)
    return _CL_GAIN * s / (_CL_HALF + s)


@dataclass
class LaunchConditions:
    """Initial conditions at the moment the ball leaves the club face."""
    ball_speed_ms: float
    launch_angle_deg: float        # vertical, above horizontal
    azimuth_deg: float = 0.0       # +right (push), -left (pull) of target line
    back_spin_rpm: float = 2500.0
    side_spin_rpm: float = 0.0     # + curves ball right (fade/slice), - left

    def velocity_vector(self) -> np.ndarray:
        """World-frame velocity.  +Y points LEFT of the target line (right-
        handed frame), so a positive (rightward) azimuth maps to -Y."""
        el = self.launch_angle_deg * RAD_PER_DEG
        az = self.azimuth_deg * RAD_PER_DEG
        v = self.ball_speed_ms
        vx = v * np.cos(el) * np.cos(az)
        vy = WORLD_Y_PER_GOLF_RIGHT * v * np.cos(el) * np.sin(az)
        vz = v * np.sin(el)
        return np.array([vx, vy, vz])

    def spin_vector(self) -> np.ndarray:
        """Spin angular-velocity vector (rad/s) in the world frame.

        Pure backspin lifts the ball: the spin axis points along -Y so that
        (w x v) has a +Z (upward) component for a ball travelling +X.
        Positive side spin (fade) tilts the axis toward -Z: the Magnus force
        (-Z x +X = -Y) then pushes the ball right of the target line.
        """
        back = rads_from_rpm(self.back_spin_rpm)
        side = rads_from_rpm(self.side_spin_rpm)
        return np.array([0.0, -back, WORLD_Y_PER_GOLF_RIGHT * side])


@dataclass
class FlightResult:
    carry_m: float
    total_m: float
    apex_m: float
    flight_time_s: float
    descent_angle_deg: float
    landing_speed_ms: float
    offline_m: float               # lateral deviation at landing (+right)
    trajectory: np.ndarray         # (N,3) sampled positions, world frame

    @property
    def carry_yards(self) -> float:
        return self.carry_m * YARDS_PER_M

    @property
    def total_yards(self) -> float:
        return self.total_m * YARDS_PER_M

    @property
    def apex_yards(self) -> float:
        return self.apex_m * YARDS_PER_M

    @property
    def offline_yards(self) -> float:
        return self.offline_m * YARDS_PER_M


def _accel(v: np.ndarray, omega: np.ndarray) -> np.ndarray:
    speed = np.linalg.norm(v)
    if speed < 1e-6:
        return np.array([0.0, 0.0, -GRAVITY_MS2])
    spin_mag = np.linalg.norm(omega)
    spin_ratio = (BALL_RADIUS_M * spin_mag) / speed if spin_mag > 0 else 0.0

    cd = drag_coefficient(spin_ratio, speed)
    cl = lift_coefficient(spin_ratio)

    q = 0.5 * AIR_DENSITY_KGM3 * BALL_AREA_M2   # dynamic-pressure prefactor
    v_hat = v / speed

    f_drag = -q * cd * speed * v          # = -q Cd |v| v
    # Magnus direction: omega_hat x v_hat, magnitude q Cl |v|^2
    if spin_mag > 0:
        magnus_dir = np.cross(omega / spin_mag, v_hat)
        f_magnus = q * cl * speed ** 2 * magnus_dir
    else:
        f_magnus = np.zeros(3)

    f_grav = np.array([0.0, 0.0, -BALL_MASS_KG * GRAVITY_MS2])
    return (f_drag + f_magnus + f_grav) / BALL_MASS_KG


def simulate(launch: LaunchConditions, dt: float = 0.002,
             spin_decay_s: float = 25.0, max_time: float = 15.0,
             roll_factor: float = 0.0) -> FlightResult:
    """Integrate the trajectory with RK4 until the ball returns to ground.

    ``spin_decay_s`` is the exponential time constant for spin decay in flight.
    ``roll_factor`` adds a crude roll-out (fraction of carry) to estimate total
    distance; for a launch-monitor we mostly care about carry so it defaults
    to 0 and total==carry unless set.
    """
    p = np.array([0.0, 0.0, 0.0])
    v = launch.velocity_vector()
    omega0 = launch.spin_vector()

    traj = [p.copy()]
    t = 0.0
    apex = 0.0
    prev_p = p.copy()
    prev_v = v.copy()

    while t < max_time:
        decay = np.exp(-t / spin_decay_s)
        omega = omega0 * decay

        def deriv(pp, vv):
            return vv, _accel(vv, omega)

        k1p, k1v = deriv(p, v)
        k2p, k2v = deriv(p + 0.5 * dt * k1p, v + 0.5 * dt * k1v)
        k3p, k3v = deriv(p + 0.5 * dt * k2p, v + 0.5 * dt * k2v)
        k4p, k4v = deriv(p + dt * k3p, v + dt * k3v)

        prev_p = p.copy()
        prev_v = v.copy()
        p = p + (dt / 6.0) * (k1p + 2 * k2p + 2 * k3p + k4p)
        v = v + (dt / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)
        t += dt
        apex = max(apex, p[2])
        traj.append(p.copy())

        if p[2] <= 0.0 and v[2] < 0.0:
            # Linear interpolate the ground crossing between prev_p and p.
            frac = prev_p[2] / (prev_p[2] - p[2])
            ground = prev_p + frac * (p - prev_p)
            v_land = prev_v + frac * (v - prev_v)
            traj[-1] = ground
            carry = float(ground[0])
            offline = float(WORLD_Y_PER_GOLF_RIGHT * ground[1])
            land_speed = float(np.linalg.norm(v_land))
            horiz = float(np.hypot(v_land[0], v_land[1]))
            descent = float(np.degrees(np.arctan2(-v_land[2], horiz)))
            total = carry + roll_factor * carry
            return FlightResult(
                carry_m=carry, total_m=total, apex_m=apex,
                flight_time_s=t, descent_angle_deg=descent,
                landing_speed_ms=land_speed, offline_m=offline,
                trajectory=np.array(traj),
            )

    # Did not land within max_time (shouldn't happen for real shots).
    return FlightResult(
        carry_m=float(p[0]), total_m=float(p[0]), apex_m=apex,
        flight_time_s=t, descent_angle_deg=0.0,
        landing_speed_ms=float(np.linalg.norm(v)),
        offline_m=float(WORLD_Y_PER_GOLF_RIGHT * p[1]),
        trajectory=np.array(traj),
    )
