/* Result views: metrics, options, itinerary and candidate explorer. */
(() => {
  const { $, state, showToast, formatMinutes, escapeHtml, escapeAttr, safeHttpsUrl, trustedImageUrl } = window.Rahgir;
  function renderMetrics(result, alternative) {
    const route = result.route, metrics = alternative?.metrics || {};
    const verifiedDuration = alternative?.verified_route_duration_minutes;
    const energy = alternative?.vehicle_cost || result.vehicle_cost_baseline || {status:'not_configured'};
    const costText = energy.status === 'estimated' ? `₹${Number(energy.estimated_cost_inr).toLocaleString('en-IN', {maximumFractionDigits:0})}` : 'Not set';
    const costNote = energy.status === 'estimated' ? `${Number(energy.estimated_units).toFixed(2)} ${energy.unit} · your inputs` : 'Enter vehicle efficiency + price';
    const items = [
      ['BASE ROAD DISTANCE', `${route.distance_km} km`, 'Provider-returned direct route'],
      ['BASE DRIVE', formatMinutes(route.duration_minutes), 'Without discovery stops'],
      ['EXTRA DRIVE', alternative ? formatMinutes(metrics.additional_driving_minutes ?? 0) : '—', 'Complete selected route vs base'],
      ['TOTAL JOURNEY', alternative ? formatMinutes(metrics.estimated_total_minutes_including_stops ?? verifiedDuration ?? route.duration_minutes) : '—', 'Drive plus planned stop time'],
      ['ENERGY COST', costText, costNote],
    ];
    $('route-metrics').innerHTML = items.map(([label,value,note])=>`<div class="metric-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
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
      const routeState = alt.actual_route_feasible === true
        ? 'Provider checked ✓'
        : alt.actual_route_feasible === false
          ? 'Provider check: not feasible'
          : 'Full-route check required';
      return `<button type="button" class="alternative-card ${isActive?'active':''}" data-alt="${index}" aria-pressed="${isActive}">
        <span class="alt-top"><span class="alt-icon">${icon}</span><span class="alt-kicker">OPTION 0${index+1} · PARETO</span></span>
        <h4>${escapeHtml(alt.label)}</h4><p class="alt-description">${description}</p>
        <div class="alt-metric"><span><b>${alt.stops.length}</b> stops</span><span><b>+${formatMinutes(m.additional_driving_minutes)}</b> drive</span><span><b>${formatMinutes(m.estimated_total_minutes_including_stops)}</b> total</span></div>
        <span class="alt-select">${isActive ? 'Currently selected ✓' : 'Explore this option ↗'}</span><small class="alt-validation-state">${routeState}</small>
      </button>`;
    }).join('');
    container.querySelectorAll('[data-alt]').forEach((button) => button.addEventListener('click', async () => {
      const alt = alternatives[Number(button.dataset.alt)];
      await window.Rahgir.selectAlternative(alt);
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
      const sourceUrl = safeHttpsUrl(stop.source_url);
      const articleUrl = safeHttpsUrl(stop.wikipedia_url, ['en.wikipedia.org']);
      const imageUrl = trustedImageUrl(stop.image_url);
      const source = sourceUrl ? `<a class="stop-source" href="${escapeAttr(sourceUrl)}" target="_blank" rel="noreferrer">View map source ↗</a>` : '<span class="stop-source muted">No external place source available in this record</span>';
      const image = imageUrl
        ? `<img class="stop-story-image" src="${escapeAttr(imageUrl)}" alt="${escapeAttr(stop.name)} — image linked through the place's mapped Wikipedia reference" loading="lazy" referrerpolicy="no-referrer"/>`
        : '<div class="stop-story-placeholder" aria-hidden="true">⌂</div>';
      const story = stop.story_summary
        ? `<div class="stop-story-copy">${escapeHtml(stop.story_summary)}${articleUrl ? `<br/><a href="${escapeAttr(articleUrl)}" target="_blank" rel="noreferrer">Read source context ↗</a>` : ''}<small class="image-credit">${escapeHtml(stop.image_attribution || stop.story_source || 'Source-linked article context')}</small></div>`
        : `<div class="stop-story-copy">No linked article context or licensed image is available for this mapped place. Rahgir will not invent a local story.</div>`;
      return `<article class="stop-item stop-card"><div class="stop-index">${String(index+1).padStart(2,'0')}</div><div class="stop-content"><div class="stop-title-row"><h4>${escapeHtml(stop.name)}</h4><span class="place-category">${escapeHtml(String(stop.category || 'place').replaceAll('_',' '))}</span></div><p class="stop-facts">${Math.round(Number(stop.corridor_distance_m || 0))} m from route · ${escapeHtml(hoursLabel)}</p><div class="stop-story">${image}${story}</div><details class="why-details"><summary>Why this place?</summary><ul>${(stop.explanation || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}<li>Cultural signal is a category/tag heuristic, not a verified cultural assessment.</li></ul><div class="evidence-mini"><span>Mapped metadata coverage</span><b>${Math.round(Number(stop.metadata_completeness || 0) * 100)}%</b></div><div class="evidence-track"><i style="width:${Math.max(0, Math.min(100, Number(stop.metadata_completeness || 0) * 100))}%"></i></div><p class="data-caveat">Metadata coverage indicates field completeness only; it is not factual confidence.</p></details>${source}</div><div class="stop-meta"><b>${stop.arrival_at ? new Date(stop.arrival_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : 'ETA —'}</b><small>${Number(stop.stop_duration_minutes || 0)} min stop</small></div></article>`;
    }).join('');
  }

  function candidateGroup(category) {
    const c = String(category || '').toLowerCase();
    if (['fuel','ev_charging','restroom','medical','vehicle_service','parking','rest_area'].includes(c)) return 'facilities';
    if (c === 'food') return 'food';
    if (['heritage','culture','religion'].includes(c)) return 'heritage';
    if (c === 'nature') return 'nature';
    if (c === 'shopping') return 'shopping';
    return 'other';
  }

  function renderCandidateExplorer(result, alternative) {
    const assessments = result.candidate_assessments || (result.candidates || []).map((item) => ({...item, individual_status:'unknown', individual_reasons:['Individual road-network assessment is unavailable.'], caveats:[]}));
    const itineraryIds = new Set(alternative?.stop_ids || (alternative?.stops || []).map((item) => item.id));
    const customIds = new Set(state.customStopIds);
    const filtered = assessments.filter((item) => (state.candidateFilter === 'all' || candidateGroup(item.category) === state.candidateFilter) && (!state.candidateSearch || `${item.name} ${item.category} ${item.story_summary || ''}`.toLocaleLowerCase().includes(state.candidateSearch)));
    $('candidate-count').textContent = `${filtered.length} of ${assessments.length} mapped places`;
    $('candidate-empty').hidden = filtered.length > 0;
    $('custom-stop-count').textContent = `${customIds.size} custom stops selected · max ${state.planRequest?.max_stops ?? '—'}`;
    $('candidate-grid').innerHTML = filtered.map((item) => {
      const inItinerary = itineraryIds.has(item.id);
      const inCustom = customIds.has(item.id);
      const blocked = item.individual_status === 'blocked';
      const status = inItinerary ? 'Current option' : blocked ? 'Fails single-stop check' : item.individual_status === 'eligible' ? 'Single-stop feasible' : 'Not assessed';
      const reasonItems = blocked ? (item.individual_reasons || []) : (item.why_it_might_fit || ['This place is mapped near the route. Check the complete route before adding it.']);
      const detour = item.single_stop_detour_minutes == null ? 'Single-stop detour unavailable' : `+${Math.round(item.single_stop_detour_minutes)} min single-stop drive`;
      const sourceUrl = safeHttpsUrl(item.source_url);
      const articleUrl = safeHttpsUrl(item.wikipedia_url, ['en.wikipedia.org']);
      const imageUrl = trustedImageUrl(item.image_url);
      const source = sourceUrl ? `<a href="${escapeAttr(sourceUrl)}" target="_blank" rel="noreferrer">Map source ↗</a>` : '<span>No source link</span>';
      const image = imageUrl ? `<img class="candidate-card-image" src="${escapeAttr(imageUrl)}" alt="${escapeAttr(item.name)}" loading="lazy" referrerpolicy="no-referrer"/>` : '<div class="candidate-image-placeholder" aria-hidden="true">⌂</div>';
      return `<article class="candidate-card ${inItinerary?'selected':''} ${blocked?'blocked':''}">${image}<div class="candidate-card-top"><span class="candidate-status ${inItinerary?'good':blocked?'warning':'neutral'}">${escapeHtml(status)}</span><span class="candidate-category">${escapeHtml(String(item.category || 'place').replaceAll('_',' '))}</span></div><h4>${escapeHtml(item.name)}</h4><p class="candidate-metric">${escapeHtml(detour)} ${item.single_stop_detour_km == null ? '' : `· +${Number(item.single_stop_detour_km).toFixed(1)} km`}</p><details><summary>Why / why not?</summary><ul>${reasonItems.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>${(item.caveats || []).map((caveat) => `<p class="candidate-caveat">${escapeHtml(caveat)}</p>`).join('')}</details><div class="candidate-card-foot">${source}${articleUrl ? `<a href="${escapeAttr(articleUrl)}" target="_blank" rel="noreferrer">Linked story ↗</a>` : ''}<button type="button" data-locate="${escapeAttr(item.id)}">Show on map ↗</button></div><label class="candidate-add-control"><input type="checkbox" data-custom-select="${escapeAttr(item.id)}" ${inCustom?'checked':''}/> Add to my route</label></article>`;
    }).join('');
    $('candidate-grid').querySelectorAll('[data-locate]').forEach((button) => button.addEventListener('click', () => {
      const marker = state.candidateMarkers[button.dataset.locate];
      if (marker && state.map) { state.map.setView(marker.getLatLng(), Math.max(state.map.getZoom(), 12), {animate:true}); marker.openPopup(); $('route-map').scrollIntoView({behavior:'smooth', block:'center'}); return; }
      const schematic = $('route-map').querySelector(`[data-schematic-candidate="${CSS.escape(button.dataset.locate)}"]`);
      if (schematic) {
        $('route-map').querySelectorAll('.schematic-candidate').forEach((item) => item.classList.remove('focused'));
        schematic.classList.add('focused');
        $('route-map').scrollIntoView({behavior:'smooth', block:'center'});
        showToast('Candidate highlighted on the route schematic. This schematic is not a navigation map.');
      } else showToast('Candidate coordinates are not available on the active map.');
    }));
    $('candidate-grid').querySelectorAll('[data-custom-select]').forEach((input) => input.addEventListener('change', () => {
      const id = input.dataset.customSelect;
      const ids = new Set(state.customStopIds);
      if (input.checked) {
        const limit = Number(state.planRequest?.max_stops ?? 4);
        if (ids.size >= limit) { input.checked = false; showToast(`Your current plan allows at most ${limit} stops.`); return; }
        ids.add(id);
      } else ids.delete(id);
      state.customStopIds = [...ids];
      state.customValidation = null;
      $('apply-custom-route').disabled = true;
      $('custom-route-result').textContent = 'Selection changed. Validate the complete stop sequence before using it.';
      $('custom-stop-count').textContent = `${ids.size} custom stops selected · max ${window.Rahgir.limitLabel()}`;
    }));
    const notSelected = assessments.filter((item) => !itineraryIds.has(item.id));
    $('not-selected-list').innerHTML = notSelected.length ? notSelected.map((item) => {
      const reasons = item.individual_status === 'blocked' ? (item.individual_reasons || []) : ['Not selected in this multi-stop combination. Validate a custom sequence to check it with other stops.'];
      return `<div class="not-selected-row"><b>${escapeHtml(item.name)}</b><span>${item.individual_status === 'blocked' ? 'Does not pass single-stop checks' : 'Not in selected combination'}</span><small>${reasons.map(escapeHtml).join(' ')}</small></div>`;
    }).join('') : '<p class="small-note">Every mapped candidate is included in this selected itinerary.</p>';
  }
  Object.assign(window.Rahgir, { renderMetrics, renderAlternatives, renderRouteInsight, renderJourneyPulse, renderStops, candidateGroup, renderCandidateExplorer });
})();
