import datetime as dt
import math

import numpy as np


def normalize_longitude_deg(value):
    result = (np.asarray(value) + 180.0) % 360.0 - 180.0
    return float(result) if result.ndim == 0 else result


def _parse_utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC time must be an ISO-8601 string ending in Z")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"invalid UTC time: {value}") from exc
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("time must be UTC")
    return parsed


def julian_date_utc(value: str) -> float:
    parsed = _parse_utc(value)
    unix_epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    unix_seconds = (parsed - unix_epoch).total_seconds()
    return unix_seconds / 86400.0 + 2440587.5


def gmst_degrees(value: str) -> float:
    jd = julian_date_utc(value)
    centuries = (jd - 2451545.0) / 36525.0
    angle = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * centuries ** 2
        - centuries ** 3 / 38710000.0
    )
    return angle % 360.0


def _position_array(value, name):
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError(f"{name} must have shape (N, 3)")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


def eci_to_ecef(eci_km, epoch_utc: str, time_s: int, earth_rotation_rad_s: float):
    eci = _position_array(eci_km, "eci_km")
    if isinstance(time_s, bool) or not isinstance(time_s, int) or time_s < 0:
        raise ValueError("time_s must be a nonnegative integer")
    if not math.isfinite(earth_rotation_rad_s):
        raise ValueError("earth_rotation_rad_s must be finite")
    theta = (math.radians(gmst_degrees(epoch_utc)) + earth_rotation_rad_s * time_s) % (2.0 * math.pi)
    cosine, sine = math.cos(theta), math.sin(theta)
    result = np.empty_like(eci)
    result[:, 0] = cosine * eci[:, 0] + sine * eci[:, 1]
    result[:, 1] = -sine * eci[:, 0] + cosine * eci[:, 1]
    result[:, 2] = eci[:, 2]
    return result


def ecef_to_spherical_latlon(ecef_km):
    ecef = _position_array(ecef_km, "ecef_km")
    horizontal = np.hypot(ecef[:, 0], ecef[:, 1])
    latitude = np.degrees(np.arctan2(ecef[:, 2], horizontal))
    longitude = normalize_longitude_deg(np.degrees(np.arctan2(ecef[:, 1], ecef[:, 0])))
    return latitude, longitude
