(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { ambiguities: [], requirements: [], revision: null, trace: null };
  const configuredBase = window.SPECFORGE_API_BASE || new URLSearchParams(location.search).get('api_base') || localStorage.getItem('specforge.apiBase') || location.origin;
  $('api-base').value = configuredBase;

  function apiBase() { return $('api-base').value.trim().replace(/\/$/, '') || location.origin; }
  function authHeaders(extra = {}) { const token = $('token').value.trim(); return { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra }; }
  function key() { if (window.crypto?.randomUUID) return window.crypto.randomUUID(); return `${Date.now()}-${Math.random()}`; }
  function log(message, type = '') {
    const list = $('event-list');
    if (list.classList.contains('empty')) { list.classList.remove('empty'); list.textContent = ''; }
    const row = document.createElement('div'); row.className = `event ${type}`;
    const time = document.createElement('time'); time.textContent = new Date().toLocaleTimeString();
    const text = document.createElement('span'); text.textContent = message; row.append(time, text); list.prepend(row);
  }
  function problemMessage(problem, fallback) {
    if (!problem || typeof problem !== 'object') return fallback;
    const payload = problem.detail && typeof problem.detail === 'object' ? problem.detail : problem;
    const code = payload.code ? ` [${payload.code}]` : '';
    return `${payload.detail || payload.title || fallback}${code}`;
  }
  async function request(path, options = {}) {
    const response = await fetch(`${apiBase()}${path}`, { ...options, headers: authHeaders(options.headers || {}) });
    const raw = await response.text(); let body = null;
    try { body = raw ? JSON.parse(raw) : null; } catch (_) { body = raw; }
    if (!response.ok) { const error = new Error(problemMessage(body, `Request failed (${response.status})`)); error.status = response.status; error.problem = body; throw error; }
    return body;
  }
  function showError(error, action) {
    const payload = error.problem?.detail && typeof error.problem.detail === 'object' ? error.problem.detail : error.problem;
    const code = payload?.code;
    if (code === 'OPEN_AMBIGUITY') { setGate('open', 'Generation blocked by the ambiguity gate.', error.message); }
    if (code === 'STALE_VERSION' || code === 'DIGEST_MISMATCH') {
      setGate('error', 'Approval rejected: revision is stale.', `${error.message} Refresh traceability and generate from the current source snapshot.`);
      $('revision-status').className = 'status-chip bad'; $('revision-status').textContent = 'STALE';
    }
    log(`${action}: ${error.message}`, code === 'OPEN_AMBIGUITY' || code?.startsWith('STALE') ? 'warn' : 'error');
    $('connection-status').className = 'status-chip bad'; $('connection-status').textContent = 'API error';
  }
  function setGate(kind, title, detail) {
    const gate = $('gate'); gate.className = `gate ${kind}`; gate.querySelector('strong').textContent = title; gate.querySelector('p').textContent = detail;
  }
  function renderRequirements() {
    const list = $('requirements-list'); $('requirements-count').textContent = state.requirements.length;
    if (!state.requirements.length) { list.className = 'list empty'; list.textContent = 'No requirements returned.'; return; }
    list.className = 'list'; list.innerHTML = state.requirements.map((r) => `<article class="item"><div class="item-title">${escapeHtml(r.statement || 'Untitled requirement')}</div><div class="item-meta"><span class="tag">${escapeHtml(r.requirement_type || 'requirement')}</span><span>source ${escapeHtml(r.source_span || 'n/a')}</span></div></article>`).join('');
  }
  function renderAmbiguities() {
    const list = $('ambiguities-list'); $('ambiguities-count').textContent = state.ambiguities.length;
    const blocking = state.ambiguities.filter((a) => ['OPEN', 'UNRESOLVED'].includes(a.resolution_status || a.status) && ['HIGH', 'CRITICAL'].includes(a.severity));
    if (blocking.length) setGate('open', `${blocking.length} high-impact ambiguity${blocking.length === 1 ? '' : 'ies'} block generation.`, 'Record a stakeholder decision for each item before requesting a revision.');
    else if (state.ambiguities.length) setGate('clear', 'Ambiguity gate is clear.', 'No open HIGH or CRITICAL ambiguity remains for this requirement set.');
    else setGate('neutral', 'No ambiguities returned.', 'Confirm the requirement set ID and API response before generating.');
    if (!state.ambiguities.length) { list.className = 'list empty'; list.textContent = 'No ambiguities returned.'; $('decision-form').classList.add('hidden'); $('generate-btn').disabled = true; return; }
    list.className = 'list'; list.innerHTML = state.ambiguities.map((a) => { const status = a.resolution_status || a.status || 'UNKNOWN'; return `<article class="item"><div class="item-title">${escapeHtml(a.question || 'No question')}</div><div class="item-meta"><span class="tag ${String(a.severity || '').toLowerCase()}">${escapeHtml(a.severity || 'unspecified')}</span><span class="tag ${status === 'RESOLVED' ? 'resolved' : ''}">${escapeHtml(status)}</span><span>${escapeHtml(a.id)}</span></div></article>`; }).join('');
    const select = $('ambiguity-id'); select.innerHTML = state.ambiguities.filter((a) => (a.resolution_status || a.status) !== 'RESOLVED').map((a) => `<option value="${escapeAttr(a.id)}">${escapeHtml(a.id)} · ${escapeHtml(a.question || '')}</option>`).join('');
    $('decision-form').classList.toggle('hidden', !select.options.length); $('generate-btn').disabled = blocking.length > 0;
  }
  function renderTrace(trace) {
    state.trace = trace; const linked = trace.linked_requirements ?? trace.requirements_linked ?? 0; const cases = trace.linked_acceptance_cases ?? trace.acceptance_cases_linked ?? 0;
    $('traceability').className = 'trace'; $('traceability').innerHTML = `<div class="trace-grid"><div class="trace-stat"><strong>${escapeHtml(linked)}</strong><span>requirements linked</span></div><div class="trace-stat"><strong>${escapeHtml(cases)}</strong><span>acceptance cases linked</span></div><div class="trace-stat"><strong>${escapeHtml(trace.status || 'UNKNOWN')}</strong><span>traceability status</span></div></div>`;
  }
  async function loadState() {
    const setId = $('set-id').value.trim(); if (!setId) { log('Load: enter a requirement set ID.', 'warn'); return; }
    localStorage.setItem('specforge.apiBase', apiBase()); $('connection-status').className = 'status-chip neutral'; $('connection-status').textContent = 'Loading…';
    try { const [requirements, ambiguities] = await Promise.all([request(`/v1/requirement-sets/${encodeURIComponent(setId)}/requirements`), request(`/v1/requirement-sets/${encodeURIComponent(setId)}/ambiguities`)]); state.requirements = requirements.items || []; state.ambiguities = ambiguities.items || []; renderRequirements(); renderAmbiguities(); $('connection-status').className = 'status-chip good'; $('connection-status').textContent = 'Connected'; log(`Loaded ${state.requirements.length} requirements and ${state.ambiguities.length} ambiguities.`); } catch (error) { showError(error, 'Load'); }
  }
  async function recordDecision(event) {
    event.preventDefault(); const id = $('ambiguity-id').value; if (!id) return;
    try { await request(`/v1/ambiguities/${encodeURIComponent(id)}/decisions`, { method:'POST', headers:{ 'Content-Type':'application/json', 'Idempotency-Key':key() }, body:JSON.stringify({ decision_text:$('decision-text').value.trim(), source_reference:$('source-reference').value.trim(), expected_version: state.ambiguities.find((a) => a.id === id)?.version || 1 }) }); log(`Decision recorded for ambiguity ${id}.`); $('decision-text').value = ''; await loadState(); } catch (error) { showError(error, 'Decision'); }
  }
  async function generate() {
    const setId = $('set-id').value.trim();
    try { const revision = await request(`/v1/requirement-sets/${encodeURIComponent(setId)}/spec-revisions`, { method:'POST', headers:{ 'Content-Type':'application/json', 'Idempotency-Key':key() }, body:JSON.stringify({ source_version:Number($('source-version').value), output_profile:$('output-profile').value.trim() }) }); state.revision = revision; $('revision-id').value = revision.id || ''; $('expected-version').value = 1; $('revision-status').className = 'status-chip warn'; $('revision-status').textContent = revision.status || 'WAITING_APPROVAL'; $('trace-btn').disabled = false; $('approve-btn').disabled = false; log(`Revision ${revision.id} queued; generation is deterministic and provider-free.`); await trace(); } catch (error) { showError(error, 'Generate'); }
  }
  async function trace() {
    const id = $('revision-id').value.trim(); if (!id) return;
    try { renderTrace(await request(`/v1/spec-revisions/${encodeURIComponent(id)}/traceability`)); log(`Traceability refreshed for revision ${id}.`); } catch (error) { showError(error, 'Traceability'); }
  }
  async function approve() {
    const id = $('revision-id').value.trim();
    try { const approved = await request(`/v1/spec-revisions/${encodeURIComponent(id)}/approve`, { method:'POST', headers:{ 'Content-Type':'application/json', 'Idempotency-Key':key() }, body:JSON.stringify({ spec_sha256:$('spec-sha').value.trim(), expected_version:Number($('expected-version').value) }) }); $('revision-status').className = 'status-chip good'; $('revision-status').textContent = approved.status || 'APPROVED'; log(`Revision ${id} approved at the submitted digest.`); } catch (error) { showError(error, 'Approval'); }
  }
  function escapeHtml(value) { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML; }
  function escapeAttr(value) { return escapeHtml(value).replace(/"/g, '&quot;'); }
  $('load-btn').addEventListener('click', loadState); $('decision-form').addEventListener('submit', recordDecision); $('generate-btn').addEventListener('click', generate); $('trace-btn').addEventListener('click', trace); $('approve-btn').addEventListener('click', approve); $('clear-events').addEventListener('click', () => { $('event-list').className = 'event-list empty'; $('event-list').textContent = 'Actions and typed API errors appear here.'; }); $('reset-btn').addEventListener('click', () => { localStorage.removeItem('specforge.apiBase'); $('api-base').value = location.origin; $('token').value = ''; $('set-id').value = ''; log('Local session reset.'); }); $('revision-id').addEventListener('change', () => { $('trace-btn').disabled = !$('revision-id').value.trim(); $('approve-btn').disabled = !$('revision-id').value.trim(); });
})();
