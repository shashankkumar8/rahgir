/* Core state, validation, API transport and safe DOM utilities. */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { tripId: null, result: null, activeAlternative: null, planRequest: null, customStopIds: [], customValidation: null, map: null, routeLayer: null, stopLayer: null, candidateLayer: null, endpointLayer: null, candidateMarkers: {}, selectedCoordinates: null, shareToken: null, candidateFilter: 'all', candidateSearch: '', workspaceView: 'dashboard', savedTrips: [], journalEntries: {} };
  const SAVED_KEY = 'rahgir.savedTrips.v2';
  const JOURNAL_KEY = 'rahgir.journal.v2';
  const DEFAULT_PREFERENCES = { culture: 80, history: 70, food: 60, nature: 50, religion: 65, shopping: 40, photography: 45 };
  const VIBE_PREFERENCES = { food: { food: 94 }, heritage: { culture: 94, history: 94 }, spiritual: { religion: 96 }, markets: { shopping: 94 }, nature: { nature: 94 }, photography: { photography: 94 } };
  const API = '/api/v1';

  function showToast(message) {
    const toast = $('toast');
    toast.textContent = message;
    toast.classList.add('show');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 3200);
  }

  function formatMinutes(minutes) {
    if (minutes === null || minutes === undefined || Number.isNaN(Number(minutes))) return '—';
    const n = Math.round(Number(minutes));
    const h = Math.floor(n / 60), m = n % 60;
    return h ? `${h}h ${m ? `${m}m` : ''}`.trim() : `${m} min`;
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      let message = typeof data === 'object' ? (data.detail?.message || data.detail || data.error || response.statusText) : data;
      if (typeof message === 'object') message = JSON.stringify(message);
      throw new Error(message || `Request failed (${response.status})`);
    }
    return data;
  }

  function buildRequest() {
    const date = $('departure-date').value;
    const time = $('departure-time').value;
    let departure_at = null;
    if (date && time) departure_at = `${date}T${time}:00+05:30`;
    const preferences = {};
    document.querySelectorAll('[data-pref]').forEach((input) => { preferences[input.dataset.pref] = Number(input.value) / 100; });
    const poi_categories = [...document.querySelectorAll('[data-category]:checked')].map((input) => input.dataset.category);
    if (!poi_categories.length) throw new Error('Choose at least one stop type or road facility.');
    const vehicle_type = $('vehicle-type').value;
    const body = {
      origin: $('origin').value.trim(),
      destination: $('destination').value.trim(),
      departure_at,
      detour_budget_minutes: Number($('detour-budget').value),
      max_journey_minutes: Number($('max-time').value),
      max_stops: Number($('max-stops').value),
      stop_duration_minutes: Number($('stop-duration').value),
      traveler_mode: $('traveler-mode').value,
      discovery_bias: Number($('discovery-bias').value) / 100,
      preferences,
      poi_categories,
      vehicle_type,
      seed: 42,
    };
    if (vehicle_type !== 'not_set') {
      const consumption = Number($('vehicle-consumption').value);
      const price = Number($('vehicle-price').value);
      if (!consumption || !price || consumption <= 0 || price <= 0) throw new Error('Enter your vehicle efficiency and current unit price, or set vehicle type to Not configured.');
      body.consumption_per_100km = consumption;
      body.energy_price_per_unit = price;
    }
    return body;
  }

  async function checkHealth() {
    try {
      const health = await api('/health');
      state.providerHealth = health;
      const providers = health.providers || {};
      const missing = Object.entries(providers).filter(([, value]) => !value.configured).map(([name]) => name);
      $('api-status').textContent = health.live_planning_ready
        ? 'Live providers configured · uptime not yet probed'
        : `Live planning unavailable · configure ${missing.join(', ') || 'provider settings'}`;
      $('route-status').textContent = health.live_planning_ready ? 'Ready for a live provider request' : 'Live provider configuration incomplete';
      $('workspace-provider-status').textContent = health.live_planning_ready ? 'Routing + geocoding configured · not probed' : `Missing: ${missing.join(', ')}`;
      $('plan-button').disabled = !health.live_planning_ready;
      $('plan-button').title = health.live_planning_ready ? 'Submit a live provider-backed trip request' : 'Live planning is not configured on this service';
      $('plan-error').hidden = health.live_planning_ready;
      $('plan-error').textContent = health.live_planning_ready
        ? ''
        : `Live planning is not configured. Missing: ${missing.join(', ')}. The offline walkthrough is separate and uses synthetic data.`;
    } catch (error) {
      $('api-status').textContent = 'API unavailable';
      $('route-status').textContent = 'Start the local API';
      $('workspace-provider-status').textContent = `API unavailable · ${error.message}`;
      $('plan-button').disabled = true;
    }
  }

  function syncVehicleFields() {
    const type = $('vehicle-type').value;
    const enabled = type !== 'not_set';
    $('vehicle-consumption').disabled = !enabled;
    $('vehicle-price').disabled = !enabled;
    $('vehicle-consumption-label').textContent = type === 'electric' ? 'ENERGY / 100 KM (KWH)' : type === 'cng' ? 'CONSUMPTION / 100 KM (KG)' : 'CONSUMPTION / 100 KM (LITRES)';
    $('vehicle-price-label').textContent = type === 'electric' ? 'PRICE PER KWH (₹)' : type === 'cng' ? 'PRICE PER KG (₹)' : 'PRICE PER LITRE (₹)';
  }
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function escapeAttr(value) { return escapeHtml(value).replace(/javascript:/gi, ''); }

  function safeHttpsUrl(value, allowedHosts = null) {
    try {
      const parsed = new URL(String(value || ''), window.location.origin);
      if (parsed.protocol !== 'https:') return '';
      if (allowedHosts && !allowedHosts.includes(parsed.hostname)) return '';
      return parsed.toString();
    } catch (_) { return ''; }
  }

  function trustedImageUrl(value) {
    return safeHttpsUrl(value, ['upload.wikimedia.org']);
  }

  function readStorage(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) { return fallback; }
  }

  function writeStorage(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (_) { showToast('Browser storage is unavailable or full. Your data was not saved.'); return false; }
  }
  window.Rahgir = {
    $, state, SAVED_KEY, JOURNAL_KEY, DEFAULT_PREFERENCES, VIBE_PREFERENCES, API,
    showToast, formatMinutes, api, buildRequest, checkHealth, syncVehicleFields,
    escapeHtml, escapeAttr, safeHttpsUrl, trustedImageUrl, readStorage, writeStorage,
  };
})();
