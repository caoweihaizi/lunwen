import math
from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np

from mucar_data.contracts import SimulationContract
from .constellation import Satellite
from .coordinates import ecef_to_spherical_latlon, eci_to_ecef


@dataclass(frozen=True)
class PositionSnapshot:
    time_s: int
    sat_ids: Tuple[str, ...]
    eci_km: np.ndarray
    ecef_km: np.ndarray
    latitude_deg: np.ndarray
    longitude_deg: np.ndarray


def _readonly(array):
    output = np.asarray(array, dtype=np.float64)
    output.flags.writeable = False
    return output


def propagate(contract: SimulationContract, satellites: Sequence[Satellite], time_s: int) -> PositionSnapshot:
    if isinstance(time_s, bool) or not isinstance(time_s, int) or time_s < 0:
        raise ValueError("time_s must be a nonnegative integer")
    if len(satellites) != contract.total_satellites:
        raise ValueError("satellite count differs from contract")
    raan = np.radians([satellite.raan_deg for satellite in satellites])
    phase = np.radians([satellite.phase_deg for satellite in satellites])
    argument = phase + contract.mean_motion_rad_s * time_s
    inclination = math.radians(contract.orbit.inclination_deg)
    cos_raan, sin_raan = np.cos(raan), np.sin(raan)
    cos_u, sin_u = np.cos(argument), np.sin(argument)
    radius = contract.orbit_radius_km
    eci = np.column_stack((
        radius * (cos_raan * cos_u - sin_raan * sin_u * math.cos(inclination)),
        radius * (sin_raan * cos_u + cos_raan * sin_u * math.cos(inclination)),
        radius * sin_u * math.sin(inclination),
    )).astype(np.float64, copy=False)
    ecef = eci_to_ecef(eci, contract.time.epoch_utc, time_s, contract.earth.rotation_rad_s)
    latitude, longitude = ecef_to_spherical_latlon(ecef)
    return PositionSnapshot(
        time_s=time_s,
        sat_ids=tuple(satellite.sat_id for satellite in satellites),
        eci_km=_readonly(eci), ecef_km=_readonly(ecef),
        latitude_deg=_readonly(latitude), longitude_deg=_readonly(longitude),
    )
