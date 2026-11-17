from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

_INDIA = ZoneInfo("Asia/Kolkata")
_DAY = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5, "Su": 6}


def _days_for_token(token: str) -> set[int] | None:
    token = token.strip()
    if token in _DAY:
        return {_DAY[token]}
    if "-" in token:
        left, right = token.split("-", 1)
        if left not in _DAY or right not in _DAY:
            return None
        out, day = set(), _DAY[left]
        while True:
            out.add(day)
            if day == _DAY[right]:
                break
            day = (day + 1) % 7
        return out
    return None


def parse_simple_opening_hours(raw: str | None) -> list[tuple[set[int], time, time]] | str | None:
    """Parse a safe subset of OSM opening_hours; return None for unknown syntax."""
    if not raw:
        return None
    if raw.strip() == "24/7":
        return "always"
    entries = []
    for part in raw.split(";"):
        match = re.fullmatch(r"\s*([A-Z][a-z](?:-[A-Z][a-z])?(?:,[A-Z][a-z](?:-[A-Z][a-z])?)*)\s+(\d{2}:\d{2})-(\d{2}:\d{2})\s*", part)
        if not match:
            return None
        days_token, start_token, end_token = match.groups()
        days: set[int] = set()
        for day_token in days_token.split(","):
            parsed = _days_for_token(day_token)
            if parsed is None:
                return None
            days.update(parsed)
        try:
            start = time.fromisoformat(start_token)
            end = time.fromisoformat(end_token)
        except ValueError:
            return None
        entries.append((days, start, end))
    return entries or None


def opening_status(raw: str | None, arrival: datetime | None) -> str:
    """Returns open, closed, or unknown. Unknown syntax is never treated as open."""
    parsed = parse_simple_opening_hours(raw)
    if parsed == "always":
        return "open"
    if parsed is None or arrival is None:
        return "unknown"
    local = arrival.astimezone(_INDIA) if arrival.tzinfo else arrival.replace(tzinfo=_INDIA)
    now_time = local.timetz().replace(tzinfo=None)
    for days, start, end in parsed:
        if local.weekday() in days:
            if start <= end and start <= now_time <= end:
                return "open"
            if start > end and now_time >= start:
                return "open"
        previous_day = (local.weekday() - 1) % 7
        if start > end and previous_day in days and now_time <= end:
            return "open"
    return "closed"
