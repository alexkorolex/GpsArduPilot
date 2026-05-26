# AP_FLAKE8_CLEAN
"""MAVLink read/write helpers."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from pymavlink import mavutil

from external_gps.battery import battery_remaining_percent
from external_gps.message_utils import safe_message_dict, safe_message_type
from external_gps.models import GpsFix, RuntimeState, distance_m, gps_week_and_ms, validate_fix
from external_gps.recorder import MavlinkJsonlRecorder


@dataclass(slots=True)
class ParameterWriteResult:
    name: str
    requested: float
    confirmed: float | None

    @property
    def acknowledged(self) -> bool:
        return self.confirmed is not None


def send_gps_input(master: Any, fix: GpsFix, now_unix_s: float | None = None) -> None:
    """Send MAVLink GPS_INPUT using pymavlink's generated helper."""
    validate_fix(fix)
    timestamp_s = time.time() if now_unix_s is None else now_unix_s
    time_week, time_week_ms = gps_week_and_ms(timestamp_s)

    master.mav.gps_input_send(
        int(timestamp_s * 1_000_000),
        0,
        0,
        time_week_ms,
        time_week,
        3,
        int(fix.lat * 1e7),
        int(fix.lon * 1e7),
        float(fix.alt_m),
        float(fix.hdop),
        float(fix.vdop),
        float(fix.vn_m_s),
        float(fix.ve_m_s),
        float(fix.vd_m_s),
        float(fix.speed_accuracy_m_s),
        float(fix.horiz_accuracy_m),
        float(fix.vert_accuracy_m),
        int(fix.satellites),
        0,
    )


def send_set_home(master: Any, fix: GpsFix) -> None:
    """Ask ArduPilot to set HOME to the injected point."""
    validate_fix(fix)
    master.mav.command_int_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL,
        mavutil.mavlink.MAV_CMD_DO_SET_HOME,
        0,
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        int(fix.lat * 1e7),
        int(fix.lon * 1e7),
        float(fix.alt_m),
    )


def request_land(master: Any) -> None:
    """Ask ArduCopter to switch to LAND, which stops the active AUTO mission."""
    master.mav.command_int_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL,
        mavutil.mavlink.MAV_CMD_NAV_LAND,
        0,
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        0,
        0.0,
    )


def maybe_request_data_stream(master: Any, rate_hz: int, logger: logging.Logger) -> None:
    if rate_hz <= 0:
        return

    try:
        master.mav.request_data_stream_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            rate_hz,
            1,
        )
        logger.info("Requested MAVLink data stream: %s Hz", rate_hz)
    except Exception as exc:
        logger.warning("Could not request MAVLink data stream: %s", exc)


def configure_sitl_for_gps_input(master: Any, logger: logging.Logger) -> list[ParameterWriteResult]:
    """Set the minimum SITL params needed for GPS_INPUT to become GPS1."""
    writes = [
        ("SIM_GPS1_ENABLE", 0, mavutil.mavlink.MAV_PARAM_TYPE_INT8),
        ("GPS1_TYPE", 14, mavutil.mavlink.MAV_PARAM_TYPE_INT8),
    ]
    results = []
    for name, value, param_type in writes:
        result = set_parameter(master, name, value, param_type)
        results.append(result)
        if result.acknowledged:
            logger.info("Parameter %s confirmed as %s", name, result.confirmed)
        else:
            logger.warning("Parameter %s was sent but no PARAM_VALUE ack arrived", name)
    return results


def disable_sitl_mag_field_check(master: Any, logger: logging.Logger) -> ParameterWriteResult:
    """Disable the magnetic model comparison for shifted SITL GPS locations."""
    result = set_parameter(master, "ARMING_MAGTHRESH", 0, mavutil.mavlink.MAV_PARAM_TYPE_INT16)
    if result.acknowledged:
        logger.warning("ARMING_MAGTHRESH confirmed as 0; use this only for SITL with synthetic GPS locations.")
    else:
        logger.warning("ARMING_MAGTHRESH=0 was sent but no PARAM_VALUE ack arrived")
    return result


def set_parameter(master: Any, name: str, value: float, param_type: int, timeout_s: float = 1.5) -> ParameterWriteResult:
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        name.encode("ascii"),
        float(value),
        param_type,
    )

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        remaining_s = max(deadline - time.monotonic(), 0.0)
        msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=remaining_s)
        if msg is None:
            break
        param_id = str(getattr(msg, "param_id", "")).rstrip("\x00")
        if param_id == name:
            return ParameterWriteResult(name=name, requested=float(value), confirmed=float(msg.param_value))

    return ParameterWriteResult(name=name, requested=float(value), confirmed=None)


def read_pending_messages(
    master: Any,
    state: RuntimeState,
    recorder: MavlinkJsonlRecorder,
    logger: logging.Logger,
) -> int:
    processed = 0

    while True:
        msg = master.recv_match(blocking=False)
        if msg is None:
            return processed

        processed += 1
        state.messages_received += 1
        recorder.write_incoming(msg)
        update_state_from_message(master, state, msg, logger)


def update_state_from_message(master: Any, state: RuntimeState, msg: Any, logger: logging.Logger) -> None:
    msg_type = safe_message_type(msg)

    if msg_type == "HEARTBEAT":
        state.last_heartbeat_wall_time = time.time()
        state.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        state.flight_mode = safe_flight_mode(master)
        return

    if msg_type == "GLOBAL_POSITION_INT":
        state.last_global_position = safe_message_dict(msg)
        return

    if msg_type == "GPS_RAW_INT":
        state.last_gps_raw = safe_message_dict(msg)
        return

    if msg_type == "SIMSTATE":
        state.last_simstate = safe_message_dict(msg)
        return

    if msg_type in {"SYS_STATUS", "BATTERY_STATUS"}:
        update_battery_state_from_message(state, msg_type, msg)
        return

    if msg_type == "STATUSTEXT":
        text = getattr(msg, "text", "")
        if text:
            logger.info("STATUSTEXT: %s", text)


def update_battery_state_from_message(state: RuntimeState, msg_type: str, msg: Any) -> None:
    remaining_percent = battery_remaining_percent(msg)
    if remaining_percent is None:
        return

    state.last_battery_remaining_percent = remaining_percent
    state.last_battery_message_type = msg_type


def verify_injected_point(state: RuntimeState, expected: GpsFix, tolerance_m: float) -> float | None:
    if state.last_gps_raw is None:
        return None

    raw_lat = int(state.last_gps_raw.get("lat", 0))
    raw_lon = int(state.last_gps_raw.get("lon", 0))
    if raw_lat == 0 and raw_lon == 0:
        return None

    distance = distance_m(raw_lat / 1e7, raw_lon / 1e7, expected.lat, expected.lon)
    if distance <= tolerance_m:
        state.injected_point_verified = True
    return distance


def safe_flight_mode(master: Any) -> str | None:
    try:
        return master.flightmode
    except Exception:
        return None
