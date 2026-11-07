/* Native, dependency-free interface. Never interpolate model/user strings into innerHTML. */
'use strict';

const state = { role: null, csrf: null, provider: 'mock', batches: [], batchId: null, itemId: null, item: null, editing: false, busy: false };
const drafts = new Map();
const dirtyDrafts = new Set();
const languageNames = new Intl.DisplayNames(['de'], {type:'language', fallback:'none'});
let currentBatch = null;
let queueFilter = 'review_required';
let creatingDemo = false;
let pollTimer;
let messageTimer;
let sessionDeadline = 0;
let viewRequest = 0;
const $ = id => document.getElementById(id);
const LABELS = {
  pending: 'Noch nicht verarbeitet', queued: 'Eingeplant', processing: 'Wird verarbeitet', ready: 'Übernahmebereit', review_required: 'Prüfung offen',
  error: 'Fehler', confirmed: 'Final übernommen',
  answered: 'Antwort', no_answer: 'Keine Antwort', multiple: 'Mehrfachmarkierung',
  unreadable: 'Nicht lesbar', translated: 'Deutsch übersetzt', empty: 'Leer',
};

function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined && text !== null) el.textContent = String(text);
  if (className) el.className = className;
  return el;
}
function setMessage(text, error = false) {
  clearTimeout(messageTimer);
  $('global-message').textContent = text || '';
  if (text) messageTimer = setTimeout(() => setMessage(''), error ? 6500 : 2800);
  $('global-message').className = error ? 'is-error' : '';
}
function errMessage(e) { setMessage(e.message || String(e), true); }
function inlineError(id, message = '') {
  $(id).textContent = message;
  $(id).hidden = !message;
}
async function request(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.csrf && !['GET','HEAD'].includes((options.method || 'GET').toUpperCase())) headers.set('x-csrf-token', state.csrf);
  const reply = await fetch(url, { credentials: 'same-origin', ...options, headers });
  if (!reply.ok) {
    let detail = `HTTP ${reply.status}`;
    try {
      const data = await reply.json();
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data);
    } catch (_) { /* Keep HTTP status. */ }
    if (reply.status === 401 && state.role && url !== '/api/login') {
      showLogin();
      $('login-error').textContent = 'Sitzung beendet. Nicht exportierte Serverdaten können verloren sein.';
    }
    throw new Error(detail);
  }
  return reply;
}
async function json(url, options = {}) {
  if (options.body && !(options.body instanceof FormData)) {
    options.headers = { ...(options.headers || {}), 'Content-Type': 'application/json' };
    options.body = JSON.stringify(options.body);
  }
  return (await request(url, options)).json();
}
function showLogin() {
  viewRequest++;
  drafts.clear();
  dirtyDrafts.clear();
  trackDraftExit();
  clearTimeout(pollTimer);
  currentBatch = null;
  sessionDeadline = 0;
  Object.assign(state, {role:null, csrf:null, batches:[], batchId:null, itemId:null, item:null, editing:false});
  $('source-image').removeAttribute('src');
  $('user-menu').open = false;
  setRename(false);
  setPanel('upload', false);
  setPanel('admin', false);
  $('batch-view').hidden = $('detail-panel').hidden = true;
  $('selected-batch-name').value = $('batch-name').value = '';
  $('files-input').value = $('folder-input').value = '';
  setMessage('');
  for (const id of ['review-findings', 'raw-fields', 'raw-json', 'final-fields', 'photo-list', 'batch-list']) $(id).replaceChildren();
  $('app-screen').hidden = true; $('login-screen').hidden = false;
}
function showApp() {
  $('login-screen').hidden = true; $('app-screen').hidden = false;
  $('role-indicator').textContent = state.role === 'admin' ? 'Administrator' : 'Testnutzer';
  $('provider-indicator').textContent = state.provider === 'mock' ? 'Demo · ohne KI' : 'Live · OpenRouter';
  $('toggle-admin').hidden = state.role !== 'admin';
  if (state.role !== 'admin') setPanel('admin', false);
}
function setPanel(panel, open) {
  $(panel + '-panel').hidden = !open;
  $('toggle-' + panel).setAttribute('aria-expanded', String(open));
}
for (const panel of ['upload', 'admin']) {
  $('toggle-' + panel).addEventListener('click', () => {
    const open = $(panel + '-panel').hidden;
    setPanel(panel === 'upload' ? 'admin' : 'upload', false);
    setPanel(panel, open);
    if (panel === 'admin') $('user-menu').open = false;
    if (open) $(panel === 'admin' ? 'provider-select' : 'folder-input').focus();
  });
}
function updateClock() {
  const minutes = Math.max(0, Math.ceil((sessionDeadline - Date.now()) / 60000));
  $('session-clock').textContent = minutes ? `Sitzung · ${minutes} min` : 'Sitzung abgelaufen';
  $('session-warning').hidden = !sessionDeadline || minutes > 10;
  $('session-warning').textContent = minutes
    ? 'Die Sitzung endet bald. Bitte bestätigte Bögen jetzt exportieren.'
    : 'Die Sitzung ist abgelaufen. Nicht exportierte Daten können verloren sein.';
}
setInterval(updateClock, 15000);

async function restore() {
  try {
    const session = await json('/api/me');
    $('login-error').textContent = '';
    state.role = session.role; state.csrf = session.csrf; state.provider = session.provider;
    sessionDeadline = Date.now() + session.remaining_seconds * 1000;
    updateClock();
    showApp(); await reloadBatches();
    if (state.role === 'admin') await readConfig();
  } catch (_) { showLogin(); }
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('login-error').textContent = '';
  try {
    const login = await json('/api/login', {method:'POST', body:{ username: $('username').value, password: $('password').value }});
    state.role = login.role; state.csrf = login.csrf;
    $('password').value = '';
    const me = await json('/api/me');
    state.provider = me.provider;
    sessionDeadline = Date.now() + me.remaining_seconds * 1000;
    updateClock();
    showApp(); await reloadBatches();
    if (state.role === 'admin') await readConfig();
  } catch (e) { $('login-error').textContent = e.message; }
});
$('logout-button').addEventListener('click', async () => {
  if (dirtyDrafts.size && !window.confirm('Abmelden und ungespeicherte Änderungen verwerfen?')) return;
  try {
    await json('/api/logout', { method:'POST' });
    showLogin();
  } catch (e) { errMessage(e); }
});

async function readConfig() {
  const config = await json('/api/admin/config');
  $('provider-select').value = config.provider;
  $('model-input').value = config.model || '';
  $('model-key-status').textContent = config.openrouter_key_configured ? 'API-Schlüssel vorhanden' : 'Kein API-Schlüssel hinterlegt';
}
$('save-model-button').addEventListener('click', async () => {
  try {
    const result = await json('/api/admin/config', { method:'POST', body:{ provider:$('provider-select').value, model:$('model-input').value } });
    state.provider = result.provider; showApp(); setMessage('Modelladapter gespeichert (bis zum nächsten Neustart).');
  } catch (e) { errMessage(e); }
});

async function reloadBatches(preferredId = state.batchId) {
  state.batches = await json('/api/batches');
  renderBatchList();
  if (preferredId && state.batches.some(b => b.id === preferredId)) {
    await openBatch(preferredId);
  } else if (state.batches.length) {
    await openBatch(state.batches[state.batches.length - 1].id);
  } else {
    state.batchId = null;
    currentBatch = null;
    closeDetail();
    $('batch-view').hidden = true; $('empty-state').hidden = false;
  }
}
function renderBatchList() {
  const list = $('batch-list'); list.replaceChildren();
  if (!state.batches.length) list.append(element('p', 'Noch keine Vorgänge.', 'small'));
  for (const batch of state.batches) {
    const b = element('button', `${batch.name} · ${batch.count} Bilder · ${batch.confirmed} final`,
      'batch-entry' + (batch.id === state.batchId ? ' selected' : ''));
    b.addEventListener('click', () => openBatch(batch.id).catch(errMessage));
    const row = element('div', null, 'batch-row');
    const remove = element('button', '×', 'remove-batch');
    remove.setAttribute('aria-label', `Vorgang ${batch.name} löschen`);
    remove.title = 'Vorgang löschen';
    remove.addEventListener('click', () => deleteBatch(batch).catch(errMessage));
    row.append(b, remove);
    list.append(row);
  }
}
async function deleteBatch(batch) {
  if (!window.confirm(`Vorgang „${batch.name}“ mit seinen Bögen löschen?`)) return;
  await request(`/api/batches/${batch.id}`, {method:'DELETE'});
  for (const item of batch.items) {
    drafts.delete(item.id);
    dirtyDrafts.delete(item.id);
  }
  trackDraftExit();
  await reloadBatches();
  setMessage('Vorgang gelöscht.');
}
function closeDetail() {
  viewRequest++;
  Object.assign(state, {itemId:null, item:null, editing:false});
  $('detail-panel').hidden = true;
  $('workflow-overview').hidden = false;
}
$('back-overview').addEventListener('click', () => {
  closeDetail();
  renderPhotos(currentBatch);
  $('batch-overview').focus();
  $('batch-overview').scrollIntoView({block:'nearest'});
});
async function openBatch(batchId, preferredItem = null) {
  clearTimeout(pollTimer);
  const view = ++viewRequest;
  const batch = await json('/api/batches/' + encodeURIComponent(batchId));
  if (view !== viewRequest) return;
  closeDetail();
  $('correction-details').open = false;
  $('correction-list').replaceChildren();
  setRename(false);
  if (state.batchId !== batch.id || !preferredItem) queueFilter = defaultFilter(batch);
  state.batchId = batch.id;
  $('empty-state').hidden = true; $('batch-view').hidden = false;
  $('selected-batch-name').value = $('batch-title').textContent = batch.name;
  if (batch.synthetic && batch.name === 'Synthetische Demo – keine KI-Verarbeitung') $('batch-title').textContent = 'Fragebogen-Demo';
  $('batch-kicker').textContent = batch.synthetic ? 'DEMONSTRATION · SYNTHETISCHE BÖGEN' : 'DIGITALISIERUNG · VORGANG';
  renderBatchStatus(batch);
  renderBatchList();
  const target = batch.items.find(x => x.id === preferredItem);
  if (target) await openItem(target.id);
}

function needsReview(item) {
  return item.status === 'review_required' || (item.review_started && !item.sample_selected);
}
function defaultFilter(batch) {
  if (batch.items.some(needsReview)) return 'review_required';
  if (batch.items.some(x => x.status === 'error')) return 'error';
  if (batch.items.some(x => ['pending','queued','processing'].includes(x.status))) return 'all';
  return 'review_required';
}
function matchesFilter(item, filter) {
  if (filter === 'all') return true;
  if (filter === 'sample') return item.sample_selected;
  if (filter === 'review_required') return needsReview(item);
  return item.status === filter && (filter !== 'ready' || !item.review_started);
}
function nextReview(items, after) {
  const matches = queueFilter === 'sample' ? item => item.sample_selected : needsReview;
  const index = items.findIndex(x => x.id === after);
  if (index < 0) return items.find(matches);
  return [...items.slice(index + 1), ...items.slice(0, index)].find(matches);
}
function renderBatchStatus(batch) {
  currentBatch = batch;
  const previous = state.batches.find(x => x.id === batch.id);
  if (previous && (previous.confirmed !== batch.confirmed || previous.name !== batch.name)) {
    Object.assign(previous, {confirmed:batch.confirmed, name:batch.name});
    renderBatchList();
  }
  const confirmed = batch.items.filter(item => item.status === 'confirmed').length;
  const counts = [
    ['Technisch bearbeitet', batch.items.filter(x => ['ready','review_required','confirmed','error'].includes(x.status)).length, 'total'],
    ['Übernahmebereit', batch.items.filter(x => x.status === 'ready' && !x.review_started).length, 'ready'],
    ['Prüfung offen', batch.items.filter(needsReview).length, 'review_required'],
    ['Bestätigt', confirmed, 'confirmed'],
    ['Fehler', batch.items.filter(x => x.status === 'error').length, 'error'],
  ];
  $('batch-summary').replaceChildren(...counts.map(([label, count, tone]) => {
    const metric = element('div', null, 'metric metric-' + tone);
    metric.append(element('strong', tone === 'total' ? `${count}/${batch.count}` : count), element('span', label));
    return metric;
  }));
  const active = Boolean(batch.run?.active);
  const ready = counts[1][1];
  const pending = batch.items.some(x => x.status === 'pending' && x.can_recognize);
  $('recognize-all-button').hidden = !pending && !active;
  $('recognize-all-button').disabled = active || state.busy;
  $('retry-button').hidden = !batch.items.some(x => x.status === 'error' && x.can_recognize);
  $('retry-button').disabled = active || state.busy;
  const open = counts[2][1];
  $('bulk-step').hidden = ready === 0;
  $('bulk-step').classList.toggle('recommended', !active && !pending && !open && !counts[4][1]);
  $('bulk-count').textContent = ready === 1 ? '1 Bogen ist übernahmebereit.' : `${ready} Bögen sind übernahmebereit.`;
  $('confirm-ready-button').disabled = active || ready === 0;
  $('confirm-ready-button').classList.toggle('secondary', active || pending || open > 0 || counts[4][1] > 0);
  $('confirm-ready-button').textContent = ready === 1 ? '1 Bogen gesammelt bestätigen' : `${ready} Bögen gesammelt bestätigen`;
  const complete = confirmed === batch.count;
  renderReviewSummary(batch, complete);
  $('export-step').hidden = confirmed === 0;
  $('export-step').classList.toggle('recommended', complete);
  $('export-title').textContent = `${confirmed} von ${batch.count} Bögen abgeschlossen`;
  $('export-note').textContent = complete ? 'Alle bestätigten Bögen stehen zum Download bereit.'
    : `${batch.count - confirmed} noch nicht bestätigte Bögen fehlen in einem Teil-Export.`;
  $('export-button').classList.toggle('secondary', !complete);
  $('export-button').textContent = complete ? 'CSV herunterladen' : 'Teil-CSV herunterladen';
  updateNextReview(batch);
  const candidates = batch.items.filter(x => x.status === 'ready' && !x.review_started && !x.sample_reviewed);
  const samplePending = batch.items.filter(x => x.sample_selected).length;
  const sampleSize = samplePending || Math.min(5, candidates.length);
  $('quality-control').hidden = sampleSize === 0;
  $('sample-button').textContent = `${sampleSize} ${sampleSize === 1 ? 'übernahmebereiten Bogen' : 'übernahmebereite Bögen'} kontrollieren`;
  const sampleCount = batch.items.filter(x => x.sample_reviewed).length;
  const sampleOpen = batch.items.filter(x => x.sample_selected).length;
  const sampleErrors = batch.items.filter(x => x.sample_corrected).length;
  $('sample-status').hidden = !sampleCount && !sampleOpen;
  $('sample-status').textContent = `Stichprobe: ${sampleCount} geprüft, ${sampleOpen} offen.` +
    (sampleErrors ? ` ${sampleErrors} korrigiert. Übrige grüne Bögen erneut prüfen (Filter „Übernahmebereit“).` : '');
  $('sample-status').classList.toggle('error', sampleErrors > 0);
  const individual = batch.items.filter(x => ['individual','sample'].includes(x.confirmation_source)).length;
  $('batch-overview').textContent = active ? 'Die Übersicht aktualisiert sich während der Verarbeitung.'
    : open ? `${open} ${open === 1 ? 'Bogen braucht' : 'Bögen brauchen'} eine manuelle Prüfung. Wähle einen Bogen aus der Warteschlange.`
    : pending ? 'Die Bögen sind bereit zur technischen Verarbeitung.'
    : counts[4][1] ? `${counts[4][1]} technische Fehler. Details stehen in der Warteschlange.`
    : `${individual} einzeln geprüft · ${ready} zur Sammelbestätigung bereit.`;
  $('batch-progress').hidden = !active;
  if (batch.run) {
    $('run-progress').max = batch.run.total;
    $('run-progress').value = batch.run.done;
    $('run-label').textContent = `${batch.run.done} von ${batch.run.total} verarbeitet`;
    $('run-breakdown').textContent = 'Technischer Lauf';
  }
  $('batch-budget').hidden = !batch.budget || state.provider === 'mock';
  if (batch.budget) {
    const b = batch.budget;
    $('batch-budget').textContent = `Aufrufbudget: ${b.remaining} verfügbar · ${b.sent} gesendet · ${b.succeeded} erfolgreich · ${b.failed} fehlgeschlagen · ${b.repeated} wiederholt`;
  }
  clearTimeout(pollTimer);
  if (active) pollTimer = setTimeout(() => refreshRun(batch.id), 800);
  $('export-button').disabled = confirmed === 0;
  renderPhotos(batch);
}

function renderReviewSummary(batch, complete) {
  $('review-summary').hidden = !complete;
  if (!complete) return;
  const reviewed = batch.items.filter(item => ['individual','sample'].includes(item.confirmation_source));
  const corrected = reviewed.filter(item => item.review_mode === 'corrected').length;
  const counts = [
    ['Gesammelt übernommen', batch.items.filter(item => item.confirmation_source === 'bulk').length],
    ['Individuell geprüft', reviewed.length],
    ['Manuell geprüft, unverändert', reviewed.length - corrected],
    ['Manuell korrigiert', corrected],
  ];
  $('review-counts').replaceChildren(...counts.map(([label, count]) => {
    const metric = element('div');
    metric.append(element('dt', label), element('dd', count));
    return metric;
  }));
}
function correctionValue(value) {
  if ('status' in value) return value.value ?? LABELS[value.status] ?? value.status;
  const text = value.german_translation || 'Kein Freitext vorhanden';
  return `${text} · ${LABELS[value.text_status] || value.text_status}`;
}
$('correction-details').addEventListener('toggle', async () => {
  if (!$('correction-details').open) return;
  const batchId = state.batchId;
  const list = $('correction-list');
  list.textContent = 'Korrekturen werden geladen …';
  try {
    const {changes} = await json(`/api/batches/${batchId}/corrections`);
    if (state.batchId !== batchId || !$('correction-details').open) return;
    list.replaceChildren();
    if (!changes.length) {
      list.textContent = 'Keine bestätigten Feldänderungen.';
      return;
    }
    for (const change of changes) {
      const row = element('article', null, 'correction-row');
      row.append(element('h4', `Bild ${change.sequence} · ${fieldLabel(change.field)}`));
      const values = element('dl');
      values.append(element('dt', 'Ursprüngliche KI-Erkennung'), element('dd', correctionValue(change.before)),
        element('dt', 'Final bestätigt'), element('dd', correctionValue(change.after)));
      row.append(values);
      if (change.reason) row.append(element('p', `Begründung der Sichtprüfung: ${change.reason}`, 'small'));
      list.append(row);
    }
  } catch (e) {
    if (state.batchId === batchId && $('correction-details').open) list.textContent = e.message;
  }
});
async function refreshRun(batchId) {
  if (state.batchId !== batchId) return;
  try {
    const previous = currentBatch.items.find(x => x.id === state.itemId)?.status;
    const batch = await json(`/api/batches/${batchId}/process`);
    if (state.batchId !== batchId) return;
    if (currentBatch.run?.active && !batch.run?.active) queueFilter = defaultFilter(batch);
    renderBatchStatus(batch);
    const status = batch.items.find(x => x.id === state.itemId)?.status;
    if (status !== previous && !state.editing) await openItem(state.itemId);
  } catch (e) {
    errMessage(e);
    if (state.batchId === batchId) pollTimer = setTimeout(() => refreshRun(batchId), 1600);
  }
}
function updateNextReview(batch) {
  $('next-review-button').hidden = !batch.items.some(queueFilter === 'sample'
    ? item => item.sample_selected : needsReview);
  $('next-review-button').classList.toggle('secondary', queueFilter === 'sample');
}
function renderPhotos(batch) {
  const names = {review_required:'Zu prüfen', ready:'Übernahmebereit', confirmed:'Bestätigt',
    all:'Alle', error:'Fehler', sample:'Gegenkontrolle'};
  for (const button of $('queue-filters').querySelectorAll('button')) {
    const key = button.dataset.filter;
    const count = batch.items.filter(item => matchesFilter(item, key)).length;
    button.textContent = `${names[key]} (${count})`;
    button.setAttribute('aria-pressed', String(queueFilter === key));
    button.hidden = (key === 'error' || key === 'sample') && count === 0;
  }
  const items = batch.items.filter(item => matchesFilter(item, queueFilter));
  const list = $('photo-list');
  const scroll = list.scrollTop;
  const previews = new Map([...list.querySelectorAll('button')].map(card => [card.dataset.itemId, card.querySelector('img')]));
  const focused = list.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
  list.replaceChildren();
  list.hidden = !items.length && queueFilter === 'review_required';
  if (!items.length && !list.hidden) list.append(element('p', 'Keine Bögen in dieser Ansicht.', 'small'));
  for (const item of items) {
    const card = element('button', null, 'photo-entry' + (item.id === state.itemId ? ' selected' : ''));
    card.dataset.itemId = item.id;
    card.setAttribute('aria-pressed', String(item.id === state.itemId));
    if (item.has_thumbnail) {
      const image = previews.get(item.id) || element('img', null, 'thumbnail');
      if (!image.hasAttribute('src')) image.src = `/api/batches/${batch.id}/items/${item.id}/thumbnail`;
      image.alt = '';
      image.loading = 'lazy';
      card.append(image);
    }
    const info = element('span', null, 'photo-info');
    info.append(element('strong', `Bild ${String(item.sequence).padStart(2, '0')}`));
    info.append(element('span', LABELS[item.status] || item.status, `status ${item.status}`));
    card.title = item.filename;
    card.append(info);
    if (item.status === 'review_required' && item.findings?.length) {
      const first = item.findings[0];
      const more = item.findings.length - 1;
      info.append(element('span', findingTitle(first) + (first.kind === 'demo' || first.kind === 'mock' ? '' : ` · ${first.reason}`) + (more ? ` + ${more}` : ''), 'photo-reason'));
    }
    if (item.error) info.append(element('span', item.error, 'small'));
    if (item.sample_selected) info.append(element('span', 'Freiwillige Gegenkontrolle', 'small'));
    if (item.confirmation_source) info.append(element('span', confirmationLabel(item), 'small'));
    card.addEventListener('click', () => openForReview(item.id));
    list.append(card);
  }
  if (focused) [...list.querySelectorAll('button')].find(card => card.dataset.itemId === focused)?.focus({preventScroll:true});
  list.scrollTop = scroll;
}
function confirmationLabel(item) {
  if (item.confirmation_source === 'bulk') return 'Gesammelt · ohne Einzelprüfung';
  const origin = item.confirmation_source === 'sample' ? 'Stichprobe' : 'Einzelprüfung';
  return origin + (item.review_mode === 'corrected' ? ' · korrigiert' : ' · unverändert');
}
$('queue-filters').addEventListener('click', event => {
  const button = event.target.closest('button[data-filter]');
  if (currentBatch && button) {
    queueFilter = button.dataset.filter;
    renderPhotos(currentBatch);
    updateNextReview(currentBatch);
  }
});
$('next-review-button').addEventListener('click', () => {
  const target = nextReview(currentBatch.items, state.itemId) || nextReview(currentBatch.items, null);
  if (target) openForReview(target.id);
});
$('sample-button').addEventListener('click', async () => {
  const batchId = state.batchId;
  try {
    const batch = await json(`/api/batches/${batchId}/sample`, {method:'POST'});
    if (state.batchId !== batchId) return;
    queueFilter = 'sample';
    await openBatch(batchId, batch.items.find(x => x.sample_selected)?.id);
  } catch (e) { errMessage(e); }
});
async function openForReview(itemId) {
  setMessage('');
  try {
    await openItem(itemId);
    if (state.itemId === itemId) focusReviewStart();
  } catch (e) { errMessage(e); }
}
async function openItem(itemId) {
  if (!state.batchId) return;
  const view = ++viewRequest;
  const item = await json(`/api/batches/${state.batchId}/items/${itemId}`);
  if (view !== viewRequest) return;
  state.itemId = itemId;
  state.item = item;
  state.editing = state.item.status === 'review_required' || Boolean(state.item.review_started);
  inlineError('review-error');
  clearFieldError();
  renderDetail();
  for (const b of $('photo-list').querySelectorAll('button')) {
    const selected = b.dataset.itemId === itemId;
    b.classList.toggle('selected', selected);
    b.setAttribute('aria-pressed', String(selected));
  }
}
function fieldLabel(field) {
  if (field === 'text') return 'Freitext';
  if (field === 'image') return 'Bild';
  return 'Frage ' + field.slice(1);
}
function findingTitle(finding) {
  if (finding.kind === 'demo') return 'Freitext · Demo-Prüffall';
  if (finding.kind === 'mock') return 'Manuelle Erfassung';
  return fieldLabel(finding.field) + ' prüfen';
}
function focusButton(field, label) {
  const button = element('button', label, 'field-focus');
  button.type = 'button';
  button.dataset.focusField = field;
  button.addEventListener('click', () => focusField(field));
  return button;
}
function focusField(field, scrollToImage = true) {
  const item = state.item;
  const demo = item.source === 'synthetic_demo';
  let region = item.raw?.regions?.[field];
  if (demo && field !== 'image') {
    if (field === 'text') region = [.07, .74, .93, .95];
    else {
      const y = (210 + (Number(field.slice(1)) - 1) * 125) / 1230;
      region = [.07, y, .86, y + .083];
    }
  }
  const valid = Array.isArray(region) && region.length === 4 &&
    region.every(x => Number.isFinite(x) && x >= 0 && x <= 1) &&
    region[0] < region[2] && region[1] < region[3];
  $('source-frame').hidden = !item.image_url;
  $('source-highlight').toggleAttribute('hidden', !valid || !item.image_url);
  $('focus-note').textContent = fieldLabel(field) + (valid
    ? demo ? ' · markierte Stelle im Demobogen' : ' · geschätzter Bildbereich des Modells'
    : ' · keine genaue Bildstelle verfügbar');
  if (valid) {
    const [left, top, right, bottom] = region;
    const box = $('source-region');
    for (const [attr, value] of Object.entries({x:left, y:top, width:right-left, height:bottom-top})) {
      box.setAttribute(attr, String(value * 1000));
    }
  }
  $('detail-panel').querySelectorAll('[data-focus-field]').forEach(node => {
    node.classList.toggle('focused-field', node.dataset.focusField === field);
    if (node.tagName === 'BUTTON') node.setAttribute('aria-pressed', String(node.dataset.focusField === field));
  });
  if (scrollToImage && matchMedia('(max-width: 760px)').matches && item.image_url) {
    $('source-frame').scrollIntoView({block:'nearest'});
  }
}
function renderFindings(item) {
  const list = $('review-findings');
  list.replaceChildren();
  const findings = item.findings || [];
  list.hidden = !findings.length;
  if (findings.length) list.append(element('h4', item.source === 'synthetic_demo' ? 'Prüfhinweise zur Demo' : 'Warum prüfen?'));
  if (findings.some(f => f.kind === 'demo')) list.append(element('p', 'Bewertungsfragen 1–5: keine Auffälligkeiten.', 'small'));
  for (const finding of findings) {
    const row = element('div', null, 'finding');
    row.append(focusButton(finding.field, findingTitle(finding)));
    row.append(element('p', finding.reason, 'small'));
    list.append(row);
  }
}
function focusReviewStart() {
  $('detail-header-title').focus();
  if (!state.editing || matchMedia('(max-width: 760px)').matches) return;
  const first = state.item.findings?.find(finding => finding.field !== 'image');
  if (first) $(first.field === 'text' ? 'final-text' : 'final-' + first.field)?.focus({preventScroll:true});
}
function displayLanguage(code) {
  try {
    return code && code !== 'unknown' ? languageNames.of(code) || 'Sprache nicht bestimmt' : 'Sprache nicht bestimmt';
  } catch (_) { return 'Sprache nicht bestimmt'; }
}
function renderRaw(item) {
  const block = $('raw-fields'); block.replaceChildren();
  if (!item.raw) {
    block.append(element('p', item.error || 'Noch keine Erkennung durchgeführt.', 'small')); return;
  }
  block.append(element('h4', 'Aus dem Original erfasst', 'recognition-section-title'));
  for (let i = 1; i <= 5; i++) {
    const field = item.raw[`q${i}`];
    const node = element('div', null, 'field' + (['unreadable','multiple'].includes(field.status) ? ' warning' : ''));
    node.append(focusButton(`q${i}`, `Frage ${i}`));
    node.classList.add('answer-row');
    node.append(element('div', field.status === 'answered' ? field.value : LABELS[field.status] || field.status, 'answer-value'));
    block.append(node);
  }
  const original = element('section', null, 'field recognition-text');
  original.append(element('h4', 'Handschriftlicher Originaltext', 'recognition-section-title'),
    focusButton('text', displayLanguage(item.raw.text.source_language)));
  original.append(element('div', item.raw.text.original_transcript || (item.raw.text.text_status === 'empty' ? 'Kein Freitext vorhanden' : 'Freitext nicht sicher lesbar'), 'field-text'));
  block.append(original);
  const german = element('section', null, 'field recognition-text' + (['review_required','unreadable'].includes(item.raw.text.text_status) ? ' warning' : ''));
  german.append(element('h4', 'Übersetzung ins Deutsche', 'recognition-section-title'));
  if (item.raw.text.source_language === 'de') german.append(element('p', 'Original bereits Deutsch', 'small'));
  german.append(element('div', item.raw.text.german_translation || (item.raw.text.text_status === 'empty' ? 'Kein Freitext vorhanden' : 'Keine Übersetzung verfügbar'), 'field-text'));
  german.append(element('p', LABELS[item.raw.text.text_status] || item.raw.text.text_status, 'small'));
  block.append(german);
}
const answerOptions = [
  {value:'answered:1', label:'1'}, {value:'answered:2', label:'2'},
  {value:'answered:3', label:'3'}, {value:'answered:4', label:'4'},
  {value:'no_answer', label:'Keine Antwort'}, {value:'multiple',label:'Mehrfachmarkierung'},
  {value:'unreadable',label:'Nicht lesbar'},
];
function answerToChoice(answer) { return answer.status === 'answered' ? `answered:${answer.value}` : answer.status; }
function renderFinal(item) {
  const parent = $('final-fields'); parent.replaceChildren();
  const confirmed = item.status === 'confirmed';
  $('result-state').hidden = true;
  const canShow = Boolean(item.final || item.draft || item.raw);
  const edit = state.editing && !confirmed;
  $('edit-button').disabled = confirmed || !item.raw || edit;
  $('edit-button').hidden = confirmed || !item.raw || edit;
  $('edit-button').classList.toggle('secondary', item.status === 'ready');
  $('confirm-button').textContent = edit ? 'Korrektur speichern & bestätigen' : 'Bogen bestätigen';
  $('confirm-button').classList.toggle('secondary', item.status === 'review_required' && !edit);
  $('confirm-button').hidden = confirmed || !canShow || (item.status === 'review_required' && !edit);
  $('reopen-button').hidden = !confirmed;
  $('confirm-button').disabled = !canShow || (item.status === 'review_required' && !edit);
  $('evidence-wrap').hidden = true;
  $('evidence-confirmed').checked = false;
  if (!canShow) {
    parent.append(element('p', item.status === 'review_required'
      ? 'Die Prüfhinweise stehen oberhalb der Felder.'
      : 'Die finale Fassung erscheint nach der Bilderkennung.', 'small'));
    return;
  }
  $('result-state').hidden = confirmed || edit;
  const localDraft = edit ? drafts.get(item.id) : null;
  const data = item.final || localDraft || item.draft || item.raw;
  $('evidence-confirmed').checked = Boolean(localDraft?.evidence_confirmed);
  for (let i = 1; i <= 5; i++) {
    const container = element('div', null, 'field final-answer');
    const original = item.raw?.[`q${i}`];
    if (item.findings?.some(finding => finding.field === `q${i}`)) container.classList.add('warning');
    const answer = data[`q${i}`];
    markChanged(container, Boolean(original && (original.value !== answer.value || original.status !== answer.status)));
    container.dataset.focusField = `q${i}`;
    const label = element('label', `Frage ${i}`);
    const select = element('select'); select.id = `final-q${i}`;
    for (const entry of answerOptions) {
      const opt = element('option', entry.label); opt.value = entry.value;
      select.append(opt);
    }
    select.value = answerToChoice(data[`q${i}`]); select.disabled = !edit;
    if (edit) {
      label.append(select);
      container.append(label);
      if (original?.status === 'multiple') {
        container.append(element('p', 'Sind im Original mehrere gültige Kreuze sichtbar, behalte die Mehrfachmarkierung bei.', 'small'));
        const reasonLabel = element('label', 'Begründung für den Einzelwert (freiwillig)');
        const reason = element('textarea');
        reason.id = `multiple-reason-q${i}`;
        reason.maxLength = 400;
        reason.placeholder = 'Bei Bedarf kannst du den Sichtbeleg hier kurz erläutern.';
        reason.value = localDraft?.multiple_reasons?.[`q${i}`] || '';
        reasonLabel.hidden = answer.status !== 'answered';
        reasonLabel.append(reason);
        container.append(reasonLabel);
      }
    } else {
      container.classList.add('answer-row');
      container.append(element('span', `Frage ${i}`), element('span', answer.value ?? LABELS[answer.status], 'answer-value'));
      select.hidden = true;
      container.append(select);
    }
    parent.append(container);
  }
  const field = element('div', null, 'field');
  field.dataset.focusField = 'text';
  if (item.findings?.some(finding => finding.field === 'text')) field.classList.add('warning');
  markChanged(field, Boolean(item.raw && data.text.german_translation !== item.raw.text.german_translation));
  const label = element('label', edit ? 'Deutscher Freitext bearbeiten' : 'Deutscher Freitext');
  const textarea = element('textarea'); textarea.id = 'final-text'; textarea.value = data.text.german_translation || '';
  textarea.disabled = !edit; textarea.maxLength = 5000; label.append(textarea); field.append(label);
  const textLabel = element('label', 'Textstatus');
  const textSelect = element('select'); textSelect.id = 'final-text-status';
  for (const [code, title] of [['review_required','Bitte Textstatus prüfen'],['translated','Übersetzt / Deutsch vorhanden'],['empty','Keine Angabe'],['unreadable','Unlesbar']]) {
    const opt = element('option', title); opt.value = code; textSelect.append(opt);
  }
  textSelect.value = data.text.text_status;
  textSelect.querySelector('option[value=review_required]').disabled = true;
  textSelect.disabled = !edit;
  textLabel.append(textSelect); field.append(textLabel);
  if (!edit) {
    label.hidden = textLabel.hidden = true;
    field.append(element('strong', 'Deutscher Freitext'),
      element('div', data.text.german_translation || (data.text.text_status === 'empty' ? 'Kein Freitext vorhanden' : '–'), 'field-text'),
      element('p', LABELS[data.text.text_status], 'small'));
  }
  parent.append(field);
  if (confirmed) parent.append(element('p', confirmationLabel(item), 'status confirmed'));
}
function renderDetail() {
  const item = state.item;
  if (!item) return;
  $('detail-panel').hidden = false;
  $('workflow-overview').hidden = true;
  $('item-indicator').textContent = `Bild ${item.sequence} · ${LABELS[item.status] || item.status}`;
  $('item-indicator').className = `status ${item.status}`;
  if (item.image_url) $('source-image').src = item.image_url;
  else $('source-image').removeAttribute('src');
  setZoom(false);
  $('source-highlight').setAttribute('hidden', '');
  $('focus-note').textContent = '';
  $('source-frame').hidden = $('toggle-image-button').hidden = $('zoom-image-button').hidden = !item.image_url;
  $('source-note').textContent = item.source === 'synthetic_demo'
    ? 'Vorgegebene Demodaten für den Prüfablauf.'
    : item.source === 'mock_upload' ? 'Demo-Adapter ohne automatische Erkennung.'
    : 'Ausgabe des multimodalen Modells. Aussagen müssen am Originalfoto geprüft werden.';
  $('raw-summary').textContent = item.source === 'synthetic_demo' ? 'Vorgegebene Demodaten (JSON)' : 'Unveränderte Modellantwort (JSON)';
  $('raw-json').textContent = item.raw_text || '(noch keine KI-Ausgabe)';
  $('recognize-one-button').disabled = state.busy || !item.can_recognize;
  $('recognize-one-button').hidden = !item.can_recognize;
  renderFindings(item); renderRaw(item); renderFinal(item);
  if (state.editing && $('final-q1')) {
    rememberDraft();
    const first = item.findings?.find(finding => finding.field !== 'image');
    if (first) focusField(first.field, false);
  }
}
function setZoom(open) {
  $('source-frame').classList.toggle('expanded', open);
  $('zoom-image-button').setAttribute('aria-expanded', String(open));
}
function toggleZoom() {
  $('source-frame').hidden = false;
  setZoom(!$('source-frame').classList.contains('expanded'));
}
$('toggle-image-button').addEventListener('click', () => {
  setZoom(false);
  $('source-frame').hidden = !$('source-frame').hidden;
});
$('zoom-image-button').addEventListener('click', toggleZoom);
$('source-image').addEventListener('click', toggleZoom);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') setZoom(false);
});
$('edit-button').addEventListener('click', async () => {
  if (!state.item?.raw || state.item.status === 'confirmed') return;
  const {batchId, itemId} = state;
  try {
    await json(`/api/batches/${batchId}/items/${itemId}/review`, {method:'POST'});
    if (state.itemId !== itemId) return;
    await openBatch(batchId, itemId);
  } catch (e) { errMessage(e); }
});
$('reopen-button').addEventListener('click', async () => {
  try {
    const {batchId, itemId} = state;
    await json(`/api/batches/${batchId}/items/${itemId}/reopen`, {method:'POST'});
    if (state.batchId === batchId) await openBatch(batchId, itemId); setMessage('Datensatz erneut geöffnet. Vor dem Export erneut final bestätigen.');
  } catch (e) { errMessage(e); }
});
function confirmationPayload() {
  const final = { evidence_confirmed: $('evidence-confirmed').checked, multiple_reasons: {} };
  for (let i = 1; i <= 5; i++) {
    const choice = $(`final-q${i}`).value;
    final[`q${i}`] = choice.startsWith('answered:')
      ? {status:'answered',value:Number(choice.split(':')[1])}
      : {status:choice,value:null};
    const reason = $(`multiple-reason-q${i}`);
    if (reason && final[`q${i}`].status === 'answered') final.multiple_reasons[`q${i}`] = reason.value;
  }
  final.text = { german_translation:$('final-text').value, text_status:$('final-text-status').value };
  return final;
}
function warnDraftExit(event) {
  event.preventDefault();
  event.returnValue = '';
}
function trackDraftExit() {
  if (dirtyDrafts.size) window.addEventListener('beforeunload', warnDraftExit);
  else window.removeEventListener('beforeunload', warnDraftExit);
}
function markChanged(field, changed) {
  field.classList.toggle('changed', changed);
  let marker = field.querySelector('.change-label');
  if (!marker) {
    marker = element('span', 'Korrigiert', 'small change-label');
    field.append(marker);
  }
  marker.hidden = !changed;
}
function rememberDraft() {
  if (!state.editing || !$('final-q1')) return;
  const payload = confirmationPayload();
  drafts.set(state.itemId, payload);
  const baseline = state.item.draft || state.item.raw;
  const modified = ['q1','q2','q3','q4','q5'].some(key =>
    payload[key].value !== baseline[key].value || payload[key].status !== baseline[key].status) ||
    payload.text.german_translation !== baseline.text.german_translation || payload.text.text_status !== baseline.text.text_status;
  if (modified) dirtyDrafts.add(state.itemId);
  else dirtyDrafts.delete(state.itemId);
  trackDraftExit();
  inlineError('review-error');
  let hasChanges = false;
  for (const field of $('final-fields').querySelectorAll('[data-focus-field]')) {
    const key = field.dataset.focusField;
    const original = state.item.raw[key];
    const edited = payload[key];
    const changed = key === 'text' ? original.german_translation !== edited.german_translation || original.text_status !== edited.text_status
      : original.value !== edited.value || original.status !== edited.status;
    const reason = $(`multiple-reason-${key}`);
    if (reason) reason.closest('label').hidden = edited.status !== 'answered';
    markChanged(field, changed);
    hasChanges ||= key === 'text' ? original.german_translation !== edited.german_translation : changed;
  }
  $('evidence-wrap').hidden = !hasChanges;
  if (!hasChanges) $('evidence-confirmed').checked = false;
}
$('final-fields').addEventListener('input', event => {
  const question = event.target.id.match(/^final-(q[1-5])$/);
  const reason = question && $(`multiple-reason-${question[1]}`);
  if (reason) reason.value = '';
  $('evidence-confirmed').checked = false;
  clearFieldError();
  rememberDraft();
});
$('evidence-confirmed').addEventListener('change', () => {
  clearFieldError();
  rememberDraft();
});
function clearFieldError() {
  const invalid = $('detail-panel').querySelector('[aria-invalid="true"]');
  invalid?.removeAttribute('aria-invalid');
  invalid?.removeAttribute('aria-describedby');
  $('field-validation-error')?.remove();
}
function fieldError(control, message) {
  clearFieldError();
  const hint = element('p', message, 'error inline-error');
  hint.id = 'field-validation-error';
  hint.setAttribute('role', 'alert');
  control.closest('label').after(hint);
  control.setAttribute('aria-invalid', 'true');
  control.setAttribute('aria-describedby', hint.id);
  control.focus();
}
$('confirm-button').addEventListener('click', async () => {
  const {batchId, itemId} = state;
  try {
    const payload = confirmationPayload();
    if (!$('evidence-wrap').hidden && !payload.evidence_confirmed) {
      fieldError($('evidence-confirmed'), 'Bitte bestätige den sichtbaren Beleg für deine Korrekturen.');
      return;
    }
    if (payload.text.text_status === 'review_required') {
      fieldError($('final-text-status'), 'Bitte wähle einen abschließenden Status für den Freitext.');
      return;
    }
    const text = payload.text.german_translation.trim();
    if (payload.text.text_status === 'translated' ? !text : Boolean(text)) {
      fieldError($('final-text'), 'Text und Textstatus müssen zusammenpassen.');
      return;
    }
    $('confirm-button').disabled = true;
    await json(`/api/batches/${batchId}/items/${itemId}/confirm`, { method:'POST', body:payload });
    drafts.delete(itemId);
    dirtyDrafts.delete(itemId);
    trackDraftExit();
    if (state.batchId === batchId && state.itemId === itemId) {
      const next = nextReview(currentBatch.items, itemId);
      await openBatch(batchId, next?.id);
      if (next) focusReviewStart();
      else $('batch-overview').focus();
    }
    setMessage('Bogen gespeichert.');
  } catch (e) {
    if (state.itemId === itemId) inlineError('review-error', e.message);
  } finally {
    if (state.itemId === itemId) $('confirm-button').disabled = false;
  }
});

$('folder-input').addEventListener('change', () => {
  $('files-input').value = '';
  const files = Array.from($('folder-input').files);
  if (files.length) $('batch-name').value = files[0].webkitRelativePath?.split('/')[0] || 'Fotoordner';
});
$('files-input').addEventListener('change', () => {
  $('folder-input').value = '';
  if (!$('batch-name').value.trim()) $('batch-name').value = 'Neuer Vorgang';
});
$('upload-button').addEventListener('click', async () => {
  const files = Array.from($('folder-input').files?.length ? $('folder-input').files : $('files-input').files);
  inlineError('upload-error');
  if (!files.length) return inlineError('upload-error', 'Bitte Fotos oder einen Fotoordner auswählen.');
  const form = new FormData(); form.set('name', $('batch-name').value.trim() || 'Neuer Vorgang');
  for (const file of files) form.append('images', file, file.name);
  try {
    setMessage(`Lade ${files.length} Foto(s) hoch ...`);
    const result = await json('/api/batches', {method:'POST', body:form});
    $('folder-input').value = ''; $('files-input').value = '';
    setPanel('upload', false);
    await reloadBatches(result.id);
    const rejected = result.items.filter(x => x.status === 'error').length;
    setMessage(`${result.count - rejected} Foto(s) hochgeladen. ${rejected} Datei(en) konnten nicht verarbeitet werden.`, rejected > 0);
  } catch (e) { inlineError('upload-error', e.message); }
});
$('empty-demo').addEventListener('click', () => $('demo-button').click());
async function loadDemo(fullBatch) {
  if (creatingDemo) return;
  creatingDemo = true;
  for (const id of ['demo-button','batch-demo-button','empty-demo']) $(id).disabled = true;
  try {
    const batch = await json(`/api/demo?full_batch=${fullBatch}`, {method:'POST'});
    await reloadBatches(batch.id);
    document.querySelector('.demo-tools').open = false;
    setMessage('Neuer Testvorgang geöffnet.');
  } catch (e) { errMessage(e); } finally {
    creatingDemo = false;
    for (const id of ['demo-button','batch-demo-button','empty-demo']) $(id).disabled = false;
  }
}
$('demo-button').addEventListener('click', () => loadDemo(false));
$('batch-demo-button').addEventListener('click', () => loadDemo(true));
function setRename(open, restoreFocus = false) {
  $('batch-title-row').hidden = open;
  $('rename-form').hidden = !open;
  inlineError('rename-error');
  if (open) {
    $('selected-batch-name').value = currentBatch.name;
    $('selected-batch-name').focus();
    $('selected-batch-name').select();
  } else if (restoreFocus) $('rename-button').focus();
}
$('rename-button').addEventListener('click', () => setRename(true));
$('rename-cancel').addEventListener('click', () => setRename(false, true));
$('rename-form').addEventListener('keydown', event => {
  if (event.key === 'Escape') setRename(false, true);
});
$('rename-form').addEventListener('submit', async event => {
  event.preventDefault();
  const batchId = state.batchId;
  try {
    const updated = await json(`/api/batches/${batchId}`, {method:'PATCH', body:{name:$('selected-batch-name').value}});
    if (state.batchId !== batchId) return;
    currentBatch.name = updated.name;
    $('batch-title').textContent = updated.name;
    state.batches.find(batch => batch.id === batchId).name = updated.name;
    renderBatchList();
    setRename(false, true);
  } catch (e) { inlineError('rename-error', e.message); }
});
async function providerForRun(batchId) {
  const me = await json('/api/me');
  if (state.batchId !== batchId) return null;
  state.provider = me.provider;
  showApp();
  if (me.provider === 'openrouter' && !currentBatch.synthetic &&
      !window.confirm('Fotos werden zur Erkennung an OpenRouter übermittelt. Verwende ausschließlich synthetische Testdaten. Live-Verarbeitung starten?')) return null;
  return me.provider;
}
function beginRecognition() {
  state.busy = true;
  $('recognize-one-button').disabled = $('recognize-all-button').disabled = true;
}
$('recognize-one-button').addEventListener('click', async () => {
  if (!state.itemId || state.busy) return;
  const {batchId, itemId} = state;
  beginRecognition();
  try {
    setMessage('Foto wird verarbeitet ...');
    const provider = await providerForRun(batchId);
    if (!provider) return;
    await json(`/api/batches/${batchId}/items/${itemId}/recognize?expected_provider=${provider}`, {method:'POST'});
    setMessage('Foto verarbeitet. Ergebnis und Prüfhinweise kontrollieren.');
  } catch (e) { errMessage(e); } finally {
    state.busy = false;
    if (state.batchId === batchId) await openBatch(batchId, itemId).catch(errMessage);
  }
});
async function startRun(retry) {
  if (!state.batchId || state.busy) return;
  const batchId = state.batchId;
  beginRecognition();
  try {
    const provider = await providerForRun(batchId);
    if (!provider) return;
    await json(`/api/batches/${batchId}/process?retry_failed=${retry}&expected_provider=${provider}`, {method:'POST'});
  } catch (e) { errMessage(e); } finally {
    state.busy = false;
    if (state.batchId === batchId) await openBatch(batchId).catch(errMessage);
  }
}
$('recognize-all-button').addEventListener('click', () => startRun(false));
$('retry-button').addEventListener('click', () => startRun(true));
$('confirm-ready-button').addEventListener('click', async () => {
  const batchId = state.batchId;
  inlineError('bulk-error');
  $('confirm-ready-button').disabled = true;
  try {
    const result = await json(`/api/batches/${batchId}/confirm-ready`, {method:'POST'});
    if (state.batchId !== batchId) return;
    await openBatch(batchId);
    if (result.batch.confirmed === result.batch.count) $('export-button').focus();
    setMessage(`${result.accepted} Bögen gesammelt übernommen.`);
  } catch (e) {
    if (state.batchId !== batchId) return;
    inlineError('bulk-error', e.message);
    $('confirm-ready-button').disabled = false;
  }
});
$('export-button').addEventListener('click', async () => {
  inlineError('export-error');
  try {
    const batchId = state.batchId;
    const res = await request(`/api/batches/${batchId}/export.csv`);
    const exported = Number(res.headers.get('X-Exported-Count'));
    const open = Number(res.headers.get('X-Unconfirmed-Count'));
    if (open && !window.confirm(`Von ${exported + open} Bögen werden ${exported} exportiert. ${open} sind noch nicht final bestätigt. Teil-CSV herunterladen?`)) return;
    const blob = await res.blob(); const link = document.createElement('a'); const url = URL.createObjectURL(blob);
    link.href = url; link.download = `form-digitizer-${batchId.slice(0,8)}.csv`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage(`${res.headers.get('X-Exported-Count')} bestätigte Datensätze exportiert. ${res.headers.get('X-Unconfirmed-Count')} noch nicht bestätigte Bilder wurden nicht exportiert.`);
  } catch (e) { inlineError('export-error', e.message); }
});
restore();
