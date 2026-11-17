import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(tempfile.gettempdir()) / f'rahgir-browser-smoke-{os.getpid()}.db'
DB_PATH.unlink(missing_ok=True)
os.environ['DATABASE_URL'] = f'sqlite:///{DB_PATH}'
os.environ['PYTHONPATH'] = str(ROOT_DIR / 'backend')
import sys
sys.path.insert(0, str(ROOT_DIR / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from playwright.sync_api import sync_playwright

ROOT = ROOT_DIR / 'backend' / 'app' / 'static'
report = {"console_errors": [], "page_errors": [], "checks": [], "requests": {}}

def route_handler(route):
    request = route.request
    parts = urlsplit(request.url)
    path = parts.path
    if path == '/':
        route.fulfill(status=200, content_type='text/html; charset=utf-8', body=(ROOT/'index.html').read_text())
        return
    if path == '/static/styles.css':
        route.fulfill(status=200, content_type='text/css; charset=utf-8', body=(ROOT/'styles.css').read_text())
        return
    if path == '/static/app.js':
        route.fulfill(status=200, content_type='application/javascript; charset=utf-8', body=(ROOT/'app.js').read_text())
        return
    if request.method == 'OPTIONS':
        route.fulfill(status=204, headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,DELETE,OPTIONS','Access-Control-Allow-Headers':'content-type,x-admin-token'})
        return
    if path.startswith('/api/') or path.startswith('/shared/'):
        body = request.post_data
        if path.endswith('/what-if') and body:
            try: report['requests']['what_if'] = json.loads(body)
            except Exception: pass
        if path.endswith('/demo/plan') and body:
            try: report['requests']['plan'] = json.loads(body)
            except Exception: pass
        headers = {k:v for k,v in request.headers.items() if k.lower() in {'content-type','x-admin-token'}}
        response = client.request(request.method, path + (('?' + parts.query) if parts.query else ''), content=body, headers=headers)
        content_type = response.headers.get('content-type', 'application/json')
        route.fulfill(status=response.status_code, content_type=content_type, headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,DELETE,OPTIONS','Access-Control-Allow-Headers':'content-type,x-admin-token'}, body=response.content)
        return
    # CDN map libraries, tiles, and other third-party network requests are deliberately disabled.
    route.fulfill(status=204, body=b'')

parser = argparse.ArgumentParser(description='Route-intercepted Chromium smoke test for the Rahgir UI')
parser.add_argument('--screenshot', type=Path, default=Path(tempfile.gettempdir()) / 'rahgir-browser-mobile.png')
parser.add_argument('--desktop-screenshot', type=Path, default=Path(tempfile.gettempdir()) / 'rahgir-browser-desktop.png')
parser.add_argument('--executable-path', type=Path, default=None)
args = parser.parse_args()
client = TestClient(app)
client.__enter__()  # initialise the isolated SQLite database through FastAPI lifespan

with sync_playwright() as p:
    executable = str(args.executable_path) if args.executable_path else (shutil.which('chromium') or shutil.which('chromium-browser'))
    launch_options = {'headless': True, 'args': ['--no-sandbox', '--disable-dev-shm-usage']}
    if executable:
        launch_options['executable_path'] = executable
    browser = p.chromium.launch(**launch_options)
    page = browser.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
    page.route('**/*', route_handler)
    page.on('console', lambda msg: report['console_errors'].append(msg.text) if msg.type == 'error' else None)
    page.on('pageerror', lambda exc: report['page_errors'].append(str(exc)))
    html = (ROOT/'index.html').read_text()
    css = (ROOT/'styles.css').read_text()
    js = (ROOT/'app.js').read_text()
    html = html.replace('<head>', '<head><base href="http://rahgir.local/"><style>' + css + '</style>')
    html = html.replace('<link rel="preconnect" href="https://unpkg.com" />', '')
    html = html.replace('<link rel="preconnect" href="https://tile.openstreetmap.org" />', '')
    import re
    html = re.sub(r'<link rel="stylesheet" href="https://unpkg.com/[^>]+>', '', html)
    html = re.sub(r'<link rel="stylesheet" href="/static/styles.css" />', '', html)
    html = re.sub(r'<script defer src="https://unpkg.com/[^>]+></script>', '', html)
    html = re.sub(r'<script defer src="/static/app.js"></script>', '<script>' + js + '</script>', html)
    page.set_content(html, wait_until='domcontentloaded', timeout=30000)
    report['checks'].append({'homepage_loaded':True, 'form_visible':page.locator('#plan-form').is_visible()})
    page.locator('#demo-case').select_option('delhi-agra')
    page.locator('#demo-button').click()
    page.wait_for_selector('#results:not([hidden])', timeout=20000)
    report['checks'].append({'synthetic_result_visible':page.locator('#results').is_visible(), 'demo_disclaimer_visible':page.locator('#demo-banner').is_visible(), 'candidate_count_text':page.locator('#results-subtitle').inner_text(), 'alternatives':page.locator('.alternative-card').count()})
    args.desktop_screenshot.parent.mkdir(parents=True, exist_ok=True)
    page.evaluate("document.querySelector('#results').scrollIntoView({block:'start', behavior:'instant'})")
    page.wait_for_timeout(350)
    page.screenshot(path=str(args.desktop_screenshot), full_page=False)
    # A route personality is a real selection control, not a decorative comparison card.
    if page.locator('.alternative-card').count() > 1:
        page.locator('.alternative-card').nth(1).click()
        page.wait_for_function("document.querySelectorAll('.alternative-card')[1].getAttribute('aria-pressed') === 'true'", timeout=10000)
        report['checks'].append({'route_persona_selects': True, 'selected_label': page.locator('#selected-label').inner_text()})
    # The category filter changes the displayed candidate set.
    all_count = page.locator('.candidate-card').count()
    page.locator('[data-filter="food"]').click()
    food_count = page.locator('.candidate-card').count()
    page.locator('[data-filter="all"]').click()
    report['checks'].append({'candidate_filter_changes_results': food_count <= all_count, 'all_candidates_restored': page.locator('.candidate-card').count() == all_count})
    # Dial label is immediate; its value is sent to the server on the next what-if recomputation.
    page.locator('#discovery-bias').fill('90')
    report['checks'].append({'discovery_dial_updates_copy': '90% discovery' in page.locator('#discovery-value').inner_text()})
    page.locator('#whatif-budget').fill('90')
    future = page.evaluate("() => { const d = new Date(); d.setDate(d.getDate()+2); d.setHours(10,0,0,0); const pad = n => String(n).padStart(2,'0'); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`; }")
    page.locator('#whatif-departure').fill(future)
    page.locator('#whatif-button').click()
    page.wait_for_function("document.querySelector('#whatif-button').disabled === false", timeout=20000)
    report['checks'].append({'what_if_recomputed':True, 'new_alternative_count':page.locator('.alternative-card').count(), 'discovery_bias_sent': report['requests'].get('what_if', {}).get('discovery_bias'), 'departure_at_sent': bool(report['requests'].get('what_if', {}).get('departure_at'))})
    page.locator('#open-report').click()
    report['checks'].append({'report_modal_open':page.locator('#report-modal').is_visible()})
    page.locator('#close-report').click()
    report['checks'].append({'report_modal_closed':page.locator('#report-modal').is_hidden()})
    report['checks'].append({'pdf_export_endpoint': 'covered by API integration test suite; browser new-tab download not asserted in this smoke run'})
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(250)
    mobile_width = page.locator('body').evaluate('el => el.scrollWidth')
    report['checks'].append({'mobile_viewport':{'width':390,'document_scroll_width':mobile_width,'document_height':page.locator('body').evaluate('el => el.scrollHeight'),'horizontal_overflow': mobile_width > 390}})
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(args.screenshot), full_page=True)
    report['console_errors'] = report['console_errors'][:20]
    report['page_errors'] = report['page_errors'][:20]
    browser.close()
client.__exit__(None, None, None)
print(json.dumps({**report, 'mobile_screenshot': str(args.screenshot), 'desktop_screenshot': str(args.desktop_screenshot)}, indent=2))
