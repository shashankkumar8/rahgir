from __future__ import annotations

import hashlib
import hmac
import io
import json
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import CommunityReport, SessionLocal, SharedTrip, TripRecord, get_session, init_db, serialise_trip
from .engine.geometry import haversine_m
from .engine.planner import RoutePlanner
from .schemas import ModerationRequest, PlanRequest, ReportRequest, WhatIfRequest, RoutePreviewRequest, AskTripRequest
from .services.demo import DEMO_CASES, DemoProviders, get_demo_case
from .services.providers import ExternalProviders, ProviderError
from .services.assistant import answer_trip_question


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Rahgir Road-Trip Intelligence",
    description="Evidence-aware, route-corridor POI discovery and deterministic multi-objective itinerary planning.",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.middleware("http")
async def request_guard(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and request.method in {"POST", "PUT", "PATCH"}:
        try:
            if int(content_length) > settings.max_request_bytes:
                return Response(content='{"error":"request_too_large","detail":"Request body exceeds configured limit."}', status_code=413, media_type="application/json")
        except ValueError:
            return Response(content='{"error":"invalid_content_length","detail":"Invalid Content-Length header."}', status_code=400, media_type="application/json")
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


def _admin_check(token: str | None) -> None:
    if not settings.admin_token or not token or not hmac.compare_digest(settings.admin_token, token):
        raise HTTPException(status_code=403, detail="Administrative action is not authorised. Configure ADMIN_TOKEN and provide X-Admin-Token.")


def _save_trip(session: Session, request_model: PlanRequest, result: dict[str, Any], *, case_id: str | None = None) -> dict[str, Any]:
    trip_id = str(uuid.uuid4())
    payload = request_model.model_dump(mode="json")
    if case_id:
        payload["_demo_case_id"] = case_id
    result["trip_id"] = trip_id
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    record = TripRecord(
        id=trip_id,
        origin=request_model.origin,
        destination=request_model.destination,
        request_json=json.dumps(payload, ensure_ascii=False),
        result_json=json.dumps(result, ensure_ascii=False),
    )
    session.add(record)
    session.commit()
    return {"trip_id": trip_id, "result": result}


async def _run_live_plan(request_model: PlanRequest) -> dict[str, Any]:
    providers = ExternalProviders()
    try:
        return await RoutePlanner(providers).plan(request_model)
    finally:
        await providers.close()


async def _run_demo_plan(request_model: PlanRequest, case_id: str) -> dict[str, Any]:
    case = get_demo_case(case_id)
    if request_model.origin.casefold() != case["origin"].casefold() or request_model.destination.casefold() != case["destination"].casefold():
        raise HTTPException(status_code=422, detail="Demo trip origin and destination must match the selected demo case.")
    return await RoutePlanner(DemoProviders(case)).plan(request_model)


@app.get("/shared/{token}", include_in_schema=False)
def shared_page(token: str):
    return FileResponse(STATIC_DIR / "share.html")


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "service": "rahgir-api",
        "version": app.version,
        "environment": settings.app_env,
        "routing_provider_configured": settings.routing_provider,
        "geocoder_provider_configured": settings.geocoder_provider,
        "overpass_configured": bool(settings.overpass_url),
        "external_providers_probed": False,
        "trip_assistant": "openrouter_configured" if settings.openrouter_api_key else "grounded_local_mode",
        "wikipedia_enrichment": settings.wikipedia_enrichment,
        "note": "Health confirms process readiness only; external providers are checked when a trip is planned.",
    }


@app.get("/api/v1/demo/cases")
def demo_cases():
    if not settings.allow_demo:
        raise HTTPException(status_code=404, detail="Demo mode is disabled")
    return {"mode": "synthetic_demo", "warning": "All POIs, road geometry and costs in these walkthrough cases are synthetic. Never use them for navigation, safety decisions or research results.", "cases": [
        {"id": c["id"], "origin": c["origin"], "destination": c["destination"], "region": c["region"]} for c in DEMO_CASES
    ]}


@app.post("/api/v1/trips/plan")
async def plan_trip(body: PlanRequest, session: Session = Depends(get_session)):
    try:
        result = await _run_live_plan(body)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail={"provider": exc.provider, "message": str(exc), "status_code": exc.status_code}) from exc
    return _save_trip(session, body, result)


@app.post("/api/v1/demo/plan")
async def plan_demo_trip(body: PlanRequest, case_id: str, session: Session = Depends(get_session)):
    if not settings.allow_demo:
        raise HTTPException(status_code=404, detail="Demo mode is disabled")
    try:
        result = await _run_demo_plan(body, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown demo case") from exc
    return _save_trip(session, body, result, case_id=case_id)


@app.get("/api/v1/trips/{trip_id}")
def get_trip(trip_id: str, session: Session = Depends(get_session)):
    record = session.get(TripRecord, trip_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trip not found")
    return serialise_trip(record)


async def _recompute_trip(trip_id: str, changes: dict[str, Any] | None, session: Session):
    record = session.get(TripRecord, trip_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trip not found")
    raw_request = json.loads(record.request_json)
    case_id = raw_request.pop("_demo_case_id", None)
    if changes:
        raw_request.update({k: v for k, v in changes.items() if v is not None})
    try:
        plan_request = PlanRequest(**raw_request)
        if case_id:
            result = await _run_demo_plan(plan_request, case_id)
        else:
            result = await _run_live_plan(plan_request)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail={"provider": exc.provider, "message": str(exc), "status_code": exc.status_code}) from exc
    return _save_trip(session, plan_request, result, case_id=case_id)


@app.post("/api/v1/trips/{trip_id}/replan")
async def replan_trip(trip_id: str, session: Session = Depends(get_session)):
    return await _recompute_trip(trip_id, None, session)


@app.post("/api/v1/trips/{trip_id}/what-if")
async def what_if_trip(trip_id: str, body: WhatIfRequest, session: Session = Depends(get_session)):
    return await _recompute_trip(trip_id, body.model_dump(exclude_unset=True), session)




@app.post("/api/v1/trips/{trip_id}/ask")
async def ask_trip_question(trip_id: str, body: AskTripRequest, session: Session = Depends(get_session)):
    record = session.get(TripRecord, trip_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trip not found")
    result = json.loads(record.result_json)
    answer = await answer_trip_question(body.question.strip(), body.history, result)
    return answer


@app.post("/api/v1/trips/{trip_id}/route-preview")
async def preview_alternative_route(trip_id: str, body: RoutePreviewRequest, session: Session = Depends(get_session)):
    record = session.get(TripRecord, trip_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trip not found")
    result = json.loads(record.result_json)
    origin = result.get("origin", {})
    destination = result.get("destination", {})
    if origin.get("latitude") is None or destination.get("latitude") is None or origin.get("longitude") is None or destination.get("longitude") is None:
        raise HTTPException(status_code=422, detail="Stored trip is missing endpoint coordinates")
    allowed = {}
    for alternative in result.get("alternatives", []):
        for stop in alternative.get("stops", []):
            allowed[stop["id"]] = stop
    if any(stop_id not in allowed for stop_id in body.stop_ids):
        raise HTTPException(status_code=422, detail="One or more selected stops are not part of this trip's computed alternatives")
    stop_rows = [allowed[x] for x in body.stop_ids]
    # Keep itinerary stops in the same along-route order used by the optimizer.
    stop_rows.sort(key=lambda x: next((p.get("route_progress", 0) for p in result.get("candidates", []) if p.get("id") == x["id"]), 0))
    coordinates = [(float(origin["latitude"]), float(origin["longitude"]))]
    coordinates += [(float(x["latitude"]), float(x["longitude"])) for x in stop_rows]
    coordinates += [(float(destination["latitude"]), float(destination["longitude"]))]
    raw_request = json.loads(record.request_json)
    case_id = raw_request.get("_demo_case_id")
    providers = DemoProviders(get_demo_case(case_id)) if case_id else ExternalProviders()
    try:
        route = await providers.route(coordinates)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail={"provider": exc.provider, "message": str(exc)}) from exc
    finally:
        if isinstance(providers, ExternalProviders):
            await providers.close()
    return {"provider": route["provider"], "geometry": route["geometry"], "distance_km": round(route["distance_m"] / 1000, 2), "duration_minutes": round(route["duration_s"] / 60, 1), "stop_ids": body.stop_ids}


@app.post("/api/v1/reports")
def create_report(body: ReportRequest, request: Request, session: Session = Depends(get_session)):
    # Store a rotating one-way fingerprint, not a raw IP address.
    ip = request.client.host if request.client else "unknown"
    day = datetime.now(timezone.utc).date().isoformat()
    fingerprint = hashlib.sha256(f"{ip}:{day}:rahgir-report-rate-limit".encode()).hexdigest()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = session.scalars(select(CommunityReport).where(CommunityReport.reporter_fingerprint == fingerprint, CommunityReport.created_at >= cutoff)).all()
    if len(recent) >= 5:
        raise HTTPException(status_code=429, detail="Report limit reached for this network in the last hour. Try later.")
    # Flag near-identical recent observations for moderator review; never treat a
    # duplicate or a corroboration count as independent factual verification.
    duplicate_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_same_category = session.scalars(
        select(CommunityReport).where(
            CommunityReport.category == body.category,
            CommunityReport.created_at >= duplicate_cutoff,
        ).order_by(CommunityReport.created_at.desc()).limit(500)
    ).all()
    duplicate_of = next((
        old.id for old in recent_same_category
        if haversine_m((body.latitude, body.longitude), (old.latitude, old.longitude)) <= 150
        and old.description.casefold() == body.description.strip().casefold()
    ), None)
    item = CommunityReport(
        category=body.category, description=body.description.strip(), latitude=body.latitude,
        longitude=body.longitude, observed_at=body.observed_at, status="submitted", reporter_fingerprint=fingerprint,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": item.id, "status": item.status, "duplicate_of": duplicate_of, "possible_duplicate": duplicate_of is not None, "created_at": item.created_at.isoformat(), "message": "Report received. It is not verified and is not used to label a road safe or unsafe."}


@app.get("/api/v1/reports")
def list_reports(latitude: float | None = None, longitude: float | None = None, radius_km: float = 15, session: Session = Depends(get_session)):
    if radius_km <= 0 or radius_km > 100:
        raise HTTPException(status_code=422, detail="radius_km must be greater than 0 and at most 100")
    reports = session.scalars(select(CommunityReport).order_by(CommunityReport.created_at.desc()).limit(500)).all()
    output = []
    for item in reports:
        distance = None
        if latitude is not None and longitude is not None:
            distance = haversine_m((latitude, longitude), (item.latitude, item.longitude)) / 1000
            if distance > radius_km:
                continue
        output.append({
            "id": item.id, "category": item.category, "description": item.description,
            "latitude": item.latitude, "longitude": item.longitude,
            "observed_at": item.observed_at.isoformat() if item.observed_at else None,
            "created_at": item.created_at.isoformat(), "status": item.status,
            "distance_km": round(distance, 2) if distance is not None else None,
        })
    return {"reports": output, "note": "Reports are community submissions. Submitted/corroborated entries are unverified; manual source-backed review is required."}


@app.post("/api/v1/reports/{report_id}/moderate")
def moderate_report(report_id: int, body: ModerationRequest, x_admin_token: str | None = Header(default=None), session: Session = Depends(get_session)):
    _admin_check(x_admin_token)
    item = session.get(CommunityReport, report_id)
    if not item:
        raise HTTPException(status_code=404, detail="Report not found")
    if body.status == "verified" and not body.evidence_url:
        raise HTTPException(status_code=422, detail="A source URL is required before a report can be marked verified")
    item.status = body.status
    item.moderator_note = body.moderator_note
    item.evidence_url = str(body.evidence_url) if body.evidence_url else None
    session.commit()
    return {"id": item.id, "status": item.status, "evidence_url": item.evidence_url, "message": "Moderation action recorded. Verification is not a statistical risk score."}


@app.post("/api/v1/trips/{trip_id}/share")
def create_share(trip_id: str, session: Session = Depends(get_session)):
    if not session.get(TripRecord, trip_id):
        raise HTTPException(status_code=404, detail="Trip not found")
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session.add(SharedTrip(trip_id=trip_id, token_hash=token_hash))
    session.commit()
    return {"share_url": f"/shared/{token}", "token": token, "note": "Anyone with this unguessable link can view the read-only itinerary. Do not share private notes or live location."}


@app.get("/api/v1/shared/{token}")
def read_shared_trip(token: str, session: Session = Depends(get_session)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    shared = session.scalar(select(SharedTrip).where(SharedTrip.token_hash == token_hash, SharedTrip.revoked_at.is_(None)))
    if not shared:
        raise HTTPException(status_code=404, detail="Share link is invalid or has been revoked")
    record = session.get(TripRecord, shared.trip_id)
    if not record:
        raise HTTPException(status_code=404, detail="Shared trip no longer exists")
    item = serialise_trip(record)
    return {"id": item["id"], "origin": item["origin"], "destination": item["destination"], "created_at": item["created_at"], "result": item["result"], "access": "read_only"}


@app.delete("/api/v1/trips/{trip_id}/share/{token}")
def revoke_share(trip_id: str, token: str, session: Session = Depends(get_session)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    shared = session.scalar(select(SharedTrip).where(SharedTrip.trip_id == trip_id, SharedTrip.token_hash == token_hash, SharedTrip.revoked_at.is_(None)))
    if not shared:
        raise HTTPException(status_code=404, detail="Active share link not found")
    shared.revoked_at = datetime.now(timezone.utc)
    session.commit()
    return {"revoked": True}


@app.get("/api/v1/trips/{trip_id}/export.pdf")
def export_pdf(trip_id: str, session: Session = Depends(get_session)):
    record = session.get(TripRecord, trip_id)
    if not record:
        raise HTTPException(status_code=404, detail="Trip not found")
    payload = serialise_trip(record)
    result = payload["result"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph("RAHGIR — Road-trip itinerary", styles["Title"]), Spacer(1, 10)]
    story.append(Paragraph(f"{payload['origin']} to {payload['destination']}", styles["Heading2"]))
    story.append(Paragraph(f"Trip ID: {payload['id']} | Mode: {result.get('mode', 'unknown')}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    route = result.get("route", {})
    data = [["Route distance", "Drive time", "Data source"], [f"{route.get('distance_km', '—')} km", f"{route.get('duration_minutes', '—')} min", str(route.get("provider", "—"))]]
    table = Table(data, colWidths=[150, 130, 180])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2933")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dbe1")), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.append(table)
    story.append(Spacer(1, 16))
    selected = result.get("selected_alternative") or {}
    story.append(Paragraph(f"Selected alternative: {selected.get('label', 'None')}", styles["Heading2"]))
    for idx, stop in enumerate(selected.get("stops", []), 1):
        story.append(Paragraph(f"{idx}. {stop.get('name')} ({stop.get('category')})", styles["Heading3"]))
        story.append(Paragraph(f"Arrival: {stop.get('arrival_at') or 'not estimated'} | Hours: {stop.get('hours_status', 'unknown')} | Source: {stop.get('source_url', 'not supplied')}", styles["BodyText"]))
        story.append(Paragraph("Why: " + "; ".join(stop.get("explanation", [])), styles["BodyText"]))
        story.append(Spacer(1, 6))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Safety: Insufficient safety data. No positive safety guarantee is provided.", styles["BodyText"]))
    if result.get("mode") == "synthetic_demo":
        story.append(Paragraph("DEMO WARNING: Synthetic data only. Not for navigation, field use, safety decisions or research results.", styles["Heading2"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Map data and POIs are subject to their source licence and attribution. Verify opening hours and local conditions before departure.", styles["Italic"]))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="rahgir-{trip_id[:8]}.pdf"'})


@app.get("/api/v1/research/experiments")
def research_index():
    return {
        "framework": "Rahgir reproducible research harness",
        "algorithm": "NSGA-II binary selection over route-corridor POIs with fixed route-progression order",
        "baselines": ["nearest-feasible", "weighted-greedy", "NSGA-II"],
        "metrics": ["hypervolume", "inverted generational distance", "feasibility rate", "runtime_ms", "average_selected_pois"],
        "dataset_policy": "Synthetic algorithm fixtures are separate from live OSM route records; no experiment output is a field-study result.",
        "run_command": "python -m research.run_experiments --seeds 10 --instances 30 --output research/results",
        "paper_draft": "research/paper/rahgir_paper_draft.tex",
    }
