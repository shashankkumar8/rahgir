"""Chromium end-to-end smoke test for Rahgir's deterministic trip workflow.

The walkthrough provider is synthetic and test-only. A separate provider-error
case verifies the live form displays a real backend failure without demo fallback.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(tempfile.gettempdir()) / f"rahgir-browser-smoke-{os.getpid()}.db"
DB_PATH.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
sys.path.insert(0, str(ROOT_DIR / "backend"))
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from app.main import app

STATIC = ROOT_DIR / "backend" / "app" / "static"
OUT = Path("/mnt/data/rahgir-v3-spec")
OUT.mkdir(parents=True, exist_ok=True)
report = {"console_errors": [], "page_errors": [], "checks": [], "requests": {}}


def route_handler(route):
    request = route.request
    path = urlsplit(request.url).path
    if path.startswith("/static/"):
        asset = STATIC / Path(path).name
        if not asset.is_file() or asset.parent != STATIC:
            route.fulfill(status=404, body="Static asset not found")
            return
        content_type = "application/javascript; charset=utf-8" if asset.suffix == ".js" else "text/css; charset=utf-8"
        route.fulfill(status=200, content_type=content_type, body=asset.read_text())
        return
    if path.startswith("/api/") or path.startswith("/shared/"):
        body = request.post_data
        if path.endswith("/demo/plan") and body:
            report["requests"]["demo_plan"] = json.loads(body)
        if path.endswith("/route-preview") and body:
            report["requests"]["route_preview"] = json.loads(body)
        headers = {k: v for k, v in request.headers.items() if k.lower() in {"content-type", "x-admin-token"}}
        report["requests"].setdefault(path, 0)
        report["requests"][path] += 1
        response = client.request(
            request.method,
            path + (("?" + urlsplit(request.url).query) if urlsplit(request.url).query else ""),
            content=body,
            headers=headers,
        )
        route.fulfill(
            status=response.status_code,
            content_type=response.headers.get("content-type", "application/json"),
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": "content-type,x-admin-token",
            },
            body=response.content,
        )
        return
    route.fulfill(status=204, body=b"")


html = (STATIC / "index.html").read_text()
css = (STATIC / "styles.css").read_text()
workspace_css = (STATIC / "workspace.css").read_text()
storage_shim = """<script>
(() => {
  const data = new Map();
  const store = {
    getItem: key => data.has(String(key)) ? data.get(String(key)) : null,
    setItem: (key, value) => data.set(String(key), String(value)),
    removeItem: key => data.delete(String(key)),
    clear: () => data.clear()
  };
  Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async value => { window.__rahgirCopied = String(value); } } });
})();
</script>"""
html = html.replace("<head>", '<head><base href="http://rahgir.local/">' + storage_shim + "<style>" + css + "\n" + workspace_css + "</style>")
import re
html = re.sub(r'<link rel="preconnect" href="https://unpkg.com" />', "", html)
html = re.sub(r'<link rel="preconnect" href="https://tile.openstreetmap.org" />', "", html)
html = re.sub(r'<link rel="stylesheet" href="https://unpkg.com/[^>]+>', "", html)
html = re.sub(r'<link rel="stylesheet" href="/static/(?:styles|workspace)\.css" />', "", html)
html = re.sub(r'<script defer src="https://unpkg.com/[^>]+></script>', "", html)

client = TestClient(app)
with client:
    with sync_playwright() as p:
        executable = shutil.which("chromium") or shutil.which("chromium-browser")
        launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable:
            launch["executable_path"] = executable
        browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        context.route("**/*", route_handler)
        page = context.new_page()
        page.set_default_timeout(7000)
        page.set_default_navigation_timeout(10000)
        page.on("console", lambda msg: report["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: report["page_errors"].append(str(exc)))
        page.set_content(html, wait_until="load", timeout=30000)
        report["checks"].append({"homepage_loaded": True, "plan_form_visible": page.locator("#plan-form").is_visible()})

        # User-entered vehicle efficiency and unit price must flow into the request.
        page.locator(".advanced-options summary").click()
        page.locator("#vehicle-type").select_option("petrol")
        page.locator("#vehicle-type").select_option("petrol")
        page.locator("#vehicle-consumption").fill("7.5")
        page.locator("#vehicle-price").fill("105")
        page.locator("#origin").fill("Delhi")
        page.locator("#destination").fill("Agra")
        page.locator("#swap-locations").click()
        swapped = page.locator("#origin").input_value() == "Agra" and page.locator("#destination").input_value() == "Delhi"
        page.locator("#swap-locations").click()
        page.locator('[data-vibe="nature"]').click()
        page.locator("#demo-case").select_option("delhi-agra")
        page.locator("#demo-button").click()
        page.wait_for_selector("#results:not([hidden])", timeout=15000)
        report["checks"].append({
            "synthetic_demo_explicitly_labelled": page.locator("#demo-banner").is_visible(),
            "workspace_shell_active": page.locator("body").evaluate("el => el.classList.contains('workspace-active')"),
            "map_moved_into_workspace": page.locator("#map-card").evaluate("el => el.parentElement.id") == "workspace-map-slot",
            "pareto_options_rendered": page.locator(".alternative-card").count() > 0,
            "selected_route_proof_present": len(page.locator("#route-proof-result").inner_text()) > 0,
            "vehicle_inputs_and_location_swap_work": swapped and report["requests"]["demo_plan"].get("vehicle_type") == "petrol" and report["requests"]["demo_plan"].get("consumption_per_100km") == 7.5,
            "selected_vibe_reaches_planner": report["requests"]["demo_plan"].get("preferences", {}).get("nature", 0) >= 0.9,
        })

        # Alternative selection must perform a fresh full-route check when the
        # option has no stored provider validation.
        alternative_cards = page.locator(".alternative-card")
        if alternative_cards.count() > 1:
            previous_checks = sum(value for key, value in report["requests"].items() if key.endswith("/route-preview") and isinstance(value, int))
            alternative_cards.nth(1).click()
            page.wait_for_function("!document.querySelector('#feasible-chip').textContent.includes('Checking')", timeout=10000)
            report["checks"].append({"pareto_option_can_be_selected": "itinerary" in page.locator("#selected-label").inner_text().lower(), "alternate_route_rechecked": sum(value for key, value in report["requests"].items() if key.endswith("/route-preview") and isinstance(value, int)) > previous_checks})
        page.locator('[data-workspace="routes"]').click()
        all_count = page.locator(".candidate-card").count()
        page.locator('[data-filter="facilities"]').click()
        facility_count = page.locator(".candidate-card").count()
        report["checks"].append({"facility_filter_operates": facility_count > 0 and facility_count <= all_count})
        page.locator('[data-locate]').first.click()
        report["checks"].append({"schematic_candidate_can_be_located": page.locator(".schematic-candidate.focused").count() == 1})
        page.locator("#fit-map").click()
        report["checks"].append({"schematic_fit_action_works": page.locator("#route-map svg").get_attribute("viewBox") == "0 0 800 460"})
        first_checkbox = page.locator('[data-custom-select]').first
        first_checkbox.check()
        report["checks"].append({"custom_stop_selection_updates_count": "1 custom stops selected" in page.locator("#custom-stop-count").inner_text()})
        page.locator("#validate-custom-route").click()
        page.wait_for_selector("#custom-route-result .route-validation-summary", timeout=15000)
        report["checks"].append({
            "custom_route_calls_provider_validation": "Complete route" in page.locator("#custom-route-result").inner_text(),
            "route_preview_request_recorded": bool(report["requests"].get("route_preview")),
        })
        custom_status = page.locator("#custom-route-result").inner_text()
        if "CONFIRMED FEASIBLE" in custom_status:
            page.locator("#apply-custom-route").click()
            report["checks"].append({"validated_custom_route_can_be_applied": page.locator("#selected-label").inner_text() == "Custom route itinerary"})
        else:
            report["checks"].append({"infeasible_custom_route_is_not_applicable": page.locator("#apply-custom-route").is_disabled()})

        page.locator('[data-filter="all"]').click()
        all_count = page.locator(".candidate-card").count()
        page.locator('[data-filter="food"]').click()
        food_count = page.locator(".candidate-card").count()
        page.locator('[data-filter="all"]').click()
        page.locator("#workspace-search").fill("museum")
        search_count = page.locator(".candidate-card").count()
        page.locator("#workspace-search").fill("")
        report["checks"].append({"category_filter_operates": food_count <= all_count, "search_operates": search_count <= all_count})


        # Recompute a what-if rather than merely changing the slider label.
        page.locator("#whatif-budget").fill("0")
        page.locator("#whatif-budget").dispatch_event("input")
        page.locator("#whatif-button").click()
        page.wait_for_function("document.querySelector('#toast').textContent.includes('What-if run complete')", timeout=10000)
        report["checks"].append({"what_if_api_called": any("/what-if" in key for key in report["requests"])})

        # Share creates a real token-backed read-only server URL and copies it.
        page.locator("#share-trip").click()
        page.wait_for_function("Boolean(window.__rahgirCopied)", timeout=8000)
        report["checks"].append({"share_link_created_and_copied": "/shared/" in page.evaluate("window.__rahgirCopied")})

        # PDF export is requested from the actual API; verify the returned bytes.
        page.evaluate("window.open = (url) => { window.__rahgirPdfUrl = String(url); window.__rahgirPdfPromise = fetch(url).then(async r => ({status:r.status, type:r.headers.get('content-type'), prefix:Array.from(new Uint8Array(await r.arrayBuffer()).slice(0,4))})); return null; }")
        page.locator("#export-trip").click()
        page.wait_for_function("Boolean(window.__rahgirPdfPromise)", timeout=5000)
        pdf_result = page.evaluate("async () => await window.__rahgirPdfPromise")
        report["checks"].append({"pdf_export_returns_pdf": pdf_result["status"] == 200 and pdf_result["type"] == "application/pdf" and pdf_result["prefix"] == [37,80,68,70]})

        page.locator("#save-trip").click()
        page.locator('[data-workspace="saved"]').click()
        report["checks"].append({"saved_trip_created": page.locator(".saved-trip-card").count() == 1})
        page.locator("[data-open-saved]").click()
        page.wait_for_selector("#results:not([hidden])", timeout=10000)
        report["checks"].append({"saved_trip_reopened_from_api": page.locator("#results").is_visible()})

        page.locator('[data-workspace="journal"]').click()
        page.locator("#journal-note-title").fill("Browser smoke note")
        page.locator("#journal-note-body").fill("A local note saved against this test trip.")
        page.locator('#journal-form button[type="submit"]').click()
        report["checks"].append({"journal_note_saved": page.locator(".journal-entry").count() == 1})
        page.locator("[data-delete-note]").click()
        report["checks"].append({"journal_note_delete_works": page.locator(".journal-entry").count() == 0})

        page.locator('[data-workspace="saved"]').click()
        page.locator("[data-delete-saved]").click()
        report["checks"].append({"saved_trip_delete_works": page.locator(".saved-trip-card").count() == 0})

        page.locator("#workspace-new-trip").click()

        # Community note is submitted to the API, not just dismissed locally.
        page.locator("#open-report").click()
        page.locator("#report-description").fill("A large pothole is visible on the road shoulder near the junction.")
        page.locator("#report-form button[type='submit']").click()
        page.wait_for_function("document.querySelector('#report-message').textContent.includes('Received')", timeout=8000)
        report["checks"].append({"community_report_submitted_for_review": "not verified" in page.locator("#report-message").inner_text()})
        page.locator("#close-report").click()

        page.locator("#origin").fill("Delhi")
        page.locator("#destination").fill("Agra")

        # The API integration suite exercises the real 502 contract; here we
        # reject the browser fetch to check that the form preserves a clear
        # failure state and never switches to synthetic data.
        page.evaluate("""() => {
          const realFetch = window.fetch.bind(window);
          window.fetch = (input, init) => String(input).includes('/api/v1/trips/plan')
            ? Promise.reject(new Error('routing: test-only provider unavailable'))
            : realFetch(input, init);
        }""")
        page.locator("#plan-button").click()
        page.wait_for_function("!document.querySelector('#plan-error').hidden", timeout=8000)
        report["checks"].append({
            "live_provider_error_visible": "test-only provider unavailable" in page.locator("#plan-error").inner_text(),
            "live_error_did_not_show_demo": page.locator("#demo-banner").is_hidden(),
        })

        page.locator("#demo-case").select_option("delhi-agra")
        page.locator("#demo-button").click()
        page.wait_for_selector("#results:not([hidden])", timeout=15000)
        page.locator('[data-workspace="dashboard"]').click()
        page.evaluate("document.querySelector('#results').scrollIntoView({block:'start', behavior:'instant'})")
        page.screenshot(path=str(OUT / "rahgir-v3-desktop.png"), full_page=False)
        page.locator('[data-workspace="routes"]').click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(150)
        mobile_width = page.locator("body").evaluate("el => el.scrollWidth")
        report["checks"].append({"mobile_viewport": {"width": 390, "document_scroll_width": mobile_width, "horizontal_overflow": mobile_width > 390}})
        page.screenshot(path=str(OUT / "rahgir-v3-mobile.png"), full_page=True)
        report["console_errors"] = report["console_errors"][:20]
        report["page_errors"] = report["page_errors"][:20]
        context.close()
        browser.close()

print(json.dumps(report, indent=2))
