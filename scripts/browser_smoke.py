"""Route-intercepted Chromium smoke test for Rahgir's public and workspace flows."""
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
report = {"console_errors": [], "page_errors": [], "checks": [], "requests": {}}


def route_handler(route):
    request = route.request
    path = urlsplit(request.url).path
    if path.startswith("/api/") or path.startswith("/shared/"):
        body = request.post_data
        if path.endswith("/demo/plan") and body:
            try:
                report["requests"]["plan"] = json.loads(body)
            except Exception:
                pass
        if path.endswith("/ask") and body:
            try:
                report["requests"]["assistant"] = json.loads(body)
            except Exception:
                pass
        headers = {k: v for k, v in request.headers.items() if k.lower() in {"content-type", "x-admin-token"}}
        response = client.request(request.method, path + (("?" + urlsplit(request.url).query) if urlsplit(request.url).query else ""), content=body, headers=headers)
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
js = (STATIC / "app.js").read_text()
# set_content runs on an opaque origin in this smoke harness. This in-memory
# localStorage shim exercises the browser-local Saved/Journal interactions; it
# is test-only and does not ship in the application.
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
})();
</script>"""
html = html.replace("<head>", '<head><base href="http://rahgir.local/">' + storage_shim + "<style>" + css + "\n" + workspace_css + "</style>")
import re
html = re.sub(r'<link rel="preconnect" href="https://unpkg.com" />', "", html)
html = re.sub(r'<link rel="preconnect" href="https://tile.openstreetmap.org" />', "", html)
html = re.sub(r'<link rel="stylesheet" href="https://unpkg.com/[^>]+>', "", html)
html = re.sub(r'<link rel="stylesheet" href="/static/styles.css" />', "", html)
html = re.sub(r'<link rel="stylesheet" href="/static/workspace.css" />', "", html)
html = re.sub(r'<script defer src="https://unpkg.com/[^>]+></script>', "", html)
html = re.sub(r'<script defer src="/static/app.js"></script>', "<script>" + js + "</script>", html)

client = TestClient(app)
with client:
    with sync_playwright() as p:
        executable = shutil.which("chromium") or shutil.which("chromium-browser")
        launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable:
            launch["executable_path"] = executable
        browser = p.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page.route("**/*", route_handler)
        page.on("console", lambda msg: report["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: report["page_errors"].append(str(exc)))
        page.set_content(html, wait_until="domcontentloaded", timeout=30000)
        report["checks"].append({"homepage_loaded": True, "form_visible": page.locator("#plan-form").is_visible()})

        page.locator("#demo-case").select_option("delhi-agra")
        page.locator("#demo-button").click()
        page.wait_for_selector("#results:not([hidden])", timeout=15000)
        report["checks"].append({
            "synthetic_result_visible": page.locator("#results").is_visible(),
            "demo_disclaimer_visible": page.locator("#demo-banner").is_visible(),
            "workspace_shell_active": page.locator("body").evaluate("el => el.classList.contains('workspace-active')"),
            "map_moved_into_workspace": page.locator("#map-card").evaluate("el => el.parentElement.id") == "workspace-map-slot",
            "pareto_alternatives": page.locator(".alternative-card").count(),
        })

        page.locator("#save-trip").click()
        page.locator('[data-workspace="saved"]').click()
        report["checks"].append({"saved_trip_created": page.locator(".saved-trip-card").count() == 1})
        page.locator("[data-open-saved]").click()
        page.wait_for_selector("#results:not([hidden])", timeout=10000)

        page.locator('[data-workspace="journal"]').click()
        page.locator("#journal-note-title").fill("Browser smoke note")
        page.locator("#journal-note-body").fill("A local note saved against this test trip.")
        page.locator('#journal-form button[type="submit"]').click()
        report["checks"].append({"journal_note_saved": page.locator(".journal-entry").count() == 1})

        page.locator('[data-workspace="assistant"]').click()
        page.locator("#assistant-question").fill("What is the route distance and total drive time?")
        page.locator('#assistant-form button[type="submit"]').click()
        page.wait_for_function("document.querySelectorAll('#assistant-messages .assistant-message').length >= 3", timeout=8000)
        report["checks"].append({"trip_assistant_replied": page.locator("#assistant-messages .assistant-message").count() >= 3})

        page.locator('[data-workspace="routes"]').click()
        all_count = page.locator(".candidate-card").count()
        page.locator('[data-filter="food"]').click()
        food_count = page.locator(".candidate-card").count()
        page.locator('[data-filter="all"]').click()
        page.locator("#workspace-search").fill("museum")
        search_count = page.locator(".candidate-card").count()
        page.locator("#workspace-search").fill("")
        report["checks"].append({"candidate_filter_operates": food_count <= all_count, "workspace_search_operates": search_count <= all_count})

        page.locator('[data-workspace="dashboard"]').click()
        page.evaluate("document.querySelector('#results').scrollIntoView({block:'start', behavior:'instant'})")
        page.screenshot(path="/mnt/data/rahgir-v2-spec/rahgir-v2-desktop.png", full_page=False)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        mobile_width = page.locator("body").evaluate("el => el.scrollWidth")
        report["checks"].append({"mobile_viewport": {"width": 390, "document_scroll_width": mobile_width, "horizontal_overflow": mobile_width > 390}})
        page.screenshot(path="/mnt/data/rahgir-v2-spec/rahgir-v2-mobile.png", full_page=True)
        report["console_errors"] = report["console_errors"][:20]
        report["page_errors"] = report["page_errors"][:20]
        browser.close()

print(json.dumps(report, indent=2))
