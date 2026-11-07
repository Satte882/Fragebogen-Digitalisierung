/* Native, dependency-free interface. Never interpolate model/user strings into innerHTML. */
'use strict';

const state = { role: null, csrf: null, provider: 'mock', batches: [], batchId: null, itemId: null, item: null, editing: false, busy: false };
const $ = id => document.getElementById(id);
const LABELS = {
  pending: 'Noch nicht verarbeitet', ready: 'Übernahmebereit', review_required: 'Manuelle Prüfung nötig',
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
  $('global-message').textContent = text || '';
  $('global-message').className = error ? 'is-error' : '';
}
function errMessage(e) { setMessage(e.message || String(e), true); }
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
    if (reply.status === 401) { showLogin(); }
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
  state.role = null; state.csrf = null;
  $('app-screen').hidden = true; $('login-screen').hidden = false;
}
function showApp() {
  $('login-screen').hidden = true; $('app-screen').hidden = false;
  $('role-indicator').textContent = state.role === 'admin' ? 'Administrator' : 'Testzugang · isolierte Sitzung';
  $('provider-indicator').textContent = state.provider === 'mock' ? 'DEMO ohne KI' : 'Gemini / OpenRouter';
  $('mock-banner').hidden = state.provider !== 'mock';
  $('admin-panel').hidden = state.role !== 'admin';
}
async function restore() {
  try {
    const session = await json('/api/me');
    state.role = session.role; state.csrf = session.csrf; state.provider = session.provider;
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
    showApp(); await reloadBatches();
    if (state.role === 'admin') await readConfig();
  } catch (e) { $('login-error').textContent = e.message; }
});
$('logout-button').addEventListener('click', async () => {
  try { await json('/api/logout', { method:'POST' }); } catch (_) { /* always close local view */ }
  state.batches = []; state.batchId = null; state.itemId = null;
  showLogin();
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
    state.batchId = null; state.itemId = null;
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
    list.append(b);
  }
}
async function openBatch(batchId) {
  const batch = await json('/api/batches/' + encodeURIComponent(batchId));
  state.batchId = batch.id;
  $('empty-state').hidden = true; $('batch-view').hidden = false;
  $('selected-batch-name').value = batch.name;
  $('batch-id').textContent = `Vorgangs-ID: ${batch.id}` + (batch.synthetic ? ' · SYNTHETISCHE DEMO (keine KI)' : '');
  const corrected = batch.items.filter(item => item.review_mode === 'corrected').length;
  const confirmed = batch.items.filter(item => item.status === 'confirmed').length;
  $('batch-summary').textContent = `${batch.count} Bilder · ${confirmed} final bestätigt (${corrected} manuell korrigiert) · ` +
    `${batch.items.filter(x => x.status === 'ready').length} übernahmebereit · ` +
    `${batch.items.filter(x => x.status === 'review_required').length} Prüfungen offen · ` +
    `${batch.items.filter(x => x.status === 'error').length} Fehler`;
  $('recognize-all-button').disabled = state.busy || !batch.items.some(x => ['pending','error'].includes(x.status));
  $('confirm-ready-button').disabled = state.busy || !batch.items.some(x => x.status === 'ready');
  $('export-button').disabled = confirmed === 0;
  const list = $('photo-list'); list.replaceChildren();
  for (const item of batch.items) {
    const card = element('button', null, 'photo-entry' + (item.id === state.itemId ? ' selected' : ''));
    card.append(element('strong', `${item.sequence}. ${item.filename}`));
    card.append(element('span', LABELS[item.status] || item.status, `status ${item.status}`));
    if (item.review_mode) card.append(element('span', item.review_mode === 'corrected' ? 'Mit Korrektur' : 'Ohne Korrektur', 'small'));
    card.addEventListener('click', () => openItem(item.id).catch(errMessage));
    list.append(card);
  }
  renderBatchList();
  if (batch.items.length) {
    const target = batch.items.some(x => x.id === state.itemId) ? state.itemId : batch.items[0].id;
    await openItem(target, false);
  } else { $('detail-panel').hidden = true; }
}
async function openItem(itemId, refreshList = true) {
  if (!state.batchId) return;
  state.itemId = itemId; state.editing = false;
  state.item = await json(`/api/batches/${state.batchId}/items/${itemId}`);
  state.editing = Boolean(state.item.review_started);
  renderDetail();
  if (refreshList) {
    for (const b of $('photo-list').querySelectorAll('button')) {
      b.classList.toggle('selected', b.textContent.startsWith(state.item.sequence + '. '));
    }
  }
}
function renderRaw(item) {
  const block = $('raw-fields'); block.replaceChildren();
  if (!item.raw) {
    block.append(element('p', item.error || 'Noch keine Erkennung durchgeführt.', 'small')); return;
  }
  for (let i = 1; i <= 5; i++) {
    const field = item.raw[`q${i}`];
    const node = element('div', null, 'field' + (['unreadable','multiple'].includes(field.status) ? ' warning' : ''));
    node.append(element('strong', `Frage ${i}`));
    node.append(element('div', field.status === 'answered' ? `Erkannt: ${field.value}` : `Status: ${LABELS[field.status] || field.status}`, 'field-text'));
    block.append(node);
  }
  const original = element('div', null, 'field');
  original.append(element('strong', `Originalfreitext (${item.raw.text.source_language})`));
  original.append(element('div', item.raw.text.original_transcript || '(leer / unlesbar)', 'field-text'));
  block.append(original);
  const german = element('div', null, 'field' + (['review_required','unreadable'].includes(item.raw.text.text_status) ? ' warning' : ''));
  german.append(element('strong', 'Deutsch (Modellvorschlag)'));
  german.append(element('div', item.raw.text.german_translation || '(kein Text)', 'field-text'));
  german.append(element('p', LABELS[item.raw.text.text_status] || item.raw.text.text_status, 'small'));
  block.append(german);
  if (item.raw.warnings?.length) {
    const warn = element('div', null, 'field warning'); warn.append(element('strong', 'Prüfhinweise'));
    item.raw.warnings.forEach(x => warn.append(element('p', x, 'small'))); block.append(warn);
  }
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
  const canShow = Boolean(item.final || item.draft) || Boolean(item.raw && (item.status === 'ready' || state.editing));
  const edit = state.editing && !confirmed;
  $('edit-button').disabled = confirmed || !item.raw;
  $('edit-button').hidden = confirmed;
  $('confirm-button').hidden = confirmed;
  $('reopen-button').hidden = !confirmed;
  $('confirm-button').disabled = !canShow || (item.status === 'review_required' && !edit);
  $('evidence-wrap').hidden = !edit;
  $('evidence-confirmed').checked = false;
  if (!canShow) {
    parent.append(element('p', item.status === 'review_required'
      ? 'Die KI-Erkennung ist unklar. Mit „Manuell prüfen“ wird die rechte Spalte freigeschaltet.'
      : 'Die finale Fassung erscheint nach der Bilderkennung.', 'small'));
    return;
  }
  const data = item.final || item.draft || item.raw;
  for (let i = 1; i <= 5; i++) {
    const container = element('div', null, 'field');
    const label = element('label', `Frage ${i}`);
    const select = element('select'); select.id = `final-q${i}`;
    for (const entry of answerOptions) {
      const opt = element('option', entry.label); opt.value = entry.value; select.append(opt);
    }
    select.value = answerToChoice(data[`q${i}`]); select.disabled = !edit;
    label.append(select); container.append(label); parent.append(container);
  }
  const field = element('div', null, 'field');
  const label = element('label', 'Deutscher Freitext (final)');
  const textarea = element('textarea'); textarea.id = 'final-text'; textarea.value = data.text.german_translation || '';
  textarea.disabled = !edit; label.append(textarea); field.append(label);
  const textLabel = element('label', 'Textstatus');
  const textSelect = element('select'); textSelect.id = 'final-text-status';
  for (const [code, title] of [['review_required','Bitte Textstatus prüfen'],['translated','Übersetzt / Deutsch vorhanden'],['empty','Keine Angabe'],['unreadable','Unlesbar']]) {
    const opt = element('option', title); opt.value = code; textSelect.append(opt);
  }
  textSelect.value = data.text.text_status;
  textSelect.querySelector('option[value=review_required]').disabled = true;
  textSelect.disabled = !edit;
  textLabel.append(textSelect); field.append(textLabel); parent.append(field);
  if (confirmed) parent.append(element('p', item.review_mode === 'corrected' ? '✓ Final bestätigt, mit Korrektur.' : '✓ Final bestätigt, ohne Korrektur.', 'status confirmed'));
}
function renderDetail() {
  const item = state.item;
  if (!item) return;
  $('detail-panel').hidden = false;
  $('item-indicator').textContent = `Bild ${item.sequence} · ${LABELS[item.status] || item.status}`;
  $('item-indicator').className = `status ${item.status}`;
  $('source-image').src = item.image_url;
  $('source-image').classList.remove('expanded'); $('source-image').hidden = false;
  $('source-note').textContent = item.source === 'synthetic_demo'
    ? 'SYNTHETISCHE FIXDATEN – kein OCR/LLM-Aufruf. Nur Darstellung des Prüfprozesses.'
    : state.provider === 'mock' ? 'Demo-Adapter ohne Erkennung. Nicht als Modellleistung interpretieren.'
    : 'Ausgabe des multimodalen Modells. Aussagen müssen am Originalfoto geprüft werden.';
  $('raw-json').textContent = item.raw_text || '(noch keine KI-Ausgabe)';
  $('recognize-one-button').disabled = state.busy || item.status === 'confirmed' || item.source === 'synthetic_demo';
  $('recognize-one-button').hidden = item.source === 'synthetic_demo';
  renderRaw(item); renderFinal(item);
}
$('toggle-image-button').addEventListener('click', () => { $('source-image').hidden = !$('source-image').hidden; });
$('source-image').addEventListener('click', () => { $('source-image').classList.toggle('expanded'); });
$('edit-button').addEventListener('click', async () => {
  if (!state.item?.raw || state.item.status === 'confirmed') return;
  try {
    await json(`/api/batches/${state.batchId}/items/${state.itemId}/review`, {method:'POST'});
    state.editing = true; state.item.review_started = true; renderFinal(state.item);
  } catch (e) { errMessage(e); }
});
$('reopen-button').addEventListener('click', async () => {
  try {
    await json(`/api/batches/${state.batchId}/items/${state.itemId}/reopen`, {method:'POST'});
    await openBatch(state.batchId); setMessage('Datensatz erneut geöffnet. Vor dem Export erneut final bestätigen.');
  } catch (e) { errMessage(e); }
});
function confirmationPayload() {
  const final = { evidence_confirmed: $('evidence-confirmed').checked };
  for (let i = 1; i <= 5; i++) {
    const choice = $(`final-q${i}`).value;
    final[`q${i}`] = choice.startsWith('answered:')
      ? {status:'answered',value:Number(choice.split(':')[1])}
      : {status:choice,value:null};
  }
  final.text = { german_translation:$('final-text').value, text_status:$('final-text-status').value };
  return final;
}
$('confirm-button').addEventListener('click', async () => {
  try {
    const payload = confirmationPayload();
    await json(`/api/batches/${state.batchId}/items/${state.itemId}/confirm`, { method:'POST', body:payload });
    await openBatch(state.batchId); setMessage('Datensatz final bestätigt.');
  } catch (e) { errMessage(e); }
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
  if (!files.length) return setMessage('Bitte Fotos oder einen Fotoordner auswählen.', true);
  const form = new FormData(); form.set('name', $('batch-name').value.trim() || 'Neuer Vorgang');
  for (const file of files) form.append('images', file, file.name);
  try {
    setMessage(`Lade ${files.length} Foto(s) hoch ...`);
    const result = await json('/api/batches', {method:'POST', body:form});
    $('folder-input').value = ''; $('files-input').value = '';
    await reloadBatches(result.id); setMessage(`${files.length} Foto(s) hochgeladen. Jetzt „Alle offenen Fotos erkennen“ auswählen.`);
  } catch (e) { errMessage(e); }
});
$('demo-button').addEventListener('click', async () => {
  try {
    const batch = await json('/api/demo', {method:'POST'});
    await reloadBatches(batch.id);
    setMessage('Synthetische Demobilder geladen. Diese sind vorbereitete Daten, keine KI-Erkennung.');
  } catch (e) { errMessage(e); }
});
$('rename-button').addEventListener('click', async () => {
  try {
    await json(`/api/batches/${state.batchId}`, {method:'PATCH', body:{name:$('selected-batch-name').value}});
    await openBatch(state.batchId); setMessage('Vorgangsname aktualisiert.');
  } catch (e) { errMessage(e); }
});
async function recognize(id) {
  await json(`/api/batches/${state.batchId}/items/${id}/recognize`, {method:'POST'});
}
$('recognize-one-button').addEventListener('click', async () => {
  if (!state.itemId) return;
  try {
    state.busy = true;
    setMessage('Foto wird verarbeitet ...');
    await recognize(state.itemId);
    await openBatch(state.batchId); setMessage('Foto verarbeitet. Ergebnis und Prüfhinweise kontrollieren.');
  } catch (e) { errMessage(e); } finally { state.busy = false; }
});
$('recognize-all-button').addEventListener('click', async () => {
  if (!state.batchId) return;
  const batchId = state.batchId;
  try {
    state.busy = true;
    const batch = await json(`/api/batches/${batchId}`);
    const pending = batch.items.filter(x => ['pending','error'].includes(x.status));
    let passed = 0, failed = 0;
    for (const item of pending) {
      setMessage(`Erkenne Bild ${passed + failed + 1} von ${pending.length} ...`);
      try { await recognize(item.id); passed++; } catch (_) { failed++; }
    }
    await openBatch(batchId);
    setMessage(`${passed} verarbeitet, ${failed} mit Fehler. Bitte Ergebnisse prüfen.`, failed > 0);
  } catch (e) { errMessage(e); } finally { state.busy = false; }
});
$('confirm-ready-button').addEventListener('click', async () => {
  try {
    const result = await json(`/api/batches/${state.batchId}/confirm-ready`, {method:'POST'});
    await openBatch(state.batchId);
    setMessage(`${result.accepted} grüne Datensätze final übernommen. Gelbe Fälle bleiben zur Prüfung offen.`);
  } catch (e) { errMessage(e); }
});
$('export-button').addEventListener('click', async () => {
  try {
    const res = await request(`/api/batches/${state.batchId}/export.csv`);
    const blob = await res.blob(); const link = document.createElement('a'); const url = URL.createObjectURL(blob);
    link.href = url; link.download = `form-digitizer-${state.batchId.slice(0,8)}.csv`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage(`${res.headers.get('X-Exported-Count')} bestätigte Datensätze exportiert. ${res.headers.get('X-Unconfirmed-Count')} noch nicht bestätigte Bilder wurden nicht exportiert.`);
  } catch (e) { errMessage(e); }
});
restore();
