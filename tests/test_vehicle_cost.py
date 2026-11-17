import pytest
from pydantic import ValidationError

from app.engine.vehicle_cost import estimate_energy_cost
from app.schemas import PlanRequest


@pytest.mark.parametrize(
    ("vehicle", "consumption", "price", "unit", "expected_cost"),
    [
        ("petrol", 7.0, 105.0, "litre", 735.0),
        ("diesel", 5.0, 92.0, "litre", 460.0),
        ("cng", 4.0, 80.0, "kg", 320.0),
        ("electric", 15.0, 8.0, "kWh", 120.0),
    ],
)
def test_vehicle_cost_uses_only_user_supplied_efficiency_and_price(vehicle, consumption, price, unit, expected_cost):
    request = PlanRequest(
        origin="Delhi", destination="Agra", vehicle_type=vehicle,
        consumption_per_100km=consumption, energy_price_per_unit=price,
    )
    result = estimate_energy_cost(100, request)
    assert result["status"] == "estimated"
    assert result["unit"] == unit
    assert result["estimated_cost_inr"] == pytest.approx(expected_cost)


def test_vehicle_cost_is_not_guessed_without_vehicle_inputs():
    request = PlanRequest(origin="Delhi", destination="Agra")
    assert estimate_energy_cost(100, request) == {
        "status": "not_configured", "label": "Vehicle cost not configured"
    }


def test_vehicle_requires_both_efficiency_and_price():
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", vehicle_type="petrol", consumption_per_100km=7)
    with pytest.raises(ValidationError):
        PlanRequest(origin="Delhi", destination="Agra", vehicle_type="electric", energy_price_per_unit=8)
