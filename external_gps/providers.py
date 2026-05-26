# AP_FLAKE8_CLEAN
"""GPS fix providers used by the command-line app."""

from __future__ import annotations

import math
import random
from typing import Protocol

from external_gps.models import (
    GpsFix,
    RandomPointConfig,
    RuntimeState,
    add_local_offset_to_lat_lon,
    local_offset_m,
    validate_fix,
    validate_random_config,
)


class GpsProvider(Protocol):
    """Interface for any source of external GPS coordinates."""

    @property
    def start_fix(self) -> GpsFix:
        """Return the first fix used by this provider."""

    def current_fix(self, now_monotonic: float) -> GpsFix:
        """Return the current GPS fix that should be injected."""


class StaticGpsProvider:
    """Always returns one fixed GPS point."""

    def __init__(self, fix: GpsFix) -> None:
        validate_fix(fix)
        self._fix = fix

    @property
    def start_fix(self) -> GpsFix:
        return self._fix

    def current_fix(self, now_monotonic: float) -> GpsFix:
        return self._fix


class RandomPointGpsProvider(StaticGpsProvider):
    """Chooses one random point at startup and keeps it stable."""

    def __init__(self, config: RandomPointConfig) -> None:
        validate_random_config(config)
        rng = random.Random(config.seed)
        super().__init__(choose_random_fix(config, rng))


class SimStateOffsetGpsProvider:
    """Translates SITL SIMSTATE movement onto a random GPS start point."""

    def __init__(self, start: GpsFix, state: RuntimeState) -> None:
        validate_fix(start)
        self._start = start
        self._state = state
        self._sim_origin: tuple[float, float] | None = None
        self._last_fix = start
        self._last_time: float | None = None

    @property
    def start_fix(self) -> GpsFix:
        return self._start

    def current_fix(self, now_monotonic: float) -> GpsFix:
        sim_lat_lon = self._sim_lat_lon()
        if sim_lat_lon is None:
            return self._start

        if self._sim_origin is None:
            self._sim_origin = sim_lat_lon
            self._last_time = now_monotonic
            return self._start

        north_m, east_m = local_offset_m(self._sim_origin[0], self._sim_origin[1], sim_lat_lon[0], sim_lat_lon[1])
        lat, lon = add_local_offset_to_lat_lon(self._start.lat, self._start.lon, north_m, east_m)
        vn_m_s, ve_m_s = self._velocity_from_last_fix(lat, lon, now_monotonic)

        fix = GpsFix(
            lat=lat,
            lon=lon,
            alt_m=self._start.alt_m,
            vn_m_s=vn_m_s,
            ve_m_s=ve_m_s,
            satellites=self._start.satellites,
            hdop=self._start.hdop,
            vdop=self._start.vdop,
            speed_accuracy_m_s=self._start.speed_accuracy_m_s,
            horiz_accuracy_m=self._start.horiz_accuracy_m,
            vert_accuracy_m=self._start.vert_accuracy_m,
        )
        self._last_fix = fix
        self._last_time = now_monotonic
        return fix

    def _sim_lat_lon(self) -> tuple[float, float] | None:
        if self._state.last_simstate is None:
            return None
        raw_lat = int(self._state.last_simstate.get("lat", 0))
        raw_lon = int(self._state.last_simstate.get("lng", 0))
        if raw_lat == 0 and raw_lon == 0:
            return None
        return raw_lat / 1e7, raw_lon / 1e7

    def _velocity_from_last_fix(self, lat: float, lon: float, now_monotonic: float) -> tuple[float, float]:
        if self._last_time is None:
            return 0.0, 0.0
        dt_s = now_monotonic - self._last_time
        if dt_s <= 0.0:
            return self._last_fix.vn_m_s, self._last_fix.ve_m_s
        north_m, east_m = local_offset_m(self._last_fix.lat, self._last_fix.lon, lat, lon)
        return north_m / dt_s, east_m / dt_s


class DemoLineGpsProvider:
    """
    Demo provider that slowly moves from the start point by north/east velocity.

    This is useful for local SITL smoke tests. A real external navigation source
    should replace this provider with measured position updates.
    """

    def __init__(self, start: GpsFix, north_m_s: float, east_m_s: float) -> None:
        validate_fix(start)
        self._start = start
        self._north_m_s = north_m_s
        self._east_m_s = east_m_s
        self._started_at: float | None = None

    @property
    def start_fix(self) -> GpsFix:
        return self._start

    def current_fix(self, now_monotonic: float) -> GpsFix:
        if self._started_at is None:
            self._started_at = now_monotonic

        elapsed_s = max(now_monotonic - self._started_at, 0.0)
        lat, lon = add_local_offset_to_lat_lon(
            lat=self._start.lat,
            lon=self._start.lon,
            north_m=self._north_m_s * elapsed_s,
            east_m=self._east_m_s * elapsed_s,
        )

        return GpsFix(
            lat=lat,
            lon=lon,
            alt_m=self._start.alt_m,
            vn_m_s=self._north_m_s,
            ve_m_s=self._east_m_s,
            vd_m_s=0.0,
            satellites=self._start.satellites,
            hdop=self._start.hdop,
            vdop=self._start.vdop,
            speed_accuracy_m_s=self._start.speed_accuracy_m_s,
            horiz_accuracy_m=self._start.horiz_accuracy_m,
            vert_accuracy_m=self._start.vert_accuracy_m,
        )


def choose_random_fix(config: RandomPointConfig, rng: random.Random) -> GpsFix:
    validate_random_config(config)
    radius_m = math.sqrt(rng.uniform(config.min_radius_m**2, config.max_radius_m**2))
    bearing_rad = rng.uniform(0.0, math.tau)
    north_m = math.cos(bearing_rad) * radius_m
    east_m = math.sin(bearing_rad) * radius_m
    lat, lon = add_local_offset_to_lat_lon(config.base_lat, config.base_lon, north_m, east_m)

    return GpsFix(
        lat=lat,
        lon=lon,
        alt_m=config.base_alt_m,
        satellites=config.satellites,
    )
