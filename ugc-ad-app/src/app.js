import {
  PLATFORMS, CREATOR_ROLES, CATEGORIES, CTA_TYPES, HOOK_TYPES, QA_CHECKLIST,
  buildBatch, checkClaims, scriptChecks, toMarkdown,
} from './generator.js';
import { PRESETS } from './presets.js';

const STORE_KEY = 'ugc-ad-studio:v1';
const $ = (sel, root = document) => root.querySelector(sel);
const form = $('#brief');
let current = null;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// --- storage (best effort; private windows may throw) ----------------------
function loadStore() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || { projects: {}, last: null, qa: {} }; }
  catch { return { projects: {}, last: null, qa: {} }; }
}
function saveStore(s) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(s)); } catch { /* ignore */ }
}
const store = loadStore();
store.qa ||= {};

// --- form setup -------------------------------------------------------------
function fillSelect(el, map) {
  el.innerHTML = Object.entries(map).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('');
}
fillSelect($('#category'), CATEGORIES);
fillSelect($('#creatorRole'), CREATOR_ROLES);
fillSelect($('#ctaType'), CTA_TYPES);
$('#platforms').innerHTML = Object.entries(PLATFORMS).map(([k, p]) =>
  `<label class="chip"><input type="checkbox" name="platforms" value="${k}"${k === 'tiktok' ? ' checked' : ''}>${esc(p.label)} <small>${p.aspect}</small></label>`
).join('');
$('#preset').insertAdjacentHTML('beforeend',
  Object.entries(PRESETS).map(([k, p]) => `<option value="${k}">${esc(p.name)}</option>`).join(''));

function readForm() {
  const fd = new FormData(form);
  const brief = Object.fromEntries([...fd.entries()].filter(([k]) => k !== 'platforms'));
  brief.platforms = fd.getAll('platforms');
  brief.disclosure = form.elements.disclosure.checked;
  return brief;
}

function writeForm(brief) {
  store.hookTypes = brief.hookTypes || null;
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.name === 'platforms') el.checked = (brief.platforms || []).includes(el.value);
    else if (el.type === 'checkbox') el.checked = brief[el.name] !== false;
    else if (brief[el.name] !== undefined) el.value = brief[el.name];
    else if (el.tagName !== 'SELECT' && el.type !== 'range') el.value = '';
  }
  render();
}

function refreshSaved() {
  const names = Object.keys(store.projects).sort();
  $('#saved').innerHTML = '<option value="">Saved projects…</option>' +
    names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join('');
}

// --- rendering --------------------------------------------------------------
// Hooks picked in the Batch tab; the variant slider trims the list or pads
// it with the remaining hook types in default order.
function withHooks(brief) {
  const picked = store.hookTypes;
  if (!picked || !picked.length) return brief;
  const n = Number(brief.variantCount);
  const rest = Object.keys(HOOK_TYPES).filter((h) => !picked.includes(h));
  return { ...brief, hookTypes: [...picked, ...rest].slice(0, n) };
}

function render() {
  const brief = withHooks(readForm());
  $('#durationOut').textContent = brief.duration;
  $('#variantOut').textContent = brief.variantCount;
  current = buildBatch(brief);
  store.last = brief;
  saveStore(store);
  $('#outTitle').textContent = `2. ${current.brief.product}: ${current.variants.length} ad${current.variants.length === 1 ? '' : 's'}`;
  renderBatch();
  renderScripts();
  renderPrompts();
  renderCompliance();
  renderQa();
}

function renderBatch() {
  const { constants, variants, brief } = current;
  $('#tab-batch').innerHTML = `
    <p class="note">Lock everything except the hook. Then if one ad wins, you know <em>the hook</em> made the difference. Read hook rate (3-second views) first, then CPA.</p>
    <dl class="constants">
      <div><dt>Locked proof</dt><dd>${esc(constants.proof)}</dd></div>
      <div><dt>Locked CTA</dt><dd>${esc(constants.cta)}</dd></div>
      <div><dt>Creator</dt><dd>${esc(constants.creatorRole)}</dd></div>
      <div><dt>Platforms</dt><dd>${brief.platforms.map((p) => `${PLATFORMS[p].label} ${PLATFORMS[p].aspect}`).join(' · ')}</dd></div>
    </dl>
    <div class="hook-picker">
      <span>Hook types:</span>
      ${Object.entries(HOOK_TYPES).map(([k, h]) =>
        `<button type="button" class="pill${variants.some((v) => v.hookType === k) ? ' on' : ''}" data-hook="${k}" title="${esc(h.angle)}">${esc(h.label)}</button>`
      ).join('')}
    </div>
    <table class="matrix">
      <thead><tr><th>#</th><th>Hook type</th><th>Angle</th><th>Hook line</th></tr></thead>
      <tbody>${variants.map((v) => `
        <tr><td>${v.id}</td><td>${esc(v.hookLabel)}</td><td>${esc(v.angle)}</td><td>${esc(v.hook)}</td></tr>`).join('')}
      </tbody>
    </table>`;
}

function renderScripts() {
  const b = current.brief;
  $('#tab-scripts').innerHTML = current.variants.map((v) => {
    const checks = scriptChecks(v.script, b);
    const over = v.script.readSeconds > b.duration;
    return `
    <article class="card">
      <header><h3>Ad ${v.id} · ${esc(v.hookLabel)}</h3>
        <span class="meter${over ? ' warn' : ''}">${v.script.words}/${v.script.targetWords} words · ${v.script.readSeconds}s</span>
        <button type="button" class="ghost small" data-copy="script-${v.id}">Copy</button>
      </header>
      <table class="beats">${v.script.beats.map((x) => `
        <tr><th>${esc(x.beat)}<small>${x.start}-${x.end}s</small></th><td contenteditable="true" spellcheck="true">${esc(x.line)}</td></tr>`).join('')}
      </table>
      <ul class="checks">${checks.map((c) => `<li class="${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '!'} ${esc(c.label)}</li>`).join('')}</ul>
    </article>`;
  }).join('');
}

function renderPrompts() {
  $('#tab-prompts').innerHTML = `
    <p class="note">Paste these into your video model (Veo, Sora, Kling, Seedance, Runway…). Start with a 6-10s cut, check face, hands and label, then extend.</p>
    ${current.variants.map((v) => Object.entries(v.prompts).map(([p, prompt]) => `
      <article class="card">
        <header><h3>Ad ${v.id} · ${esc(v.hookLabel)} · ${esc(PLATFORMS[p].label)}</h3>
          <button type="button" class="ghost small" data-copy="prompt-${v.id}-${p}">Copy prompt</button>
        </header>
        <pre id="prompt-${v.id}-${p}">${esc(prompt)}</pre>
      </article>`).join('')).join('')}`;
}

function highlight(text, findings) {
  let out = '', i = 0;
  for (const f of findings) {
    if (f.index < i) continue;
    out += esc(text.slice(i, f.index)) + `<mark class="${f.level}" title="${esc(f.why)}">${esc(f.match)}</mark>`;
    i = f.index + f.match.length;
  }
  return out + esc(text.slice(i));
}

function renderCompliance() {
  const all = current.variants.map((v) => v.script.beats.map((x) => x.line).join(' ')).join('\n');
  const findings = checkClaims(all);
  $('#tab-compliance').innerHTML = `
    <p class="note">Every generated script is checked automatically. Paste any other copy below (a caption, a client script, a voiceover) to check it too.</p>
    <div class="summary ${findings.length ? 'warn' : 'ok'}">
      ${findings.length ? `${findings.length} risky phrase${findings.length > 1 ? 's' : ''} found in the generated scripts.` : 'No risky claims found in the generated scripts.'}
    </div>
    ${findings.length ? `<ul class="findings">${findings.map((f) => `<li><mark class="${f.level}">${esc(f.match)}</mark> ${esc(f.why)}</li>`).join('')}</ul>` : ''}
    <label class="block">Check your own copy
      <textarea id="claimInput" rows="5" placeholder="e.g. This serum is clinically proven and guaranteed to clear your skin in 7 days!">${esc(store.claimDraft || '')}</textarea>
    </label>
    <div id="claimOut" class="claim-out"></div>`;
  checkCustom();
}

function checkCustom() {
  const ta = $('#claimInput');
  if (!ta) return;
  const text = ta.value;
  const f = checkClaims(text);
  $('#claimOut').innerHTML = text.trim()
    ? `<p class="hl">${highlight(text, f)}</p>` +
      (f.length ? `<ul class="findings">${f.map((x) => `<li><mark class="${x.level}">${esc(x.match)}</mark> ${esc(x.why)}</li>`).join('')}</ul>` : '<p class="ok-text">✓ Looks clean.</p>')
    : '';
}

function renderQa() {
  const key = current.brief.product;
  const done = store.qa[key] || {};
  const total = QA_CHECKLIST.reduce((n, [, items]) => n + items.length, 0);
  const count = Object.values(done).filter(Boolean).length;
  $('#tab-qa').innerHTML = `
    <div class="progress"><span style="width:${(count / total) * 100}%"></span></div>
    <p class="note">${count} of ${total} checked for <strong>${esc(key)}</strong>. Go through these before you deliver or publish.</p>
    ${QA_CHECKLIST.map(([group, items]) => `
      <fieldset class="qa"><legend>${esc(group)}</legend>
        ${items.map((item) => `<label class="check"><input type="checkbox" data-qa="${esc(item)}"${done[item] ? ' checked' : ''}> ${esc(item)}</label>`).join('')}
      </fieldset>`).join('')}`;
}

// --- actions ----------------------------------------------------------------
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, 1800);
}

async function copy(text, label = 'Copied') {
  try { await navigator.clipboard.writeText(text); toast(label); }
  catch { toast('Copy failed. Select the text manually.'); }
}

function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const slug = () => current.brief.product.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'ugc-ad';

form.addEventListener('input', render);
form.addEventListener('change', render);

$('#preset').addEventListener('change', (e) => {
  const p = PRESETS[e.target.value];
  if (p) writeForm(p.brief);
  e.target.value = '';
});

$('#saved').addEventListener('change', (e) => {
  const p = store.projects[e.target.value];
  if (p) writeForm(p);
  e.target.value = '';
});

$('#save').addEventListener('click', () => {
  const brief = withHooks(readForm());
  const name = (brief.product || 'Untitled').trim();
  store.projects[name] = brief;
  saveStore(store);
  refreshSaved();
  toast(`Saved "${name}"`);
});

$('#copyMd').addEventListener('click', () => copy(toMarkdown(current), 'Markdown copied'));
$('#dlMd').addEventListener('click', () => download(`${slug()}-ugc-batch.md`, toMarkdown(current), 'text/markdown'));
$('#dlJson').addEventListener('click', () => download(`${slug()}-ugc-batch.json`, JSON.stringify(current, null, 2), 'application/json'));

document.querySelector('.tabs').addEventListener('click', (e) => {
  const tab = e.target.closest('[data-tab]');
  if (!tab) return;
  for (const b of document.querySelectorAll('.tabs [data-tab]')) b.setAttribute('aria-selected', String(b === tab));
  for (const p of document.querySelectorAll('.tab')) p.hidden = p.id !== `tab-${tab.dataset.tab}`;
});

document.querySelector('.output').addEventListener('click', (e) => {
  const hookBtn = e.target.closest('[data-hook]');
  if (hookBtn) {
    const active = current.variants.map((v) => v.hookType);
    const k = hookBtn.dataset.hook;
    const next = active.includes(k) ? active.filter((h) => h !== k) : [...active, k];
    if (!next.length) return;
    // Keep the variant slider in sync with the hooks the user picked.
    form.elements.variantCount.value = next.length;
    store.hookTypes = next;
    render();
    return;
  }
  const copyBtn = e.target.closest('[data-copy]');
  if (copyBtn) {
    const id = copyBtn.dataset.copy;
    if (id.startsWith('script-')) {
      const card = copyBtn.closest('.card');
      const text = [...card.querySelectorAll('.beats tr')].map((tr) =>
        `${tr.querySelector('th').firstChild.textContent} (${tr.querySelector('small').textContent}): ${tr.querySelector('td').innerText.trim()}`
      ).join('\n');
      copy(text, 'Script copied');
    } else {
      copy(document.getElementById(id).textContent, 'Prompt copied');
    }
  }
});

document.querySelector('.output').addEventListener('input', (e) => {
  if (e.target.id === 'claimInput') {
    store.claimDraft = e.target.value;
    saveStore(store);
    checkCustom();
  }
});

document.querySelector('.output').addEventListener('change', (e) => {
  const item = e.target.dataset.qa;
  if (item === undefined) return;
  const key = current.brief.product;
  store.qa[key] = { ...(store.qa[key] || {}), [item]: e.target.checked };
  saveStore(store);
  renderQa();
});

refreshSaved();
writeForm(store.last || PRESETS.gripmount.brief);
