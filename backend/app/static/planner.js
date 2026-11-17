/* User actions that change or export the trip. */
(() => {
  const { $, state, API, api, showToast, buildRequest, formatMinutes, renderResults, applyVibePreferences, setWorkspaceView } = window.Rahgir;
  async function submitPlan(isDemo = false) {
    const button = isDemo ? $('demo-button') : $('plan-button');
    const original = button.innerHTML;
    button.disabled = true;
    button.textContent = isDemo ? 'Building offline walkthrough…' : 'Computing route & alternatives…';
    $('plan-error').hidden = true;
    try {
      const body = buildRequest();
      state.planRequest = body;
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
      state.planRequest = {...(state.planRequest || {}), ...changes};
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
      const url = new URL(item.share_url, document.baseURI || window.location.href).toString();
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
  Object.assign(window.Rahgir, { submitPlan, runWhatIf, shareTrip, openReportModal, closeReportModal, submitReport, loadResearch, setToday, updateDiscoveryDial });
})();
