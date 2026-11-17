from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


class Preferences(BaseModel):
    culture: float = Field(default=0.8, ge=0, le=1)
    history: float = Field(default=0.7, ge=0, le=1)
    food: float = Field(default=0.6, ge=0, le=1)
    nature: float = Field(default=0.5, ge=0, le=1)
    religion: float = Field(default=0.4, ge=0, le=1)
    shopping: float = Field(default=0.3, ge=0, le=1)
    photography: float = Field(default=0.4, ge=0, le=1)
    facilities: float = Field(default=0.5, ge=0, le=1)
    vehicle: float = Field(default=0.5, ge=0, le=1)


class PlanRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=160)
    destination: str = Field(min_length=2, max_length=160)
    departure_at: datetime | None = None
    detour_budget_minutes: int = Field(default=45, ge=0, le=360)
    max_journey_minutes: int = Field(default=720, ge=30, le=2880)
    max_stops: int = Field(default=4, ge=0, le=8)
    stop_duration_minutes: int = Field(default=30, ge=0, le=240)
    preferences: Preferences = Field(default_factory=Preferences)
    traveler_mode: Literal["balanced", "culture", "food", "nature", "family", "explorer"] = "balanced"
    # Preference-conditioned selection among already non-dominated Pareto plans.
    # 0 = efficiency-first, 1 = discovery-first; it does not change hard constraints.
    discovery_bias: float = Field(default=0.55, ge=0, le=1)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    poi_categories: list[Literal["heritage", "culture", "food", "nature", "religion", "shopping", "fuel", "ev_charging", "restroom", "medical", "vehicle_service", "parking", "rest_area"]] = Field(
        default_factory=lambda: ["heritage", "culture", "food", "nature", "religion", "shopping", "fuel", "ev_charging", "restroom", "medical", "vehicle_service", "parking", "rest_area"],
        min_length=1,
        max_length=13,
    )
    vehicle_type: Literal["not_set", "petrol", "diesel", "cng", "electric"] = "not_set"
    # Liquid fuel: litres/100 km or kg/100 km for CNG. Electric: kWh/100 km.
    consumption_per_100km: float | None = Field(default=None, gt=0, le=100)
    energy_price_per_unit: float | None = Field(default=None, gt=0, le=1000)

    @field_validator("origin", "destination")
    @classmethod
    def clean_location(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Location cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def different_endpoints(self):
        if self.origin.casefold() == self.destination.casefold():
            raise ValueError("Origin and destination must be different")
        if self.max_journey_minutes < self.detour_budget_minutes:
            raise ValueError("Maximum journey time must be at least the detour budget")
        if self.vehicle_type != "not_set" and (self.consumption_per_100km is None or self.energy_price_per_unit is None):
            raise ValueError("Enter both vehicle consumption and current price, or set vehicle type to not_set")
        if self.departure_at is not None:
            departure = self.departure_at
            if departure.tzinfo is None:
                departure = departure.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            if departure.astimezone(timezone.utc) < datetime.now(timezone.utc):
                raise ValueError("Departure time cannot be in the past")
        return self


class ReportRequest(BaseModel):
    category: Literal["accident", "road_damage", "flooding", "obstruction", "lighting", "closure", "traffic", "local_discovery", "facility_update"]
    description: str = Field(min_length=10, max_length=1200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observed_at: datetime | None = None


class ModerationRequest(BaseModel):
    status: Literal["under_review", "corroborated", "verified", "rejected", "expired"]
    moderator_note: str = Field(default="", max_length=1000)
    evidence_url: AnyHttpUrl | None = None


class WhatIfRequest(BaseModel):
    detour_budget_minutes: int | None = Field(default=None, ge=0, le=360)
    max_journey_minutes: int | None = Field(default=None, ge=30, le=2880)
    max_stops: int | None = Field(default=None, ge=0, le=8)
    stop_duration_minutes: int | None = Field(default=None, ge=0, le=240)
    discovery_bias: float | None = Field(default=None, ge=0, le=1)
    departure_at: datetime | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None

class RoutePreviewRequest(BaseModel):
    stop_ids: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("stop_ids")
    @classmethod
    def unique_stop_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("Stop identifiers cannot be blank")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Select each stop only once")
        return cleaned
