/* Browser-local saved journeys, journal and workspace navigation. */
(() => {
  const { $, state, SAVED_KEY, JOURNAL_KEY, DEFAULT_PREFERENCES, VIBE_PREFERENCES, api, showToast, escapeHtml, escapeAttr, readStorage, writeStorage } = window.Rahgir;
  function enterWorkspace(view = 'dashboard') {
    $('results').hidden = false;
    document.body.classList.add('workspace-active');
    const mapCard = $('map-card');
    if (mapCard && $('workspace-map-slot') && mapCard.parentElement !== $('workspace-map-slot')) $('workspace-map-slot').appendChild(mapCard);
    setWorkspaceView(view);
    window.setTimeout(() => { if (state.map) state.map.invalidateSize(); }, 140);
  }

  function exitWorkspace() {
    document.body.classList.remove('workspace-active');
    const mapCard = $('map-card');
    if (mapCard && $('planner-map-slot') && mapCard.parentElement !== $('planner-map-slot')) $('planner-map-slot').appendChild(mapCard);
    $('results').hidden = true;
    $('planner').scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.setTimeout(() => { if (state.map) state.map.invalidateSize(); }, 180);
  }

  function setWorkspaceView(view) {
    state.workspaceView = view;
    const showSaved = view === 'saved';
    const showJournal = view === 'journal';
    $('workspace-dashboard').hidden = showSaved || showJournal;
    $('workspace-saved').hidden = !showSaved;
    $('workspace-journal').hidden = !showJournal;
    document.querySelectorAll('[data-workspace]').forEach((button) => button.classList.toggle('active', button.dataset.workspace === view));
    document.querySelectorAll('[data-topnav]').forEach((button) => {
      const target = button.dataset.topnav;
      const active = (view === 'dashboard' || view === 'routes') ? target === 'trips' : view === 'saved' ? target === 'dashboard' : target === 'explore';
      button.classList.toggle('active', active);
    });
    if (showSaved) renderSavedTrips();
    if (showJournal) renderJournal();
    if (view === 'routes' && state.result) window.setTimeout(() => $('stop-list').scrollIntoView({ behavior: 'smooth', block: 'start' }), 70);
    if (view === 'dashboard' && state.result) window.setTimeout(() => $('workspace-context').scrollIntoView({ behavior: 'smooth', block: 'start' }), 70);
  }

  function applyVibePreferences() {
    const active = [...document.querySelectorAll('[data-vibe].active')].map((button) => button.dataset.vibe);
    const values = { ...DEFAULT_PREFERENCES };
    active.forEach((vibe) => Object.entries(VIBE_PREFERENCES[vibe] || {}).forEach(([key, score]) => { values[key] = Math.max(values[key] || 0, score); }));
    document.querySelectorAll('[data-pref]').forEach((input) => {
      input.value = String(values[input.dataset.pref] ?? DEFAULT_PREFERENCES[input.dataset.pref] ?? 50);
      const label = input.parentElement.querySelector('b');
      if (label) label.textContent = input.value;
    });
  }

  function renderSavedTrips() {
    const container = $('saved-trip-list');
    const saved = state.savedTrips.slice().sort((a, b) => (b.savedAt || '').localeCompare(a.savedAt || ''));
    if (!saved.length) {
      container.innerHTML = '<div class="saved-empty">No saved journeys yet. Plan a route and choose <b>Save journey</b> to keep it here on this device.</div>';
      return;
    }
    container.innerHTML = saved.map((trip) => `<article class="saved-trip-card"><span class="saved-trip-meta">SAVED ${escapeHtml(new Date(trip.savedAt).toLocaleString())}</span><h3>${escapeHtml(trip.origin)} <span aria-hidden="true">→</span> ${escapeHtml(trip.destination)}</h3><p>${escapeHtml(trip.mode || 'Road journey')} · Trip ID ${escapeHtml(String(trip.tripId).slice(0, 8))}</p><div class="saved-trip-actions"><button type="button" data-open-saved="${escapeAttr(trip.tripId)}">Open journey ↗</button><button type="button" class="danger" data-delete-saved="${escapeAttr(trip.tripId)}">Remove</button></div></article>`).join('');
    container.querySelectorAll('[data-open-saved]').forEach((button) => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const wrapper = await api(`/trips/${encodeURIComponent(button.dataset.openSaved)}`);
        window.Rahgir.renderResults(wrapper);
        showToast('Saved journey reopened.');
      } catch (error) { showToast(`This trip could not be restored: ${error.message}. The server may have restarted and cleared its temporary database.`); }
      finally { button.disabled = false; }
    }));
    container.querySelectorAll('[data-delete-saved]').forEach((button) => button.addEventListener('click', () => {
      state.savedTrips = state.savedTrips.filter((trip) => trip.tripId !== button.dataset.deleteSaved);
      writeStorage(SAVED_KEY, state.savedTrips);
      renderSavedTrips();
      showToast('Removed from this browser’s saved list.');
    }));
  }

  function saveCurrentTrip() {
    if (!state.tripId || !state.result) { showToast('Plan a journey before saving it.'); return; }
    const trip = {
      tripId: state.tripId,
      origin: state.result.origin?.label || 'Origin unavailable',
      destination: state.result.destination?.label || 'Destination unavailable',
      mode: state.activeAlternative?.label || 'Road journey',
      savedAt: new Date().toISOString(),
    };
    state.savedTrips = [trip, ...state.savedTrips.filter((item) => item.tripId !== state.tripId)].slice(0, 60);
    if (writeStorage(SAVED_KEY, state.savedTrips)) {
      $('save-trip').textContent = 'Saved ✓';
      renderSavedTrips();
      showToast('Journey saved to this browser.');
    }
  }

  function renderJournal() {
    const container = $('journal-entry-list');
    const entries = state.tripId ? (state.journalEntries[state.tripId] || []) : [];
    if (!entries.length) {
      container.innerHTML = '<div class="saved-empty">No notes for this journey yet. Add a reminder, place to verify, or memory you want to keep.</div>';
      return;
    }
    container.innerHTML = entries.slice().sort((a, b) => b.createdAt.localeCompare(a.createdAt)).map((entry) => `<article class="journal-entry"><h3>${escapeHtml(entry.title)}</h3><p>${escapeHtml(entry.body)}</p><footer><time>${escapeHtml(new Date(entry.createdAt).toLocaleString())}</time><button type="button" data-delete-note="${escapeAttr(entry.id)}">Delete note</button></footer></article>`).join('');
    container.querySelectorAll('[data-delete-note]').forEach((button) => button.addEventListener('click', () => {
      const key = state.tripId;
      state.journalEntries[key] = (state.journalEntries[key] || []).filter((entry) => entry.id !== button.dataset.deleteNote);
      writeStorage(JOURNAL_KEY, state.journalEntries);
      renderJournal();
    }));
  }

  function saveJournalNote(event) {
    event.preventDefault();
    if (!state.tripId) { $('journal-status').textContent = 'Open a saved trip or plan one before adding a note.'; return; }
    const title = $('journal-note-title').value.trim();
    const body = $('journal-note-body').value.trim();
    if (!title || !body) return;
    const entry = { id: (window.crypto?.randomUUID?.() || `note-${Date.now()}`), title: title.slice(0, 90), body: body.slice(0, 2000), createdAt: new Date().toISOString() };
    state.journalEntries[state.tripId] = [entry, ...(state.journalEntries[state.tripId] || [])].slice(0, 100);
    if (writeStorage(JOURNAL_KEY, state.journalEntries)) {
      $('journal-form').reset();
      $('journal-status').textContent = 'Saved locally in this browser. It is not synced or uploaded.';
      renderJournal();
      showToast('Journal note saved on this device.');
    }
  }

  function bindWorkspaceNavigation() {
    document.querySelectorAll('[data-workspace]').forEach((button) => button.addEventListener('click', () => setWorkspaceView(button.dataset.workspace)));
    document.querySelectorAll('[data-topnav]').forEach((button) => button.addEventListener('click', () => {
      const target = button.dataset.topnav;
      setWorkspaceView(target === 'explore' ? 'routes' : 'dashboard');
      if (target === 'explore' && state.result) window.setTimeout(() => $('candidate-heading').scrollIntoView({ behavior: 'smooth', block: 'start' }), 90);
    }));
    $('workspace-new-trip').addEventListener('click', exitWorkspace);
    $('workspace-exit').addEventListener('click', exitWorkspace);
    $('workspace-brand').addEventListener('click', (event) => { event.preventDefault(); exitWorkspace(); });
    $('workspace-back-to-top').addEventListener('click', () => $('results').scrollIntoView({ behavior: 'smooth', block: 'start' }));
    $('landing-saved-link').addEventListener('click', (event) => { event.preventDefault(); enterWorkspace('saved'); });
    $('workspace-search').addEventListener('input', (event) => {
      state.candidateSearch = event.target.value.trim().toLocaleLowerCase();
      if (state.result) window.Rahgir.renderCandidateExplorer(state.result, state.activeAlternative);
      if (state.candidateSearch && state.workspaceView === 'dashboard') setWorkspaceView('routes');
    });
    $('save-trip').addEventListener('click', saveCurrentTrip);
    $('journal-form').addEventListener('submit', saveJournalNote);
  }
  Object.assign(window.Rahgir, { enterWorkspace, exitWorkspace, setWorkspaceView, applyVibePreferences, renderSavedTrips, saveCurrentTrip, renderJournal, saveJournalNote, bindWorkspaceNavigation });
})();
