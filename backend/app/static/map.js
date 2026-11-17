/* Map lifecycle and provider/schematic rendering. */
(() => {
  const { $, state, showToast, escapeHtml, escapeAttr } = window.Rahgir;
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
    const candidates = (result.candidates || []).filter((item) => Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)));
    const linePoints = routePoints.length > 1 ? routePoints : [start, ...stops.map((s) => [s.latitude, s.longitude]), end];
    const all = [...linePoints, start, ...stops.map((s) => [s.latitude, s.longitude]), ...candidates.map((item) => [Number(item.latitude), Number(item.longitude)]), end];
    const width = 800, height = 460, pad = 65;
    const lats = all.map(x => x[0]), lons = all.map(x => x[1]);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const dx = Math.max(.001, maxLon - minLon), dy = Math.max(.001, maxLat - minLat);
    const point = ([lat, lon]) => [pad + (lon - minLon) / dx * (width - 2 * pad), height - pad - (lat - minLat) / dy * (height - 2 * pad)];
    const pts = linePoints.map(point);
    const path = pts.map((p,i)=>`${i?'L':'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
    const candidateMarkers = candidates.map((candidate) => {
      const p = point([Number(candidate.latitude), Number(candidate.longitude)]);
      return `<g class="schematic-candidate" data-schematic-candidate="${escapeAttr(candidate.id)}" tabindex="0" role="button" aria-label="Show ${escapeAttr(candidate.name)}"><circle cx="${p[0]}" cy="${p[1]}" r="5" fill="#82988a" stroke="#fffefa" stroke-width="2"/></g>`;
    }).join('');
    const markers = [
      {xy: start, label: 'START', fill: '#18292b'},
      ...stops.map((stop, i) => ({xy: [stop.latitude, stop.longitude], label: String(i + 1).padStart(2, '0'), fill: '#526d59'})),
      {xy: end, label: 'END', fill: '#c78c3d'},
    ].map((item) => {
      const p = point(item.xy);
      return `<circle cx="${p[0]}" cy="${p[1]}" r="${item.label==='START'||item.label==='END'?10:7}" fill="${item.fill}" stroke="#fffefa" stroke-width="3"/><text x="${p[0]}" y="${p[1]-16}" text-anchor="middle" font-size="11" fill="#18292b">${item.label}</text>`;
    }).join('');
    host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Route geometry schematic without map tiles" style="width:100%;height:100%;min-height:430px;background:#e8e9df"><defs><pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M 34 0 L 0 0 0 34" fill="none" stroke="#cfd8cc" stroke-width="1"/></pattern></defs><rect width="100%" height="100%" fill="url(#grid)"/><path d="${path}" fill="none" stroke="#c75d3d" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="${path}" fill="none" stroke="#fffefa" stroke-width="1.4" stroke-dasharray="7 10"/>${candidateMarkers}${markers}<text x="24" y="30" font-size="10" fill="#64716c" font-family="monospace">SCHEMATIC GEOMETRY · MAP TILES UNAVAILABLE · NOT FOR NAVIGATION</text></svg>`;
    $('fit-map').disabled = false;
    $('fit-map').title = 'Reset the schematic to the complete route';
  }


  function renderMap(result, alternative) {
    const geometry = result.route.selected_geometry || result.route.geometry;
    const demo = result.mode === 'synthetic_demo';
    renderNavigationLink(result, alternative, demo);
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
    $('fit-map').disabled = false;
    $('fit-map').title = 'Fit the complete road route in the map';
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

  function renderNavigationLink(result, alternative, demo) {
    const directions = $('google-route-link');
    const validEndpoints = Number.isFinite(Number(result.origin.latitude)) && Number.isFinite(Number(result.origin.longitude)) && Number.isFinite(Number(result.destination.latitude)) && Number.isFinite(Number(result.destination.longitude));
    const providerConfirmed = alternative?.actual_route_feasible === true && alternative?.route_validation?.status === 'confirmed_feasible';
    if (directions && !demo && validEndpoints && providerConfirmed) {
      const waypoints = (alternative?.stops || []).slice(0, 8).map((stop) => `${Number(stop.latitude)},${Number(stop.longitude)}`).join('|');
      const params = new URLSearchParams({ api: '1', origin: `${result.origin.latitude},${result.origin.longitude}`, destination: `${result.destination.latitude},${result.destination.longitude}`, travelmode: 'driving' });
      if (waypoints) params.set('waypoints', waypoints);
      directions.href = `https://www.google.com/maps/dir/?${params.toString()}`;
      directions.hidden = false;
    } else if (directions) {
      directions.hidden = true;
      directions.removeAttribute('href');
    }
  }
  Object.assign(window.Rahgir, { initMap, customIcon, renderSchematicMap, renderMap, renderNavigationLink });
})();
