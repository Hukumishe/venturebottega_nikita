"""Helpers for Dagospia API: parse window and keywords from query params."""

from __future__ import annotations

import re

WINDOW_PATTERN = re.compile(r"^\s*(\d+)\s*([hd]?)\s*$")


def parse_window_hours(raw_window: str) -> int:
    match = WINDOW_PATTERN.match(raw_window or "")
    if not match:
        raise ValueError("Invalid window format. Use values like 24h or 7d.")
    value = int(match.group(1))
    unit = match.group(2) or "h"
    if value <= 0:
        raise ValueError("Window must be a positive integer.")
    if unit == "d":
        value *= 24
    return max(1, min(value, 72))


def parse_keywords(keywords: str | None, keyword: list[str] | None) -> list[str]:
    parsed: list[str] = []
    if keywords:
        parsed.extend(part.strip() for part in keywords.split(",") if part.strip())
    if keyword:
        parsed.extend(part.strip() for part in keyword if part and part.strip())
    return parsed
