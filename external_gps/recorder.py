# AP_FLAKE8_CLEAN
"""JSONL recorder for MAVLink traffic and app events."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, TextIO

from external_gps.message_utils import (
    iso_utc_now,
    safe_call,
    safe_message_dict,
    safe_message_type,
    safe_raw_hex,
    to_jsonable,
)
from external_gps.models import GpsFix, gps_input_payload


class MavlinkJsonlRecorder:
    """Writes incoming/outgoing MAVLink data as newline-delimited JSON."""

    def __init__(self, path: Path | None, flush_every: int = 1) -> None:
        self._path = path
        self._flush_every = max(flush_every, 1)
        self._file: TextIO | None = None
        self._pending_flushes = 0

    def __enter__(self) -> MavlinkJsonlRecorder:
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self._path.open("a", encoding="utf-8", buffering=1)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None

    def write_incoming(self, msg: Any) -> None:
        if self._file is None:
            return

        self._write(
            {
                "wall_time_unix_s": time.time(),
                "wall_time_iso": iso_utc_now(),
                "monotonic_s": time.monotonic(),
                "direction": "rx",
                "type": safe_message_type(msg),
                "src_system": safe_call(lambda: msg.get_srcSystem()),
                "src_component": safe_call(lambda: msg.get_srcComponent()),
                "raw_hex": safe_raw_hex(msg),
                "message": safe_message_dict(msg),
            }
        )

    def write_outgoing_gps_input(self, fix: GpsFix) -> None:
        self.write_event("GPS_INPUT", gps_input_payload(fix), direction="tx")

    def write_event(self, event: str, payload: dict[str, Any], direction: str = "event") -> None:
        if self._file is None:
            return

        self._write(
            {
                "wall_time_unix_s": time.time(),
                "wall_time_iso": iso_utc_now(),
                "monotonic_s": time.monotonic(),
                "direction": direction,
                "type": event,
                "message": payload,
            }
        )

    def _write(self, record: dict[str, Any]) -> None:
        assert self._file is not None
        self._file.write(json.dumps(to_jsonable(record), ensure_ascii=False, separators=(",", ":")) + "\n")
        self._pending_flushes += 1
        if self._pending_flushes >= self._flush_every:
            self._file.flush()
            self._pending_flushes = 0
