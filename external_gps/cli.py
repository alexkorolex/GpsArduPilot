# AP_FLAKE8_CLEAN
"""CLI and runtime loop for the GPS_INPUT injector."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Callable

from pymavlink import mavutil

from external_gps.mavlink_io import (
    configure_sitl_for_gps_input,
    disable_sitl_mag_field_check,
    maybe_request_data_stream,
    read_pending_messages,
    send_gps_input,
    send_set_home,
    verify_injected_point,
)
from external_gps.models import GpsFix, RandomPointConfig, RuntimeState, gps_input_payload
from external_gps.providers import (
    DemoLineGpsProvider,
    GpsProvider,
    RandomPointGpsProvider,
    SimStateOffsetGpsProvider,
    StaticGpsProvider,
)
from external_gps.recorder import MavlinkJsonlRecorder


def build_logger(level: str) -> logging.Logger:
    logger = logging.getLogger("external_gps")
    logger.setLevel(level.upper())
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPS_INPUT injector with random point support for ArduPilot SITL.")
    parser.add_argument("--connect", default="udpin:0.0.0.0:14560", help="MAVLink connection string.")
    parser.add_argument("--interval", type=float, default=0.2, help="GPS_INPUT interval in seconds; 0.2 = 5 Hz.")
    parser.add_argument("--stream-rate-hz", type=int, default=5, help="Request MAVLink stream rate. 0 disables request.")

    parser.add_argument("--static-lat", type=float, default=55.0, help="Static/base latitude.")
    parser.add_argument("--static-lon", type=float, default=37.0, help="Static/base longitude.")
    parser.add_argument("--static-alt", type=float, default=50.0, help="Static/base MSL altitude in metres.")
    parser.add_argument("--satellites", type=int, default=10, help="Satellites visible in GPS_INPUT.")

    parser.add_argument(
        "--provider",
        choices=["static", "random-point", "random-simstate", "demo-line"],
        default="random-simstate",
        help="GPS source: random-simstate follows SITL movement from a random start point.",
    )
    parser.add_argument("--random-radius-min", type=float, default=0.0, help="Minimum random offset from base, metres.")
    parser.add_argument("--random-radius-max", type=float, default=100.0, help="Maximum random offset from base, metres.")
    parser.add_argument("--random-seed", type=int, default=None, help="Seed for reproducible random points.")
    parser.add_argument("--demo-north-speed", type=float, default=0.0, help="North speed for demo-line provider, m/s.")
    parser.add_argument("--demo-east-speed", type=float, default=0.0, help="East speed for demo-line provider, m/s.")

    parser.add_argument("--configure-sitl-gps-input", action="store_true", help="Set GPS1_TYPE=14 and SIM_GPS1_ENABLE=0.")
    parser.add_argument(
        "--disable-sitl-mag-field-check",
        action="store_true",
        help="SITL only: set ARMING_MAGTHRESH=0 for shifted synthetic GPS locations.",
    )
    parser.add_argument("--set-home", action="store_true", help="Send MAV_CMD_DO_SET_HOME for the selected point.")
    parser.add_argument("--verify-after", type=float, default=8.0, help="Seconds before warning if point is not accepted.")
    parser.add_argument("--verify-tolerance-m", type=float, default=10.0, help="GPS_RAW_INT distance accepted as matching.")

    parser.add_argument("--mavlink-log", type=Path, default=Path("logs/mavlink_messages.jsonl"), help="JSONL log path.")
    parser.add_argument("--mavlink-log-flush-every", type=int, default=1, help="Flush JSONL after N records.")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    parser.add_argument("--summary-every", type=float, default=2.0, help="Console summary interval in seconds.")
    return parser.parse_args(argv)


def build_provider(args: argparse.Namespace, state: RuntimeState | None = None) -> GpsProvider:
    start = GpsFix(
        lat=args.static_lat,
        lon=args.static_lon,
        alt_m=args.static_alt,
        satellites=args.satellites,
    )

    if args.provider == "demo-line":
        return DemoLineGpsProvider(start, args.demo_north_speed, args.demo_east_speed)

    if args.provider in {"random-point", "random-simstate"}:
        random_provider = RandomPointGpsProvider(random_config_from_args(args))
        if args.provider == "random-simstate":
            if state is None:
                raise ValueError("random-simstate provider requires RuntimeState")
            return SimStateOffsetGpsProvider(random_provider.start_fix, state)
        return random_provider

    return StaticGpsProvider(start)


def random_config_from_args(args: argparse.Namespace) -> RandomPointConfig:
    return RandomPointConfig(
        base_lat=args.static_lat,
        base_lon=args.static_lon,
        base_alt_m=args.static_alt,
        min_radius_m=args.random_radius_min,
        max_radius_m=args.random_radius_max,
        satellites=args.satellites,
        seed=args.random_seed,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logger = build_logger(args.log_level)
    state = RuntimeState()
    provider = build_provider(args, state)
    should_stop = False

    def handle_stop(signum: int, frame: object) -> None:
        nonlocal should_stop
        should_stop = True
        logger.info("Stop signal received: %s", signum)

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    logger.info("Connecting to %s", args.connect)
    master = mavutil.mavlink_connection(args.connect)
    logger.info("Waiting for heartbeat...")
    master.wait_heartbeat()
    logger.info("Heartbeat received: system=%s component=%s", master.target_system, master.target_component)

    if args.configure_sitl_gps_input:
        configure_sitl_for_gps_input(master, logger)
        logger.warning("If these parameters changed, restart SITL before expecting GPS_INPUT to become primary GPS.")
    if args.disable_sitl_mag_field_check:
        disable_sitl_mag_field_check(master, logger)

    maybe_request_data_stream(master, args.stream_rate_hz, logger)

    with MavlinkJsonlRecorder(args.mavlink_log, args.mavlink_log_flush_every) as recorder:
        log_start(recorder, args, provider.start_fix)
        logger.info(
            "Selected injected point: lat=%.7f lon=%.7f alt=%.1fm",
            provider.start_fix.lat,
            provider.start_fix.lon,
            provider.start_fix.alt_m,
        )
        if args.set_home:
            send_set_home(master, provider.start_fix)
            recorder.write_event("SET_HOME_SENT", gps_input_payload(provider.start_fix))

        run_loop(args, master, provider, state, recorder, logger, should_stop_getter=lambda: should_stop)

    logger.info("Stopped. MAVLink JSONL log: %s", args.mavlink_log)


def log_start(recorder: MavlinkJsonlRecorder, args: argparse.Namespace, fix: GpsFix) -> None:
    recorder.write_event("SCRIPT_STARTED", {"args": vars(args)})
    recorder.write_event("SELECTED_POINT", gps_input_payload(fix))


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
    return (
        f"state armed={state.armed} mode={state.flight_mode} rx={state.messages_received} "
        f"tx_gps={state.gps_messages_sent} global_position={'yes' if state.last_global_position else 'no'} "
        f"gps_raw={'yes' if state.last_gps_raw else 'no'} simstate={'yes' if state.last_simstate else 'no'}"
    )
