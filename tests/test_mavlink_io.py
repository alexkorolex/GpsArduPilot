# AP_FLAKE8_CLEAN
"""Tests for MAVLink helpers without a live autopilot."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from pymavlink import mavutil

from external_gps.mavlink_io import (
    battery_remaining_percent,
    disable_sitl_mag_field_check,
    request_land,
    send_gps_input,
    send_set_home,
    set_parameter,
    update_state_from_message,
    verify_injected_point,
)
from external_gps.models import GpsFix, RuntimeState


@dataclass(slots=True)
class ParamValueMessage:
    param_id: str
    param_value: float


class SimpleMessage:
    def __init__(self, msg_type: str, **fields: Any) -> None:
        self._msg_type = msg_type
        self._fields = dict(fields)
        for key, value in fields.items():
            setattr(self, key, value)

    def get_type(self) -> str:
        return self._msg_type

    def to_dict(self) -> dict[str, Any]:
        return {"mavpackettype": self._msg_type, **self._fields}


class FakeMav:
    def __init__(self) -> None:
        self.gps_input_args: tuple[Any, ...] | None = None
        self.command_int_args: tuple[Any, ...] | None = None
        self.param_set_args: tuple[Any, ...] | None = None

    def gps_input_send(self, *args: Any) -> None:
        self.gps_input_args = args

    def command_int_send(self, *args: Any) -> None:
        self.command_int_args = args

    def param_set_send(self, *args: Any) -> None:
        self.param_set_args = args


class FakeMaster:
    def __init__(self, messages: list[Any] | None = None) -> None:
        self.target_system = 1
        self.target_component = 1
        self.mav = FakeMav()
        self._messages = list(messages or [])

    def recv_match(self, **kwargs: Any) -> Any:
        if not self._messages:
            return None
        return self._messages.pop(0)


class MavlinkIoTests(unittest.TestCase):
    def test_send_gps_input_uses_valid_gps_time_and_scaled_coordinates(self) -> None:
        master = FakeMaster()
        fix = GpsFix(lat=55.1234567, lon=37.7654321, alt_m=42.5, vn_m_s=1.0, ve_m_s=2.0)

        send_gps_input(master, fix, now_unix_s=315_964_800.0 + 604_801.25)

        assert master.mav.gps_input_args is not None
        args = master.mav.gps_input_args
        self.assertEqual(args[3], 1250)
        self.assertEqual(args[4], 1)
        self.assertEqual(args[5], 3)
        self.assertEqual(args[6], 551234567)
        self.assertEqual(args[7], 377654321)
        self.assertEqual(args[8], 42.5)

    def test_send_set_home_uses_command_int_coordinates(self) -> None:
        master = FakeMaster()

        send_set_home(master, GpsFix(lat=55.1, lon=37.2, alt_m=50.0))

        assert master.mav.command_int_args is not None
        args = master.mav.command_int_args
        self.assertEqual(args[2], mavutil.mavlink.MAV_FRAME_GLOBAL)
        self.assertEqual(args[3], mavutil.mavlink.MAV_CMD_DO_SET_HOME)
        self.assertEqual(args[10], 551000000)
        self.assertEqual(args[11], 372000000)
        self.assertEqual(args[12], 50.0)

    def test_request_land_uses_nav_land_command(self) -> None:
        master = FakeMaster()

        request_land(master)

        assert master.mav.command_int_args is not None
        args = master.mav.command_int_args
        self.assertEqual(args[2], mavutil.mavlink.MAV_FRAME_GLOBAL)
        self.assertEqual(args[3], mavutil.mavlink.MAV_CMD_NAV_LAND)
        self.assertEqual(args[10], 0)
        self.assertEqual(args[11], 0)
        self.assertEqual(args[12], 0.0)

    def test_set_parameter_returns_acknowledged_value(self) -> None:
        master = FakeMaster([ParamValueMessage(param_id="GPS1_TYPE", param_value=14.0)])

        result = set_parameter(master, "GPS1_TYPE", 14, mavutil.mavlink.MAV_PARAM_TYPE_INT8)

        assert master.mav.param_set_args is not None
        self.assertEqual(master.mav.param_set_args[2], b"GPS1_TYPE")
        self.assertTrue(result.acknowledged)
        self.assertEqual(result.confirmed, 14.0)

    def test_disable_sitl_mag_field_check_sets_threshold_zero(self) -> None:
        master = FakeMaster([ParamValueMessage(param_id="ARMING_MAGTHRESH", param_value=0.0)])

        result = disable_sitl_mag_field_check(master, logger=_NullLogger())

        assert master.mav.param_set_args is not None
        self.assertEqual(master.mav.param_set_args[2], b"ARMING_MAGTHRESH")
        self.assertEqual(master.mav.param_set_args[3], 0.0)
        self.assertTrue(result.acknowledged)

    def test_verify_injected_point_sets_verified_flag(self) -> None:
        state = RuntimeState(last_gps_raw={"lat": 551000000, "lon": 372000000})

        distance = verify_injected_point(state, GpsFix(lat=55.1, lon=37.2, alt_m=50.0), tolerance_m=1.0)

        self.assertIsNotNone(distance)
        self.assertTrue(state.injected_point_verified)

    def test_update_state_records_battery_percent_from_sys_status(self) -> None:
        state = RuntimeState()

        update_state_from_message(FakeMaster(), state, SimpleMessage("SYS_STATUS", battery_remaining=9), _NullLogger())

        self.assertEqual(state.last_battery_remaining_percent, 9)
        self.assertEqual(state.last_battery_message_type, "SYS_STATUS")

    def test_battery_remaining_percent_ignores_unknown_values(self) -> None:
        self.assertIsNone(battery_remaining_percent(SimpleMessage("BATTERY_STATUS", battery_remaining=-1)))
        self.assertIsNone(battery_remaining_percent(SimpleMessage("BATTERY_STATUS", battery_remaining=101)))
        self.assertIsNone(battery_remaining_percent(SimpleMessage("BATTERY_STATUS")))


class _NullLogger:
    def info(self, *args: Any) -> None:
        return None

    def warning(self, *args: Any) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
