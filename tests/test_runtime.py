# AP_FLAKE8_CLEAN
"""Tests for runtime mission safety checks."""

from __future__ import annotations

import argparse
import unittest
from typing import Any

from pymavlink import mavutil

from external_gps.models import RuntimeState
from external_gps.runtime import maybe_handle_critical_battery


class FakeMav:
    def __init__(self) -> None:
        self.command_int_args: tuple[Any, ...] | None = None

    def command_int_send(self, *args: Any) -> None:
        self.command_int_args = args


class FakeMaster:
    def __init__(self) -> None:
        self.target_system = 1
        self.target_component = 1
        self.mav = FakeMav()


class FakeRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], str]] = []

    def write_event(self, event: str, payload: dict[str, Any], direction: str = "event") -> None:
        self.events.append((event, payload, direction))


class FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[tuple[Any, ...]] = []
        self.errors: list[tuple[Any, ...]] = []

    def warning(self, *args: Any) -> None:
        self.warnings.append(args)

    def error(self, *args: Any) -> None:
        self.errors.append(args)


class RuntimeTests(unittest.TestCase):
    def test_critical_battery_requests_land_once(self) -> None:
        args = argparse.Namespace(critical_battery_percent=10)
        master = FakeMaster()
        recorder = FakeRecorder()
        logger = FakeLogger()
        state = RuntimeState(last_battery_remaining_percent=9, last_battery_message_type="SYS_STATUS")

        maybe_handle_critical_battery(args, master, state, recorder, logger)
        maybe_handle_critical_battery(args, master, state, recorder, logger)

        assert master.mav.command_int_args is not None
        self.assertEqual(master.mav.command_int_args[3], mavutil.mavlink.MAV_CMD_NAV_LAND)
        self.assertTrue(state.low_battery_landing_requested)
        self.assertEqual(len(recorder.events), 1)
        self.assertEqual(recorder.events[0][0], "CRITICAL_BATTERY_LAND_REQUESTED")
        self.assertEqual(recorder.events[0][1]["battery_remaining_percent"], 9)
        self.assertEqual(len(logger.warnings), 1)

    def test_critical_battery_disabled_does_not_request_land(self) -> None:
        args = argparse.Namespace(critical_battery_percent=0)
        master = FakeMaster()
        state = RuntimeState(last_battery_remaining_percent=1)

        maybe_handle_critical_battery(args, master, state, FakeRecorder(), FakeLogger())

        self.assertIsNone(master.mav.command_int_args)
        self.assertFalse(state.low_battery_landing_requested)


if __name__ == "__main__":
    unittest.main()
