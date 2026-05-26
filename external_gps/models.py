# AP_FLAKE8_CLEAN
"""Core data structures and geodesy helpers."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class GpsFix:
    """GPS fix in units used by the application layer."""

    lat: float
    lon: float
    alt_m: float
    vn_m_s: float = 0.0
    ve_m_s: float = 0.0
    vd_m_s: float = 0.0
    satellites: int = 10
    hdop: float = 1.0
    vdop: float = 1.0
    speed_accuracy_m_s: float = 0.5
    horiz_accuracy_m: float = 0.5
    vert_accuracy_m: float = 1.0


@dataclass(slots=True)
class RandomPointConfig:
    """Configuration for one random, stable start point."""

    base_lat: float
    base_lon: float
    base_alt_m: float
    min_radius_m: float
    max_radius_m: float
    satellites: int
    seed: int | None = None


@dataclass(slots=True)
class RuntimeState:
    """Small state cache for diagnostics and runtime safety decisions."""

    armed: bool = False
    flight_mode: str | None = None
    messages_received: int = 0
    gps_messages_sent: int = 0
    last_heartbeat_wall_time: float | None = None
    last_global_position: dict[str, Any] | None = None
    last_gps_raw: dict[str, Any] | None = None
    last_simstate: dict[str, Any] | None = None
    last_battery_remaining_percent: int | None = None
    last_battery_message_type: str | None = None
    injected_point_verified: bool = False
    injected_point_warning_sent: bool = False
    low_battery_landing_requested: bool = False


def validate_lat_lon(lat: float, lon: float) -> None:
    if not math.isfinite(lat) or not -90.0 <= lat <= 90.0:
        raise ValueError(f"latitude must be finite and in [-90, 90], got {lat!r}")
    if not math.isfinite(lon) or not -180.0 <= lon <= 180.0:
        raise ValueError(f"longitude must be finite and in [-180, 180], got {lon!r}")


def validate_fix(fix: GpsFix) -> None:
    validate_lat_lon(fix.lat, fix.lon)
    numeric_values = [
        fix.alt_m,
        fix.vn_m_s,
        fix.ve_m_s,
        fix.vd_m_s,
        fix.hdop,
        fix.vdop,
        fix.speed_accuracy_m_s,
        fix.horiz_accuracy_m,
        fix.vert_accuracy_m,
    ]
    if any(not math.isfinite(value) for value in numeric_values):
        raise ValueError(f"GPS fix contains non-finite numeric values: {fix!r}")
    if not 0 <= fix.satellites <= 255:
        raise ValueError(f"satellites must be in [0, 255], got {fix.satellites!r}")


def validate_random_config(config: RandomPointConfig) -> None:
    validate_lat_lon(config.base_lat, config.base_lon)
    if not math.isfinite(config.base_alt_m):
        raise ValueError("base altitude must be finite")
    if config.min_radius_m < 0:
        raise ValueError("minimum random radius must be non-negative")
    if config.max_radius_m < config.min_radius_m:
        raise ValueError("maximum random radius must be >= minimum random radius")
    if not 0 <= config.satellites <= 255:
        raise ValueError(f"satellites must be in [0, 255], got {config.satellites!r}")


def add_local_offset_to_lat_lon(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    validate_lat_lon(lat, lon)
    earth_radius_m = 6_371_000.0
    lat_rad = math.radians(lat)
    cos_lat = max(abs(math.cos(lat_rad)), 1e-9)

    new_lat = lat + (north_m / earth_radius_m) * (180.0 / math.pi)
    new_lon = lon + (east_m / (earth_radius_m * cos_lat)) * (180.0 / math.pi)
    return new_lat, normalize_lon(new_lon)


def local_offset_m(origin_lat: float, origin_lon: float, lat: float, lon: float) -> tuple[float, float]:
    validate_lat_lon(origin_lat, origin_lon)
    validate_lat_lon(lat, lon)
    earth_radius_m = 6_371_000.0
    origin_lat_rad = math.radians(origin_lat)
    north_m = math.radians(lat - origin_lat) * earth_radius_m
    east_m = math.radians(lon - origin_lon) * earth_radius_m * max(abs(math.cos(origin_lat_rad)), 1e-9)
    return north_m, east_m


def distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    validate_lat_lon(lat_a, lon_a)
    validate_lat_lon(lat_b, lon_b)
    earth_radius_m = 6_371_000.0
    lat1 = math.radians(lat_a)
    lat2 = math.radians(lat_b)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon_b - lon_a)

    hav = math.sin(delta_lat / 2.0) ** 2
    hav += math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2.0) ** 2
    return 2.0 * earth_radius_m * math.asin(min(1.0, math.sqrt(hav)))


def normalize_lon(lon: float) -> float:
    normalized = (lon + 180.0) % 360.0 - 180.0
    if normalized == -180.0 and lon > 0:
        return 180.0
    return normalized


def gps_week_and_ms(now_unix_s: float | None = None) -> tuple[int, int]:
    timestamp_s = time.time() if now_unix_s is None else now_unix_s
    gps_epoch_unix_s = 315_964_800.0
    seconds_per_week = 604_800.0
    elapsed_s = max(timestamp_s - gps_epoch_unix_s, 0.0)
    week = int(elapsed_s // seconds_per_week)
    week_ms = int((elapsed_s % seconds_per_week) * 1000.0)
    return week, week_ms


def gps_input_payload(fix: GpsFix) -> dict[str, Any]:
    validate_fix(fix)
    payload = asdict(fix)
    payload.update(
        {
            "lat_int": int(fix.lat * 1e7),
            "lon_int": int(fix.lon * 1e7),
            "fix_type": 3,
            "ignore_flags": 0,
        }
    )
    return payload
