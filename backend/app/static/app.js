/* Event bindings and client entry point. */
(() => {
  const { $, state, SAVED_KEY, JOURNAL_KEY, API, readStorage, showToast, setToday, updateDiscoveryDial, checkHealth, loadResearch, submitPlan, syncVehicleFields, validateCustomRoute, applyCustomRoute, runWhatIf, shareTrip, openReportModal, closeReportModal, submitReport, bindWorkspaceNavigation, renderSavedTrips, renderCandidateExplorer, applyVibePreferences } = window.Rahgir;
  function init() {
    const savedStorage = readStorage(SAVED_KEY, []);
    const journalStorage = readStorage(JOURNAL_KEY, {});
    state.savedTrips = Array.isArray(savedStorage) ? savedStorage.filter((item) => item && typeof item.tripId === 'string') : [];
    state.journalEntries = journalStorage && typeof journalStorage === 'object' && !Array.isArray(journalStorage) ? journalStorage : {};
    setToday();
    updateDiscoveryDial(Number($('discovery-bias').value));
    checkHealth(); loadResearch();
    $('plan-form').addEventListener('submit', (event) => { event.preventDefault(); submitPlan(false); });
    $('demo-button').addEventListener('click', () => submitPlan(true));
    $('swap-locations').addEventListener('click', () => { const a=$('origin').value; $('origin').value=$('destination').value; $('destination').value=a; });
    $('detour-budget').addEventListener('input', (e) => $('detour-value').textContent = e.target.value);
    $('vehicle-type').addEventListener('change', syncVehicleFields);
    syncVehicleFields();
    $('validate-custom-route').addEventListener('click', validateCustomRoute);
    $('apply-custom-route').addEventListener('click', applyCustomRoute);
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
    document.querySelectorAll('[data-vibe]').forEach((button) => button.addEventListener('click', () => {
      const active = !button.classList.contains('active');
      button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); applyVibePreferences();
    }));
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
    $('fit-map').addEventListener('click', () => {
      if (state.map && state.result) {
        const coords = state.result.route.selected_geometry || state.result.route.geometry;
        if (coords?.length) { state.map.fitBounds(L.latLngBounds(coords.map(([lon,lat])=>[lat,lon])).pad(.12)); showToast('Map fitted to the complete road route.'); }
        return;
      }
      const schematic = $('route-map').querySelector('svg');
      if (schematic) { schematic.setAttribute('viewBox', '0 0 800 460'); $('route-map').querySelectorAll('.schematic-candidate').forEach((item) => item.classList.remove('focused')); showToast('Schematic reset to show the full route. It is not a navigation map.'); }
      else showToast('No route geometry is available to fit.');
    });
    window.addEventListener('resize', () => { if (state.map) state.map.invalidateSize(); });
    bindWorkspaceNavigation();
    renderSavedTrips();
  }
  window.Rahgir.start = init;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
