# AP_FLAKE8_CLEAN
"""Battery status parsing helpers."""

from __future__ import annotations

from typing import Any


def battery_remaining_percent(msg: Any) -> int | None:
    raw_percent = getattr(msg, "battery_remaining", None)
    if raw_percent is None:
        return None

    try:
        percent = int(raw_percent)
    except (TypeError, ValueError):
        return None

    if not 0 <= percent <= 100:
        return None
    return percent
