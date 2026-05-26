# AP_FLAKE8_CLEAN
"""Tests for CLI assembly helpers."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr

from external_gps.cli import build_provider, parse_args, summary_text
from external_gps.models import RuntimeState
from external_gps.providers import RandomPointGpsProvider, SimStateOffsetGpsProvider, StaticGpsProvider


class CliTests(unittest.TestCase):
    def test_default_provider_is_random_simstate(self) -> None:
        args = parse_args(["--random-seed", "7"])
        state = RuntimeState()

        provider = build_provider(args, state)

        self.assertIsInstance(provider, SimStateOffsetGpsProvider)

    def test_random_point_provider_builds_without_state(self) -> None:
        args = parse_args(["--provider", "random-point", "--random-seed", "7"])

        provider = build_provider(args)

        self.assertIsInstance(provider, RandomPointGpsProvider)

    def test_static_provider_builds_from_cli_coordinates(self) -> None:
        args = parse_args(["--provider", "static", "--static-lat", "55.5", "--static-lon", "37.5"])

        provider = build_provider(args)

        self.assertIsInstance(provider, StaticGpsProvider)
        self.assertEqual(provider.start_fix.lat, 55.5)
        self.assertEqual(provider.start_fix.lon, 37.5)

    def test_critical_battery_percent_is_configurable(self) -> None:
        args = parse_args(["--critical-battery-percent", "12"])

        self.assertEqual(args.critical_battery_percent, 12)

    def test_critical_battery_percent_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            parse_args(["--critical-battery-percent", "101"])

    def test_summary_mentions_simstate(self) -> None:
        state = RuntimeState(messages_received=3, gps_messages_sent=2, last_simstate={"lat": 1, "lng": 2})

        self.assertIn("simstate=yes", summary_text(state))

    def test_summary_mentions_battery(self) -> None:
        state = RuntimeState(last_battery_remaining_percent=8, last_battery_message_type="SYS_STATUS")

        self.assertIn("battery=8%/SYS_STATUS", summary_text(state))


if __name__ == "__main__":
    unittest.main()
