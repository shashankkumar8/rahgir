/* Rahgir client: no LLM SDK, no hidden scoring service. */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { tripId: null, result: null, activeAlternative: null, map: null, routeLayer: null, stopLayer: null, candidateLayer: null, endpointLayer: null, candidateMarkers: {}, selectedCoordinates: null, shareToken: null, candidateFilter: 'all' };
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
    return {
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
      seed: 42,
    };
  }

  async function checkHealth() {
    try {
      const health = await api('/health');
      $('api-status').textContent = 'API online · ' + health.routing_provider_configured.toUpperCase() + ' selected';
      $('route-status').textContent = 'Ready to plan';
    } catch (_) {
      $('api-status').textContent = 'API unavailable';
      $('route-status').textContent = 'Start the local API';
    }
  }

  function initMap() {
    const host = $('route-map');
    if (window.L && !state.map) {
      host.innerHTML = '';
      state.map = L.map(host, { zoomControl: true, scrollWheelZoom: false }).setView([27.9, 78.2], 6);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>',
      }).addTo(state.map);
      state.routeLayer = L.layerGroup().addTo(state.map);
      state.stopLayer = L.layerGroup().addTo(state.map);
      state.candidateLayer = L.layerGroup().addTo(state.map);
      state.endpointLayer = L.layerGroup().addTo(state.map);
      state.map.on('click', (event) => {
        $('report-lat').value = event.latlng.lat.toFixed(6);
        $('report-lon').value = event.latlng.lng.toFixed(6);
        openReportModal();
      });
    }
    if (state.map) setTimeout(() => state.map.invalidateSize(), 80);
  }

  function customIcon(kind) {
    if (!window.L) return null;
    return L.divIcon({ className: '', html: `<span class="custom-pin ${kind}"></span>`, iconSize: [18, 18], iconAnchor: [9, 9] });
  }

  function renderSchematicMap(result, alternative) {
    const host = $('route-map');
    const stops = alternative?.stops || [];
    const start = [result.origin.latitude, result.origin.longitude];
    const end = [result.destination.latitude, result.destination.longitude];
    const geometry = result.route.selected_geometry || result.route.geometry || [];
    const routePoints = geometry.map(([lon, lat]) => [lat, lon]);
    const linePoints = routePoints.length > 1 ? routePoints : [start, ...stops.map((s) => [s.latitude, s.longitude]), end];
    const all = [...linePoints, start, ...stops.map((s) => [s.latitude, s.longitude]), end];
    const width = 800, height = 460, pad = 65;
    const lats = all.map(x => x[0]), lons = all.map(x => x[1]);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const dx = Math.max(.001, maxLon - minLon), dy = Math.max(.001, maxLat - minLat);
    const point = ([lat, lon]) => [pad + (lon - minLon) / dx * (width - 2 * pad), height - pad - (lat - minLat) / dy * (height - 2 * pad)];
    const pts = linePoints.map(point);
    const path = pts.map((p,i)=>`${i?'L':'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
    const markers = [
      {xy: start, label: 'START', fill: '#18292b'},
      ...stops.map((stop, i) => ({xy: [stop.latitude, stop.longitude], label: String(i + 1).padStart(2, '0'), fill: '#526d59'})),
      {xy: end, label: 'END', fill: '#c78c3d'},
    ].map((item) => {
      const p = point(item.xy);
      return `<circle cx="${p[0]}" cy="${p[1]}" r="${item.label==='START'||item.label==='END'?10:7}" fill="${item.fill}" stroke="#fffefa" stroke-width="3"/><text x="${p[0]}" y="${p[1]-16}" text-anchor="middle" font-size="11" fill="#18292b">${item.label}</text>`;
    }).join('');
    host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Route geometry schematic without map tiles" style="width:100%;height:100%;min-height:430px;background:#e8e9df"><defs><pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M 34 0 L 0 0 0 34" fill="none" stroke="#cfd8cc" stroke-width="1"/></pattern></defs><rect width="100%" height="100%" fill="url(#grid)"/><path d="${path}" fill="none" stroke="#c75d3d" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="${path}" fill="none" stroke="#fffefa" stroke-width="1.4" stroke-dasharray="7 10"/>${markers}<text x="24" y="30" font-size="10" fill="#64716c" font-family="monospace">SCHEMATIC GEOMETRY · MAP TILES UNAVAILABLE · NOT FOR NAVIGATION</text></svg>`;
  }


  function renderMap(result, alternative) {
    const geometry = result.route.selected_geometry || result.route.geometry;
    const demo = result.mode === 'synthetic_demo';
    if (!state.map && !window.L) {
      renderSchematicMap(result, alternative);
      $('map-warning').hidden = false;
      $('map-warning').textContent = demo ? 'Synthetic illustration only — not a navigational map.' : 'Map library unavailable. Showing a schematic from provider coordinates.';
      $('map-title').textContent = `${result.origin.label.split(',')[0]} → ${result.destination.label.split(',')[0]}`;
      $('route-status').textContent = demo ? 'Synthetic walkthrough' : 'Road route calculated';
      $('data-freshness').textContent = result.data_integrity?.retrieved_at
        ? new Date(result.data_integrity.retrieved_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})
        : '—';
      return;
    }
    initMap();
    if (!state.map) return;
    state.routeLayer.clearLayers();
    state.stopLayer.clearLayers();
    state.candidateLayer.clearLayers();
    state.candidateMarkers = {};
    state.endpointLayer.clearLayers();
    const latlngs = (geometry || []).map(([lon, lat]) => [lat, lon]);
    if (latlngs.length > 1) {
      L.polyline(latlngs, { color: '#c75d3d', weight: 5, opacity: .9, lineCap: 'round' }).addTo(state.routeLayer);
      if (demo) L.polyline(latlngs, { color: '#fffefa', weight: 1, dashArray: '5 8', opacity: .9 }).addTo(state.routeLayer);
    }
    const start = [result.origin.latitude, result.origin.longitude];
    const end = [result.destination.latitude, result.destination.longitude];
    L.marker(start, { icon: customIcon('origin') }).bindPopup(`<b>Start</b><br>${escapeHtml(result.origin.label)}`).addTo(state.endpointLayer);
    L.marker(end, { icon: customIcon('destination') }).bindPopup(`<b>Destination</b><br>${escapeHtml(result.destination.label)}`).addTo(state.endpointLayer);
    const selectedIds = new Set(alternative?.stop_ids || (alternative?.stops || []).map((x) => x.id));
    (result.candidate_assessments || result.candidates || []).forEach((candidate) => {
      if (!Number.isFinite(Number(candidate.latitude)) || !Number.isFinite(Number(candidate.longitude))) return;
      const selected = selectedIds.has(candidate.id);
      const marker = L.circleMarker([Number(candidate.latitude), Number(candidate.longitude)], {
        radius: selected ? 8 : 5,
        color: selected ? '#fffefa' : '#596d61',
        weight: selected ? 2 : 1,
        fillColor: selected ? '#c75d3d' : '#8da493',
        fillOpacity: selected ? 1 : .76,
      }).bindPopup(`<b>${escapeHtml(candidate.name)}</b><br>${escapeHtml(candidate.category || 'mapped place')}<br><small>${selected ? 'In selected itinerary' : (candidate.individual_status === 'blocked' ? 'Single-stop constraints not met' : 'Mapped candidate')}</small>`);
      marker.addTo(state.candidateLayer);
      state.candidateMarkers[candidate.id] = marker;
    });
    (alternative?.stops || []).forEach((stop, index) => {
      const marker = L.marker([stop.latitude, stop.longitude], { icon: customIcon('poi') });
      marker.bindPopup(`<b>${escapeHtml(stop.name)}</b><br>${escapeHtml(stop.category.replaceAll('_',' '))}<br><small>${escapeHtml(stop.hours_status)} · ${Math.round(stop.corridor_distance_m)} m from route</small><br><a href="${escapeAttr(stop.source_url)}" target="_blank" rel="noreferrer">Source ↗</a>`);
      marker.addTo(state.stopLayer);
    });
    const bounds = L.latLngBounds([start, end, ...latlngs]);
    state.map.fitBounds(bounds.pad(.12));
    $('map-warning').hidden = false;
    $('map-warning').textContent = demo ? 'DEMO: synthetic road costs and POIs; not for navigation or safety decisions.' : (result.route.selected_geometry ? `Route geometry returned by ${result.route.selected_geometry_provider}.` : 'Selected alternative route geometry unavailable; map shows the original provider route.');
    $('map-title').textContent = `${result.origin.label.split(',')[0]} → ${result.destination.label.split(',')[0]}`;
    $('route-status').textContent = demo ? 'Synthetic walkthrough' : 'Road route calculated';
    $('data-freshness').textContent = new Date(result.data_integrity.retrieved_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function escapeAttr(value) { return escapeHtml(value).replace(/javascript:/gi, ''); }

  function renderMetrics(result, alternative) {
    const route = result.route, m = alternative?.metrics || {};
    const verifiedDuration = alternative?.verified_route_duration_minutes;
    const items = [
      ['ROAD DISTANCE', `${route.distance_km} km`, 'Base route returned by routing provider'],
      ['BASE DRIVE', formatMinutes(route.duration_minutes), 'Without discovery stops'],
      ['EXTRA DRIVE', formatMinutes(m.additional_driving_minutes ?? 0), 'Compared with the base route'],
      ['TOTAL TIME', formatMinutes(m.estimated_total_minutes_including_stops ?? (verifiedDuration ?? route.duration_minutes)), 'Drive plus planned stop time'],
    ];
    $('route-metrics').innerHTML = items.map(([a,b,c])=>`<div class="metric-card"><span>${a}</span><strong>${b}</strong><small>${c}</small></div>`).join('');
  }

  const personaInfo = {
    'Balanced': ['✳', 'A considered mix of discovery and time on the road.'],
    'Fastest': ['⚡', 'Keeps additional driving as low as possible within the feasible set.'],
    'Culture-rich': ['⌂', 'Prioritises the model’s cultural and heritage relevance signals.'],
    'Explorer': ['✧', 'Prioritises corridor-category novelty and variety; novelty is a local proxy.'],
    'Food trail': ['◒', 'Prioritises mapped food-related places that fit the constraints.'],
  };

  function renderAlternatives(alternatives, selected) {
    const container = $('alternative-cards');
    if (!alternatives || !alternatives.length) {
      container.innerHTML = '<div class="empty-state"><strong>No feasible stops fit these settings.</strong><p>Your direct road route remains available. Try a larger detour allowance or longer journey window.</p></div>';
      return;
    }
    container.innerHTML = alternatives.map((alt, index) => {
      const m = alt.metrics || {};
      const isActive = alt.label === selected?.label;
      const [icon, description] = personaInfo[alt.label] || ['✳', 'A non-dominated alternative from the current feasible set.'];
      return `<button type="button" class="alternative-card ${isActive?'active':''}" data-alt="${index}" aria-pressed="${isActive}">
        <span class="alt-top"><span class="alt-icon">${icon}</span><span class="alt-kicker">OPTION 0${index+1} · PARETO</span></span>
        <h4>${escapeHtml(alt.label)}</h4><p class="alt-description">${description}</p>
        <div class="alt-metric"><span><b>${alt.stops.length}</b> stops</span><span><b>+${formatMinutes(m.additional_driving_minutes)}</b> drive</span><span><b>${formatMinutes(m.estimated_total_minutes_including_stops)}</b> total</span></div>
        <span class="alt-select">${isActive ? 'Currently selected ✓' : 'Explore this option ↗'}</span>
      </button>`;
    }).join('');
    container.querySelectorAll('[data-alt]').forEach((button) => button.addEventListener('click', async () => {
      const alt = alternatives[Number(button.dataset.alt)];
      await selectAlternative(alt);
    }));
  }

  function renderRouteInsight(result, alternative) {
    const box = $('route-insight');
    if (!alternative) {
      box.innerHTML = '<span class="insight-spark">✳</span><div><span class="card-kicker">YOUR ROUTE RECIPE</span><strong>No alternative could be computed.</strong><p>Review the provider response and try again.</p></div>';
      return;
    }
    const m = alternative.metrics || {};
    const stops = alternative.stops || [];
    const extra = Number(m.additional_driving_minutes || 0);
    const total = m.estimated_total_minutes_including_stops;
    const text = stops.length
      ? `${alternative.label} adds about ${Math.round(extra)} minutes of driving and includes ${stops.length} mapped ${stops.length === 1 ? 'stop' : 'stops'}. ${total == null ? '' : `Estimated journey time including stops: ${formatMinutes(total)}.`}`
      : 'Your current constraints favour the direct road journey. No detours were selected.';
    const caveat = result.mode === 'synthetic_demo'
      ? 'This is an offline synthetic walkthrough; the route and places are illustrative only.'
      : 'This is a planning estimate from the configured routing provider, not turn-by-turn navigation.';
    box.innerHTML = `<span class="insight-spark">✳</span><div><span class="card-kicker">YOUR ROUTE RECIPE</span><strong>${escapeHtml(text)}</strong><p>${escapeHtml(caveat)}</p></div>`;
  }

  function renderJourneyPulse(result, alternative) {
    const stops = alternative?.stops || [];
    const sequence = [{label: result.origin.label.split(',')[0], sub: 'Start', time: 'DEPART', kind:'start'}];
    stops.forEach((stop, i) => sequence.push({
      label: stop.name,
      sub: stop.category.replaceAll('_',' '),
      time: stop.arrival_at ? new Date(stop.arrival_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : 'ETA unknown',
      kind: 'stop',
    }));
    const selectedDuration = alternative?.verified_route_duration_minutes ?? (Number(result.route.duration_minutes || 0) + Number(alternative?.metrics?.additional_driving_minutes || 0));
    let arrival = 'ETA estimate';
    const lastArrival = stops.length && stops[stops.length - 1].arrival_at ? new Date(stops[stops.length - 1].arrival_at) : null;
    if (lastArrival && Number.isFinite(lastArrival.getTime())) {
      const stopMin = Number(stops[stops.length - 1].stop_duration_minutes || 0);
      const end = new Date(lastArrival.getTime() + stopMin * 60000 + Math.max(0, selectedDuration - Number(result.route.duration_minutes || 0)) * 60000);
      arrival = end.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
    }
    sequence.push({label: result.destination.label.split(',')[0], sub:'Destination', time: arrival, kind:'end'});
    $('journey-pulse').innerHTML = sequence.map((item, i) => `<div class="pulse-stop ${item.kind}"><span class="pulse-node">${item.kind === 'start' ? 'A' : item.kind === 'end' ? 'B' : String(i).padStart(2,'0')}</span><div><b>${escapeHtml(item.label)}</b><small>${escapeHtml(item.sub)}</small></div><time>${escapeHtml(item.time)}</time></div>`).join('');
  }

  function renderStops(alternative) {
    const stops = alternative?.stops || [];
    $('empty-stops').hidden = stops.length > 0;
    $('stop-list').innerHTML = stops.map((stop, index) => {
      const hoursLabel = stop.hours_status === 'open' ? 'Mapped hours: open at estimated ETA' : stop.hours_status === 'closed' ? 'Mapped hours: closed at estimated ETA' : 'Opening hours: unknown';
      const source = stop.source_url && /^https?:\/\//i.test(stop.source_url) ? `<a class="stop-source" href="${escapeAttr(stop.source_url)}" target="_blank" rel="noreferrer">View map source ↗</a>` : '<span class="stop-source muted">No external place source available in this record</span>';
      return `<article class="stop-item stop-card"><div class="stop-index">${String(index+1).padStart(2,'0')}</div><div class="stop-content"><div class="stop-title-row"><h4>${escapeHtml(stop.name)}</h4><span class="place-category">${escapeHtml(stop.category.replaceAll('_',' '))}</span></div><p class="stop-facts">${Math.round(stop.corridor_distance_m)} m from route · ${escapeHtml(hoursLabel)}</p><details class="why-details"><summary>Why this place?</summary><ul>${(stop.explanation || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}<li>Cultural signal is a category/tag heuristic, not a verified cultural assessment.</li></ul><div class="evidence-mini"><span>Mapped metadata coverage</span><b>${Math.round(Number(stop.metadata_completeness || 0) * 100)}%</b></div><div class="evidence-track"><i style="width:${Math.max(0, Math.min(100, Number(stop.metadata_completeness || 0) * 100))}%"></i></div><p class="data-caveat">Metadata coverage indicates field completeness only; it is not factual confidence.</p></details>${source}</div><div class="stop-meta"><b>${stop.arrival_at ? new Date(stop.arrival_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : 'ETA —'}</b><small>${stop.stop_duration_minutes} min stop</small></div></article>`;
    }).join('');
  }

  function candidateGroup(category) {
    const c = String(category || '').toLowerCase();
    if (['heritage','historic','museum','castle','gallery','attraction','place_of_worship'].includes(c)) return 'heritage';
    if (['restaurant','cafe','bakery','food_court'].includes(c)) return 'food';
    if (['park','garden','nature_reserve','viewpoint','zoo'].includes(c)) return 'nature';
    if (['craft','marketplace'].includes(c)) return 'craft';
    return 'other';
  }

  function renderCandidateExplorer(result, alternative) {
    const assessments = result.candidate_assessments || (result.candidates || []).map((x) => ({...x, individual_status:'unknown', individual_reasons:['Individual route-fit assessment is unavailable.'], caveats:[]}));
    const selectedIds = new Set(alternative?.stop_ids || (alternative?.stops || []).map((x) => x.id));
    const filtered = assessments.filter((item) => state.candidateFilter === 'all' || candidateGroup(item.category) === state.candidateFilter);
    $('candidate-count').textContent = `${filtered.length} of ${assessments.length} mapped places`;
    $('candidate-empty').hidden = filtered.length > 0;
    $('candidate-grid').innerHTML = filtered.map((item) => {
      const selected = selectedIds.has(item.id);
      const blocked = item.individual_status === 'blocked';
      const status = selected ? 'In this itinerary' : blocked ? 'Outside current limits' : item.individual_status === 'eligible' ? 'Individually feasible' : 'Not assessed';
      const reasonItems = selected ? (item.why_it_might_fit || []) : blocked ? (item.individual_reasons || []) : ['This place passes the single-stop checks, but is not part of the currently selected combination. Another Pareto option may include it.'];
      const detour = item.single_stop_detour_minutes == null ? 'Detour unavailable' : `+${Math.round(item.single_stop_detour_minutes)} min single-stop drive`;
      const source = item.source_url && /^https?:\/\//i.test(item.source_url) ? `<a href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer">Source ↗</a>` : '<span>No source link</span>';
      return `<article class="candidate-card ${selected?'selected':''} ${blocked?'blocked':''}"><div class="candidate-card-top"><span class="candidate-status ${selected?'good':blocked?'warning':'neutral'}">${escapeHtml(status)}</span><span class="candidate-category">${escapeHtml(item.category || 'place')}</span></div><h4>${escapeHtml(item.name)}</h4><p class="candidate-metric">${escapeHtml(detour)} ${item.single_stop_detour_km == null ? '' : `· +${Number(item.single_stop_detour_km).toFixed(1)} km`}</p><details><summary>${selected ? 'Why this stop?' : 'Why / why not?'}</summary><ul>${reasonItems.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>${(item.caveats || []).map((caveat) => `<p class="candidate-caveat">${escapeHtml(caveat)}</p>`).join('')}</details><div class="candidate-card-foot">${source}<button type="button" data-locate="${escapeAttr(item.id)}">Show on map ↗</button></div></article>`;
    }).join('');
    $('candidate-grid').querySelectorAll('[data-locate]').forEach((button) => button.addEventListener('click', () => {
      const marker = state.candidateMarkers[button.dataset.locate];
      if (marker && state.map) { state.map.setView(marker.getLatLng(), Math.max(state.map.getZoom(), 12), {animate:true}); marker.openPopup(); $('route-map').scrollIntoView({behavior:'smooth', block:'center'}); }
      else showToast('Candidate coordinates are not available on the active map.');
    }));
    const notSelected = assessments.filter((item) => !selectedIds.has(item.id));
    $('not-selected-list').innerHTML = notSelected.length ? notSelected.map((item) => {
      const reasons = item.individual_status === 'blocked' ? (item.individual_reasons || []) : ['Individually feasible, but not selected in this itinerary. The optimizer balances the complete stop combination rather than choosing every feasible place.'];
      return `<div class="not-selected-row"><b>${escapeHtml(item.name)}</b><span>${item.individual_status === 'blocked' ? 'Does not pass single-stop checks' : 'Not in selected combination'}</span><small>${reasons.map(escapeHtml).join(' ')}</small></div>`;
    }).join('') : '<p class="small-note">Every mapped candidate is included in this selected itinerary.</p>';
  }

  async function selectAlternative(alternative) {
    state.activeAlternative = alternative;
    document.querySelectorAll('.alternative-card').forEach((card, index) => {
      const active = state.result.alternatives[index]?.label === alternative.label;
      card.classList.toggle('active', active);
      card.setAttribute('aria-pressed', active ? 'true' : 'false');
      const selectText = card.querySelector('.alt-select');
      if (selectText) selectText.textContent = active ? 'Currently selected ✓' : 'Explore this option ↗';
    });
    $('selected-label').textContent = `${alternative.label} itinerary`;
    $('feasible-chip').textContent = alternative.constraints.detour_budget_respected && alternative.constraints.max_journey_time_respected ? 'Constraints satisfied' : 'Check constraints';
    renderMetrics(state.result, alternative);
    renderStops(alternative);
    renderRouteInsight(state.result, alternative);
    renderJourneyPulse(state.result, alternative);
    renderCandidateExplorer(state.result, alternative);
    if (state.tripId) {
      try {
        const preview = await api(`/trips/${state.tripId}/route-preview`, {method:'POST', body:JSON.stringify({stop_ids: alternative.stop_ids || []})});
        state.result.route.selected_geometry = preview.geometry;
        state.result.route.selected_geometry_provider = preview.provider;
      } catch (error) {
        state.result.route.selected_geometry = null;
        $('map-warning').textContent = `Selected route geometry unavailable: ${error.message}. The provider's baseline route will remain visible.`;
      }
    }
    renderMap(state.result, alternative);
  }

  function renderResults(wrapper) {
    const result = wrapper.result || wrapper;
    state.tripId = wrapper.trip_id || result.trip_id || null;
    state.result = result;
    state.activeAlternative = result.selected_alternative || result.alternatives?.[0] || null;
    $('results').hidden = false;
    $('results').scrollIntoView({behavior:'smooth', block:'start'});
    $('results-subtitle').textContent = `${result.origin.label.split(',')[0]} to ${result.destination.label.split(',')[0]} · ${result.candidate_count} mapped corridor candidates examined`;
    $('demo-banner').hidden = result.mode !== 'synthetic_demo';
    renderAlternatives(result.alternatives, state.activeAlternative);
    renderMetrics(result, state.activeAlternative);
    renderStops(state.activeAlternative);
    renderRouteInsight(result, state.activeAlternative);
    renderJourneyPulse(result, state.activeAlternative);
    renderCandidateExplorer(result, state.activeAlternative);
    renderMap(result, state.activeAlternative);
    $('safety-insight').querySelector('p').textContent = result.safety?.explanation || 'Insufficient safety data. Missing incident reports do not establish that a road is safe.';
    $('weather-insight').querySelector('p').textContent = result.weather?.explanation || 'No forecast data was used in this plan.';
    $('plan-error').hidden = true;
  }

  async function submitPlan(isDemo = false) {
    const button = isDemo ? $('demo-button') : $('plan-button');
    const original = button.innerHTML;
    button.disabled = true;
    button.textContent = isDemo ? 'Building offline walkthrough…' : 'Computing route & alternatives…';
    $('plan-error').hidden = true;
    try {
      const body = buildRequest();
      if (!body.origin || !body.destination || body.origin.toLowerCase() === body.destination.toLowerCase()) throw new Error('Enter two different locations.');
      let wrapper;
      if (isDemo) {
        const caseId = $('demo-case').value;
        const selectedCase = (await api('/demo/cases')).cases.find(c => c.id === caseId);
        body.origin = selectedCase.origin; body.destination = selectedCase.destination;
        $('origin').value = body.origin; $('destination').value = body.destination;
        wrapper = await api(`/demo/plan?case_id=${encodeURIComponent(caseId)}`, {method:'POST', body:JSON.stringify(body)});
      } else {
        wrapper = await api('/trips/plan', {method:'POST', body:JSON.stringify(body)});
      }
      $('whatif-departure').value = body.departure_at ? body.departure_at.slice(0, 16) : '';
      $('whatif-budget').value = String(body.detour_budget_minutes);
      $('whatif-value').textContent = String(body.detour_budget_minutes);
      renderResults(wrapper);
      showToast(isDemo ? 'Synthetic walkthrough ready — clearly labelled as demo data.' : 'Route and Pareto alternatives calculated.');
    } catch (error) {
      $('plan-error').hidden = false;
      $('plan-error').textContent = `${error.message}\nLive planning requires network access to the configured geocoder, routing and POI providers. Use the labelled offline walkthrough to test the product without live data.`;
      showToast('Trip planning could not complete.');
    } finally {
      button.disabled = false;
      button.innerHTML = original;
    }
  }

  async function runWhatIf() {
    if (!state.tripId) return;
    const button = $('whatif-button'), original = button.textContent;
    button.disabled = true; button.textContent = 'Recomputing…';
    try {
      const changes = {detour_budget_minutes:Number($('whatif-budget').value), discovery_bias:Number($('discovery-bias').value)/100};
      const departure = $('whatif-departure').value;
      if (departure) changes.departure_at = departure;
      const wrapper = await api(`/trips/${state.tripId}/what-if`, {method:'POST', body:JSON.stringify(changes)});
      renderResults(wrapper);
      showToast('What-if run complete — the itinerary was recalculated.');
    } catch (error) { showToast(`What-if failed: ${error.message}`); }
    finally { button.disabled = false; button.textContent = original; }
  }

  async function shareTrip() {
    if (!state.tripId) return;
    try {
      const item = await api(`/trips/${state.tripId}/share`, {method:'POST', body:'{}'});
      state.shareToken = item.token;
      const url = new URL(item.share_url, window.location.origin).toString();
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(url);
      else window.prompt('Copy read-only share link:', url);
      showToast('Read-only share link created.');
    } catch (error) { showToast(`Share failed: ${error.message}`); }
  }

  function openReportModal() {
    $('report-modal').hidden = false;
    $('report-description').focus();
  }
  function closeReportModal() { $('report-modal').hidden = true; }

  async function submitReport(event) {
    event.preventDefault();
    const message = $('report-message');
    message.textContent = 'Submitting for review…';
    try {
      const payload = {
        category: $('report-category').value,
        description: $('report-description').value.trim(),
        latitude: Number($('report-lat').value),
        longitude: Number($('report-lon').value),
      };
      const response = await api('/reports', {method:'POST', body:JSON.stringify(payload)});
      message.textContent = response.possible_duplicate
        ? `Received as possible duplicate of report #${response.duplicate_of}. A moderator will review it; it is not verified.`
        : `Received · report #${response.id} · status: ${response.status}. It is not verified.`;
      $('report-form').reset();
      showToast('Report submitted for moderation.');
    } catch (error) { message.textContent = error.message; }
  }

  async function loadResearch() {
    try {
      const info = await api('/research/experiments');
      $('research-stats').setAttribute('aria-label', info.algorithm);
    } catch (_) { /* Research notes remain visible without API access. */ }
  }

  function setToday() {
    const today = new Date();
    const local = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0,10);
    $('departure-date').min = local;
    $('whatif-departure').min = `${local}T${new Date().toTimeString().slice(0,5)}`;
  }

  function updateDiscoveryDial(value) {
    const v = Math.max(0, Math.min(100, Number(value) || 0));
    $('discovery-value').textContent = v <= 20 ? `${v}% efficiency` : v >= 80 ? `${v}% discovery` : `${v}% discovery`;
    $('discovery-copy').textContent = v <= 20
      ? 'Efficiency-first: the balanced option will lean toward less additional driving.'
      : v >= 80
        ? 'Discovery-first: the balanced option will lean toward cultural relevance, variety and local novelty signals.'
        : 'A thoughtful mix: keep the journey moving, but leave room for places worth remembering.';
  }

  function init() {
    setToday();
    updateDiscoveryDial(Number($('discovery-bias').value));
    checkHealth(); loadResearch();
    $('plan-form').addEventListener('submit', (event) => { event.preventDefault(); submitPlan(false); });
    $('demo-button').addEventListener('click', () => submitPlan(true));
    $('swap-locations').addEventListener('click', () => { const a=$('origin').value; $('origin').value=$('destination').value; $('destination').value=a; });
    $('detour-budget').addEventListener('input', (e) => $('detour-value').textContent = e.target.value);
    $('discovery-bias').addEventListener('input', (e) => updateDiscoveryDial(Number(e.target.value)));
    document.querySelectorAll('[data-mode]').forEach((button) => button.addEventListener('click', () => {
      $('traveler-mode').value = button.dataset.mode;
      document.querySelectorAll('[data-mode]').forEach((item) => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
    }));
    document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
      state.candidateFilter = button.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach((item) => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
      if (state.result) renderCandidateExplorer(state.result, state.activeAlternative);
    }));
    $('whatif-budget').addEventListener('input', (e) => $('whatif-value').textContent = e.target.value);
    document.querySelectorAll('[data-pref]').forEach((input) => input.addEventListener('input', () => input.parentElement.querySelector('b').textContent = input.value));
    $('whatif-button').addEventListener('click', runWhatIf);
    $('share-trip').addEventListener('click', shareTrip);
    $('export-trip').addEventListener('click', () => { if (state.tripId) window.open(`${API}/trips/${state.tripId}/export.pdf`, '_blank', 'noopener'); });
    $('open-report').addEventListener('click', () => {
      if (state.result) { $('report-lat').value = state.result.origin.latitude; $('report-lon').value = state.result.origin.longitude; }
      openReportModal();
    });
    $('close-report').addEventListener('click', closeReportModal);
    $('report-modal').addEventListener('click', (e) => { if (e.target === $('report-modal')) closeReportModal(); });
    $('report-form').addEventListener('submit', submitReport);
    $('fit-map').addEventListener('click', () => { if (state.map && state.result) { const coords = state.result.route.selected_geometry || state.result.route.geometry; if (coords?.length) state.map.fitBounds(L.latLngBounds(coords.map(([lon,lat])=>[lat,lon])).pad(.12)); } });
    window.addEventListener('resize', () => { if (state.map) state.map.invalidateSize(); });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
