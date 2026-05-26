# AP_FLAKE8_CLEAN
"""Tests for GPS model helpers."""

from __future__ import annotations

import unittest

from external_gps.models import (
    GpsFix,
    add_local_offset_to_lat_lon,
    distance_m,
    gps_input_payload,
    gps_week_and_ms,
    local_offset_m,
    validate_fix,
)


class ModelTests(unittest.TestCase):
    def test_local_offset_round_trips(self) -> None:
        origin_lat = 55.0
        origin_lon = 37.0
        lat, lon = add_local_offset_to_lat_lon(origin_lat, origin_lon, north_m=120.0, east_m=-40.0)

        north_m, east_m = local_offset_m(origin_lat, origin_lon, lat, lon)

        self.assertAlmostEqual(north_m, 120.0, delta=0.01)
        self.assertAlmostEqual(east_m, -40.0, delta=0.01)
        self.assertAlmostEqual(distance_m(origin_lat, origin_lon, lat, lon), 126.49, delta=0.1)

    def test_gps_week_and_ms_uses_gps_epoch(self) -> None:
        gps_epoch_unix_s = 315_964_800.0

        self.assertEqual(gps_week_and_ms(gps_epoch_unix_s), (0, 0))
        self.assertEqual(gps_week_and_ms(gps_epoch_unix_s + 604_801.25), (1, 1250))

    def test_gps_input_payload_converts_lat_lon_to_ints(self) -> None:
        payload = gps_input_payload(GpsFix(lat=55.1234567, lon=37.7654321, alt_m=42.0))

        self.assertEqual(payload["lat_int"], 551234567)
        self.assertEqual(payload["lon_int"], 377654321)
        self.assertEqual(payload["fix_type"], 3)

    def test_invalid_fix_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_fix(GpsFix(lat=91.0, lon=37.0, alt_m=50.0))


if __name__ == "__main__":
    unittest.main()
