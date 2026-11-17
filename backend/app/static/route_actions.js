/* Route validation and state transitions for selected itineraries. */
(() => {
  const { $, state, api, showToast, formatMinutes, escapeHtml, renderMetrics, renderStops, renderRouteInsight, renderJourneyPulse, renderCandidateExplorer, renderMap, renderNavigationLink, renderAlternatives, enterWorkspace, setWorkspaceView } = window.Rahgir;
  function limitLabel() { return String(state.planRequest?.max_stops ?? 4); }

  function validationMarkup(validation) {
    const status = validation.status === 'confirmed_feasible' ? 'CONFIRMED FEASIBLE' : 'CONSTRAINTS NOT MET';
    const rows = [
      ['Complete route', `${validation.distance_km} km · ${formatMinutes(validation.duration_minutes)} drive`],
      ['Extra driving', `+${validation.additional_distance_km} km · ${formatMinutes(validation.additional_driving_minutes)}`],
      ['Total journey', formatMinutes(validation.total_journey_minutes)],
      ['Stop limit', `${validation.constraints.stop_count} / ${validation.constraints.max_stops}`],
    ];
    const cost = validation.vehicle_cost?.status === 'estimated' ? `₹${Number(validation.vehicle_cost.estimated_cost_inr).toLocaleString('en-IN', {maximumFractionDigits:0})} estimated` : 'Vehicle cost not configured';
    const warnings = (validation.warnings || []).map((warning) => `<li>${escapeHtml(warning)}</li>`).join('');
    return `<div class="route-validation-summary ${validation.feasible?'pass':'fail'}"><b>${status}</b><div class="route-validation-grid">${rows.map(([key,value])=>`<div><span>${key}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}<div><span>Energy cost</span><strong>${escapeHtml(cost)}</strong></div></div>${warnings?`<ul class="route-validation-warnings">${warnings}</ul>`:'<p>No closed stops were found in supported mapped opening-hours rules. Unknown hours remain a caveat.</p>'}</div>`;
  }

  async function validateCustomRoute() {
    if (!state.tripId || !state.result) { showToast('Plan or open a journey before building a custom route.'); return; }
    const button = $('validate-custom-route');
    button.disabled = true;
    button.textContent = 'Checking road route…';
    $('apply-custom-route').disabled = true;
    $('custom-route-result').textContent = 'Calling the route provider for your complete stop sequence…';
    try {
      const validation = await api(`/trips/${encodeURIComponent(state.tripId)}/route-preview`, {method:'POST', body:JSON.stringify({stop_ids: state.customStopIds})});
      state.customValidation = validation;
      $('custom-route-result').innerHTML = validationMarkup(validation);
      $('apply-custom-route').disabled = !validation.feasible;
      if (!validation.feasible) showToast('This combination exceeds a journey limit or includes a mapped-closed stop.');
      else showToast('The complete custom route passed provider validation.');
    } catch (error) {
      state.customValidation = null;
      $('custom-route-result').textContent = `Route validation failed: ${error.message}. No custom route has been marked feasible.`;
      showToast('The custom route could not be verified.');
    } finally {
      button.disabled = false;
      button.textContent = 'Check this route ↗';
    }
  }

  function applyCustomRoute() {
    const validation = state.customValidation;
    if (!validation?.feasible) { showToast('Validate a feasible custom route first.'); return; }
    const candidates = new Map((state.result.candidates || []).map((item) => [item.id, item]));
    const stops = (validation.stop_assessments || []).map((assessment) => {
      const source = candidates.get(assessment.id);
      return {...source, arrival_at: assessment.arrival_at, hours_status: assessment.hours_status, stop_duration_minutes: state.planRequest?.stop_duration_minutes ?? 30};
    });
    const metrics = {
      additional_driving_minutes: validation.additional_driving_minutes,
      additional_distance_km: validation.additional_distance_km,
      estimated_total_minutes_including_stops: validation.total_journey_minutes,
      total_route_distance_km: validation.distance_km,
    };
    const alternative = {
      label: 'Custom route', stop_ids: validation.stop_ids, stops, metrics,
      verified_route_distance_km: validation.distance_km,
      verified_route_duration_minutes: validation.duration_minutes,
      vehicle_cost: validation.vehicle_cost,
      actual_route_feasible: true,
      route_validation_status: 'confirmed_feasible',
      route_validation: validation,
      constraints: {
        detour_budget_respected: validation.constraints.detour_budget_respected,
        max_journey_time_respected: validation.constraints.max_journey_time_respected,
        provider_route_recheck_completed: true,
        max_stops_respected: validation.constraints.max_stops_respected,
      },
    };
    state.activeAlternative = alternative;
    state.result.route.selected_geometry = validation.geometry;
    state.result.route.selected_geometry_provider = validation.provider;
    $('selected-label').textContent = 'Custom route itinerary';
    $('feasible-chip').textContent = 'Provider confirmed feasible';
    renderMetrics(state.result, alternative);
    renderStops(alternative);
    renderRouteInsight(state.result, alternative);
    renderJourneyPulse(state.result, alternative);
    renderCandidateExplorer(state.result, alternative);
    renderMap(state.result, alternative);
    $('route-proof-result').innerHTML = validationMarkup(validation);
    setWorkspaceView('dashboard');
    $('stop-list').scrollIntoView({behavior:'smooth', block:'start'});
    showToast('Custom route is now your selected itinerary.');
  }

  async function selectAlternative(alternative) {
    state.activeAlternative = alternative;
    const validationPanel = $('route-proof-result');
    $('feasible-chip').textContent = 'Checking complete route…';
    validationPanel.textContent = 'Checking the complete stop sequence with the configured routing provider. Matrix estimates alone are not treated as final feasibility.';
    document.querySelectorAll('.alternative-card').forEach((card, index) => {
      const active = state.result.alternatives[index]?.label === alternative.label;
      card.classList.toggle('active', active);
      card.setAttribute('aria-pressed', active ? 'true' : 'false');
      const selectText = card.querySelector('.alt-select');
      if (selectText) selectText.textContent = active ? 'Currently selected ✓' : 'Explore this option ↗';
    });
    $('selected-label').textContent = `${alternative.label} itinerary`;
    let validation = alternative.route_validation;
    if (!validation && state.tripId) {
      try {
        validation = await api(`/trips/${encodeURIComponent(state.tripId)}/route-preview`, {
          method: 'POST',
          body: JSON.stringify({stop_ids: alternative.stop_ids || []}),
        });
        alternative.route_validation = validation;
        alternative.actual_route_feasible = validation.feasible === true;
        alternative.route_validation_status = validation.status;
        alternative.verified_route_distance_km = validation.distance_km;
        alternative.verified_route_duration_minutes = validation.duration_minutes;
        alternative.vehicle_cost = validation.vehicle_cost;
        alternative.metrics = {
          ...(alternative.metrics || {}),
          additional_driving_minutes: validation.additional_driving_minutes,
          additional_distance_km: validation.additional_distance_km,
          estimated_total_minutes_including_stops: validation.total_journey_minutes,
          total_route_distance_km: validation.distance_km,
        };
        const candidates = new Map((state.result.candidates || []).map((item) => [item.id, item]));
        alternative.stops = (validation.stop_assessments || []).map((assessment) => ({
          ...candidates.get(assessment.id),
          arrival_at: assessment.arrival_at,
          hours_status: assessment.hours_status,
          stop_duration_minutes: state.planRequest?.stop_duration_minutes ?? 30,
        }));
      } catch (error) {
        alternative.actual_route_feasible = null;
        alternative.route_validation_status = 'unverified_provider_error';
        alternative.route_validation_error = error.message;
      }
    }
    const verified = alternative.actual_route_feasible === true && validation?.status === 'confirmed_feasible';
    $('feasible-chip').textContent = verified ? 'Provider confirmed feasible' : alternative.actual_route_feasible === false ? 'Constraints not met' : 'Not provider-verified';
    if (validation) {
      state.result.route.selected_geometry = validation.feasible ? validation.geometry : null;
      state.result.route.selected_geometry_provider = validation.feasible ? validation.provider : null;
      $('route-proof-result').innerHTML = validationMarkup(validation);
    } else {
      state.result.route.selected_geometry = null;
      state.result.route.selected_geometry_provider = null;
      $('route-proof-result').textContent = alternative.route_validation_error || 'This option has not passed a complete via-point route check. It is not labelled feasible.';
    }
    renderMetrics(state.result, alternative);
    renderStops(alternative);
    renderRouteInsight(state.result, alternative);
    renderJourneyPulse(state.result, alternative);
    renderCandidateExplorer(state.result, alternative);
    renderMap(state.result, alternative);
    renderAlternatives(state.result.alternatives, alternative);
    if (!validation && alternative.route_validation_error) showToast(`Full-route check unavailable: ${alternative.route_validation_error}`);
    else if (validation && !validation.feasible) showToast('This option does not pass the complete route constraints.');
  }

  function renderResults(wrapper) {
    const result = wrapper.result || wrapper;
    state.tripId = wrapper.trip_id || wrapper.id || result.trip_id || null;
    state.result = result;
    state.planRequest = wrapper.request || state.planRequest || null;
    state.customStopIds = [];
    state.customValidation = null;
    state.activeAlternative = result.selected_alternative || null;
    $('apply-custom-route').disabled = true;
    $('custom-route-result').textContent = 'Select mapped places below and validate the complete sequence.';
    $('save-trip').textContent = state.savedTrips.some((item) => item.tripId === state.tripId) ? 'Saved ✓' : 'Save journey ☆';
    $('workspace-route-name').textContent = `${result.origin.label.split(',')[0]} → ${result.destination.label.split(',')[0]}`;
    enterWorkspace('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    $('results-subtitle').textContent = `${result.origin.label.split(',')[0]} to ${result.destination.label.split(',')[0]} · ${result.candidate_count} mapped corridor candidates examined`;
    $('demo-banner').hidden = result.mode !== 'synthetic_demo';
    renderAlternatives(result.alternatives, state.activeAlternative);
    renderMetrics(result, state.activeAlternative);
    renderStops(state.activeAlternative);
    renderRouteInsight(result, state.activeAlternative);
    renderJourneyPulse(result, state.activeAlternative);
    renderCandidateExplorer(result, state.activeAlternative);
    renderMap(result, state.activeAlternative);
    if (state.activeAlternative?.route_validation) {
      $('route-proof-result').innerHTML = validationMarkup(state.activeAlternative.route_validation);
      $('feasible-chip').textContent = 'Provider confirmed feasible';
    } else if (state.activeAlternative) {
      $('route-proof-result').textContent = state.activeAlternative.route_validation_error || 'No complete via-point route check is available for this option.';
      $('feasible-chip').textContent = 'Not provider-verified';
    } else {
      $('route-proof-result').textContent = result.route_validation_summary?.message || 'No itinerary passed the final route validation. The base road route is still shown.';
      $('feasible-chip').textContent = 'No confirmed stop sequence';
    }
    $('safety-insight').querySelector('p').textContent = result.safety?.explanation || 'Insufficient safety data. Missing incident reports do not establish that a road is safe.';
    $('weather-insight').querySelector('p').textContent = result.weather?.explanation || 'No forecast data was used in this plan.';
    $('plan-error').hidden = true;
  }
  Object.assign(window.Rahgir, { limitLabel, validationMarkup, validateCustomRoute, applyCustomRoute, selectAlternative, renderResults });
})();
