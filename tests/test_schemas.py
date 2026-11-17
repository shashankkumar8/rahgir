from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas import PlanRequest, ReportRequest


def test_plan_request_normalises_location_and_rejects_same_endpoints():
    request = PlanRequest(origin="  New   Delhi ", destination="Agra")
    assert request.origin == "New Delhi"
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination=" delhi ")


def test_plan_request_rejects_invalid_budgets_and_stop_caps():
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", detour_budget_minutes=-1)
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", max_stops=9)


def test_plan_request_rejects_departure_in_past():
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", departure_at=datetime.now(timezone.utc) - timedelta(days=1))


def test_report_coordinates_and_text_are_validated():
    with pytest.raises(ValidationError):
        ReportRequest(category="flooding", description="tiny", latitude=28.6, longitude=77.2)
    with pytest.raises(ValidationError):
        ReportRequest(category="flooding", description="Water blocks the road", latitude=91, longitude=77.2)


def test_discovery_bias_is_bounded():
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", discovery_bias=1.01)
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", discovery_bias=-0.01)


def test_what_if_accepts_departure_replanning_timestamp():
    from app.schemas import WhatIfRequest
    from datetime import datetime, timezone
    request = WhatIfRequest(departure_at=datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc))
    assert request.departure_at is not None
