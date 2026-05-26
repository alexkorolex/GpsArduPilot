# AP_FLAKE8_CLEAN
"""Small helpers for safe MAVLink message serialization."""

from __future__ import annotations

import time
from typing import Any


def safe_message_type(msg: Any) -> str:
    try:
        return str(msg.get_type())
    except Exception:
        return type(msg).__name__


def safe_message_dict(msg: Any) -> dict[str, Any]:
    try:
        return to_jsonable(msg.to_dict())
    except Exception as exc:
        return {"error": f"to_dict failed: {exc}", "repr": repr(msg)}


def safe_raw_hex(msg: Any) -> str | None:
    try:
        raw = msg.get_msgbuf()
    except Exception:
        return None
    if isinstance(raw, bytes):
        return raw.hex()
    return None


def safe_call(callback: Any) -> Any:
    try:
        return callback()
    except Exception:
        return None


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return str(value)


def iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
