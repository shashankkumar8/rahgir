from datetime import datetime
from zoneinfo import ZoneInfo

from app.engine.temporal import opening_status, parse_simple_opening_hours


def test_24_7_is_always_open():
    assert opening_status("24/7", datetime(2026, 11, 17, 23, 59, tzinfo=ZoneInfo("Asia/Kolkata"))) == "open"


def test_weekday_opening_hours():
    # 2026-11-17 is Tuesday.
    dt = datetime(2026, 11, 17, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert opening_status("Mo-Fr 09:00-18:00", dt) == "open"
    assert opening_status("Mo-Fr 09:00-18:00", dt.replace(hour=20)) == "closed"


def test_unsupported_syntax_is_unknown_not_open():
    assert opening_status("sunrise-sunset", datetime.now(ZoneInfo("Asia/Kolkata"))) == "unknown"
    assert opening_status(None, datetime.now(ZoneInfo("Asia/Kolkata"))) == "unknown"


def test_opening_hours_parser_returns_unknown_for_complex_rule():
    assert parse_simple_opening_hours("PH off") is None
