# AP_FLAKE8_CLEAN
"""Runtime loop and mission safety checks for the GPS_INPUT injector."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Callable

from external_gps.mavlink_io import read_pending_messages, request_land, send_gps_input, verify_injected_point
from external_gps.models import GpsFix, RuntimeState
from external_gps.providers import GpsProvider
from external_gps.recorder import MavlinkJsonlRecorder


def run_loop(
    args: argparse.Namespace,
    master: object,
    provider: GpsProvider,
    state: RuntimeState,
    recorder: MavlinkJsonlRecorder,
    logger: logging.Logger,
    should_stop_getter: Callable[[], bool],
) -> None:
    started_at = time.monotonic()
    last_send_monotonic = 0.0
    last_summary_monotonic = 0.0

    while not should_stop_getter():
        now = time.monotonic()
        processed = read_pending_messages(master, state, recorder, logger)
        if processed and args.log_level == "DEBUG":
            logger.debug("Processed %s MAVLink messages", processed)

        maybe_handle_critical_battery(args, master, state, recorder, logger)

        if now - last_send_monotonic >= args.interval:
            fix = provider.current_fix(now)
            send_gps_input(master, fix)
            recorder.write_outgoing_gps_input(fix)
            state.gps_messages_sent += 1
            last_send_monotonic = now

        maybe_report_verification(args, provider.start_fix, state, logger, now - started_at)

        if now - last_summary_monotonic >= args.summary_every:
            logger.info(summary_text(state))
            last_summary_monotonic = now

        time.sleep(0.01)

    recorder.write_event(
        "SCRIPT_STOPPED",
        {"messages_received": state.messages_received, "gps_messages_sent": state.gps_messages_sent},
    )


def maybe_handle_critical_battery(
    args: argparse.Namespace,
    master: object,
    state: RuntimeState,
    recorder: MavlinkJsonlRecorder,
    logger: logging.Logger,
) -> None:
    threshold = int(getattr(args, "critical_battery_percent", 0))
    remaining = state.last_battery_remaining_percent
    if threshold <= 0 or remaining is None or remaining > threshold or state.low_battery_landing_requested:
        return

    payload = {
        "battery_remaining_percent": remaining,
        "threshold_percent": threshold,
        "battery_message_type": state.last_battery_message_type,
        "action": "LAND",
    }

    try:
        request_land(master)
    except Exception as exc:
        payload["error"] = str(exc)
        recorder.write_event("CRITICAL_BATTERY_LAND_FAILED", payload)
        logger.error("Critical battery at %s%%, but LAND request failed: %s", remaining, exc)
        return

    state.low_battery_landing_requested = True
    recorder.write_event("CRITICAL_BATTERY_LAND_REQUESTED", payload)
    logger.warning(
        "Critical battery at %s%% (threshold %s%%); requested LAND to stop AUTO mission.",
        remaining,
        threshold,
    )


def maybe_report_verification(
    args: argparse.Namespace,
    expected: GpsFix,
    state: RuntimeState,
    logger: logging.Logger,
    elapsed_s: float,
) -> None:
    distance = verify_injected_point(state, expected, args.verify_tolerance_m)
    if state.injected_point_verified:
        return
    if elapsed_s < args.verify_after or state.injected_point_warning_sent:
        return

    if distance is None:
        logger.warning("ArduPilot has not reported a usable GPS_RAW_INT yet.")
    else:
        logger.warning(
            "ArduPilot GPS_RAW_INT is %.1fm from the injected point. Use --configure-sitl-gps-input and restart SITL.",
            distance,
        )
    state.injected_point_warning_sent = True


def summary_text(state: RuntimeState) -> str:
    battery = battery_summary(state)
    return (
        f"state armed={state.armed} mode={state.flight_mode} rx={state.messages_received} "
        f"tx_gps={state.gps_messages_sent} battery={battery} "
        f"land_requested={'yes' if state.low_battery_landing_requested else 'no'} "
        f"global_position={'yes' if state.last_global_position else 'no'} "
        f"gps_raw={'yes' if state.last_gps_raw else 'no'} simstate={'yes' if state.last_simstate else 'no'}"
    )


def battery_summary(state: RuntimeState) -> str:
    remaining = state.last_battery_remaining_percent
    if remaining is None:
        return "unknown"
    if state.last_battery_message_type is None:
        return f"{remaining}%"
    return f"{remaining}%/{state.last_battery_message_type}"
