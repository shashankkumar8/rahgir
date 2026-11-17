from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def evidence_completeness(tags: dict[str, Any]) -> float:
    """Metadata completeness proxy; deliberately not a truth probability/confidence."""
    keys = ("name", "tourism", "historic", "heritage", "amenity", "craft", "shop", "description", "website", "opening_hours")
    count = sum(1 for key in keys if tags.get(key))
    return round(count / len(keys), 4)


def evidence_record(source: str, source_url: str, retrieved_at: datetime | None = None, license_name: str = "ODbL") -> dict:
    return {
        "source": source,
        "source_url": source_url,
        "retrieved_at": (retrieved_at or datetime.now(timezone.utc)).isoformat(),
        "license": license_name,
    }


def safety_summary(reports: list[dict] | None = None) -> dict:
    """Community reports alone are not enough to make a positive safety assertion."""
    reports = reports or []
    verified = [r for r in reports if r.get("status") == "verified" and r.get("evidence_url")]
    if not verified:
        return {
            "status": "insufficient_evidence",
            "label": "Insufficient safety data",
            "verified_evidence_count": 0,
            "unverified_report_count": len(reports),
            "interpretation": "No verified, source-backed road-safety dataset is connected. Absence of reports is not evidence of safety.",
        }
    return {
        "status": "evidence_available_not_a_safety_rating",
        "label": "Verified incident evidence available",
        "verified_evidence_count": len(verified),
        "unverified_report_count": len(reports) - len(verified),
        "interpretation": "These are source-backed reports, not a probability of safety or a guarantee that the road is safe.",
    }
