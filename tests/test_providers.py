# AP_FLAKE8_CLEAN
"""Tests for GPS providers."""

from __future__ import annotations

import unittest

from external_gps.models import GpsFix, RandomPointConfig, RuntimeState, distance_m
from external_gps.providers import DemoLineGpsProvider, RandomPointGpsProvider, SimStateOffsetGpsProvider


class ProviderTests(unittest.TestCase):
    def test_random_point_is_reproducible_and_inside_radius(self) -> None:
        config = RandomPointConfig(
            base_lat=55.0,
            base_lon=37.0,
            base_alt_m=50.0,
            min_radius_m=10.0,
            max_radius_m=20.0,
            satellites=10,
            seed=42,
        )

        first = RandomPointGpsProvider(config).start_fix
        second = RandomPointGpsProvider(config).start_fix
        radius_m = distance_m(config.base_lat, config.base_lon, first.lat, first.lon)

        self.assertEqual(first, second)
        self.assertGreaterEqual(radius_m, 10.0)
        self.assertLessEqual(radius_m, 20.0)

    def test_random_point_rejects_invalid_radius(self) -> None:
        config = RandomPointConfig(
            base_lat=55.0,
            base_lon=37.0,
            base_alt_m=50.0,
            min_radius_m=20.0,
            max_radius_m=10.0,
            satellites=10,
        )

        with self.assertRaises(ValueError):
            RandomPointGpsProvider(config)

    def test_demo_line_moves_by_velocity(self) -> None:
        provider = DemoLineGpsProvider(GpsFix(lat=55.0, lon=37.0, alt_m=50.0), north_m_s=5.0, east_m_s=0.0)

        provider.current_fix(100.0)
        moved = provider.current_fix(110.0)

        self.assertAlmostEqual(distance_m(55.0, 37.0, moved.lat, moved.lon), 50.0, delta=0.1)
        self.assertEqual(moved.vn_m_s, 5.0)

    def test_simstate_provider_translates_sitl_motion(self) -> None:
        state = RuntimeState()
        provider = SimStateOffsetGpsProvider(GpsFix(lat=55.0, lon=37.0, alt_m=50.0), state)

        state.last_simstate = {"lat": int(-35.0 * 1e7), "lng": int(149.0 * 1e7)}
        self.assertEqual(provider.current_fix(10.0).lat, 55.0)

        state.last_simstate = {"lat": int((-35.0 + 0.0001) * 1e7), "lng": int(149.0 * 1e7)}
        moved = provider.current_fix(11.0)

        self.assertAlmostEqual(distance_m(55.0, 37.0, moved.lat, moved.lon), 11.12, delta=0.2)
        self.assertAlmostEqual(moved.vn_m_s, 11.12, delta=0.2)


if __name__ == "__main__":
    unittest.main()
