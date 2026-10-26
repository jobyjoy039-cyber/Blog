// AI Studio UI: concept → AI scene → playback with music/SFX → video export.
import { normalizeScene, SOUNDS, MOODS } from './scene.js';
import { drawFrame } from './renderer.js';
import { AudioEngine } from './audio.js';
import { generateScene, PROVIDERS } from './ai.js';
import { DEMO_SCENE } from './demo.js';
import { listSounds, putSound } from './store.js';
import { saveBlob } from './bridge.js';

const $ = (id) => document.getElementById(id);
const canvas = $('stage'), ctx = canvas.getContext('2d');
const audio = new AudioEngine();

const store = {
  get(key, d) { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { toast('Could not save on this device.'); } },
};

const state = { scene: null, t: 0, playing: false, loop: false, exporting: false, customNames: [] };
let settings = store.get('studio.settings', { provider: 'claude', keys: {}, models: { claude: 'claude-opus-5-5', openai: 'gpt-5' } });

function toast(msg, ms = 3200) {
  const el = $('toast'); el.textContent = msg; el.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => (el.hidden = true), ms);
}
function showError(msg) { const el = $('error'); el.textContent = msg || ''; el.hidden = !msg; }

function setScene(raw, { keepTime = false } = {}) {
  const { scene, warnings } = normalizeScene(raw, state.customNames);
  scene.sfxVolume = Number.isFinite(raw?.sfxVolume) ? raw.sfxVolume : 1;
  state.scene = scene;
  if (!keepTime) state.t = 0;
  state.t = Math.min(state.t, scene.duration);
  $('scrub').max = scene.duration;
  $('json').value = JSON.stringify(scene, null, 2);
  $('warnings').innerHTML = warnings.map((w) => `<li>⚠ ${escapeHtml(w)}</li>`).join('');
  store.set('studio.current', scene);
  renderSoundPanel();
  draw();
}
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function draw() {
  if (!state.scene) return;
  drawFrame(ctx, state.scene, state.t);
  $('scrub').value = state.t;
  $('time').textContent = `${state.t.toFixed(1)} / ${state.scene.duration.toFixed(1)}s`;
}

// ---------- playback ----------
function play() {
  if (!state.scene) return;
  if (state.t >= state.scene.duration - 0.05) state.t = 0;
  audio.play(state.scene, state.t);
  state.playing = true;
  $('play').textContent = '❚❚';
  tick();
}
function pause() {
  audio.stop();
  state.playing = false;
  $('play').textContent = '▶';
}
function tick() {
  if (!state.playing) return;
  const pos = audio.position();
  state.t = pos ?? state.t;
  if (state.t >= state.scene.duration) {
    if (state.loop) { state.t = 0; audio.play(state.scene, 0); }
    else { state.t = state.scene.duration; pause(); draw(); return; }
  }
  draw();
  requestAnimationFrame(tick);
}
$('play').onclick = () => (state.playing ? pause() : play());
$('scrub').oninput = (e) => { const was = state.playing; if (was) pause(); state.t = Number(e.target.value); draw(); };
$('loop').onclick = (e) => { state.loop = !state.loop; e.currentTarget.setAttribute('aria-pressed', String(state.loop)); };

// ---------- AI ----------
function updateProviderHint() {
  const p = settings.provider, key = settings.keys[p];
  $('providerHint').textContent = key ? `Using ${PROVIDERS[p].label} · ${settings.models[p]}` : `No API key yet. Tap ⚙ to add a ${PROVIDERS[p].label} key. You can still play the demo and edit sounds.`;
}

async function runAI(revise) {
  const concept = (revise ? $('refine') : $('concept')).value.trim();
  if (!concept) { showError(revise ? 'Describe what to change.' : 'Describe your animation concept first.'); return; }
  showError('');
  pause();
  const p = settings.provider;
  $('busy').hidden = false;
  $('busyText').textContent = revise ? 'Revising your animation…' : `Directing your animation with ${PROVIDERS[p].label}…`;
  for (const b of [$('generate'), $('refineBtn')]) b.disabled = true;
  try {
    const raw = await generateScene({
      provider: p, key: settings.keys[p], model: settings.models[p], concept,
      duration: Number($('duration').value) || 0,
      current: revise ? state.scene : null,
      customSounds: state.customNames,
    });
    setScene(raw);
    if (revise) $('refine').value = '';
    toast(`“${state.scene.title}” is ready`);
    play();
  } catch (err) {
    showError(err.message || String(err));
  } finally {
    $('busy').hidden = true;
    for (const b of [$('generate'), $('refineBtn')]) b.disabled = false;
  }
}
$('generate').onclick = () => runAI(false);
$('refineBtn').onclick = () => runAI(true);

// ---------- settings ----------
$('provider').innerHTML = Object.entries(PROVIDERS).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join('');
function fillSettings(p) {
  $('provider').value = p;
  $('model').value = settings.models[p] || PROVIDERS[p].models[0];
  $('modelList').innerHTML = PROVIDERS[p].models.map((m) => `<option value="${m}">`).join('');
  $('apiKey').value = settings.keys[p] || '';
  $('apiKey').placeholder = PROVIDERS[p].keyHint;
}
$('openSettings').onclick = () => { fillSettings(settings.provider); $('settings').showModal(); };
$('provider').onchange = (e) => fillSettings(e.target.value);
$('saveSettings').onclick = () => {
  const p = $('provider').value;
  settings = { ...settings, provider: p, keys: { ...settings.keys, [p]: $('apiKey').value.trim() }, models: { ...settings.models, [p]: $('model').value.trim() || PROVIDERS[p].models[0] } };
  store.set('studio.settings', settings);
  updateProviderHint();
  toast('Settings saved');
};

// ---------- sound panel ----------
function soundOptions(selected) {
  const custom = state.customNames.map((n) => `<option value="custom:${escapeHtml(n)}"${selected === `custom:${n}` ? ' selected' : ''}>🎵 ${escapeHtml(n)}</option>`).join('');
  return SOUNDS.map((s) => `<option value="${s}"${s === selected ? ' selected' : ''}>${s}</option>`).join('') + custom;
}
function renderSoundPanel() {
  const s = state.scene;
  if (!s) return;
  $('mood').innerHTML = MOODS.map((m) => `<option value="${m}"${m === s.music.mood ? ' selected' : ''}>${m}</option>`).join('');
  $('bpm').value = s.music.bpm;
  $('musicVol').value = s.music.volume;
  $('sfxVol').value = s.sfxVolume;
  $('musicFile').innerHTML = '<option value="">Generated by mood</option>' + state.customNames.map((n) => `<option value="${escapeHtml(n)}"${n === s.music.custom ? ' selected' : ''}>${escapeHtml(n)}</option>`).join('');
  const sel = $('newSound').value;
  $('newSound').innerHTML = soundOptions(sel || 'punch');
  $('sfxCount').textContent = `(${s.sfx.length})`;
  $('cues').innerHTML = s.sfx.map((c, i) => `<li data-i="${i}">
    <input type="number" step="0.05" min="0" max="${s.duration}" value="${c.t}" data-f="t" aria-label="Time" />
    <select data-f="sound" aria-label="Sound">${soundOptions(c.sound)}</select>
    <input type="range" min="0" max="2" step="0.1" value="${c.volume}" data-f="volume" aria-label="Volume" />
    <button class="btn small" data-a="hear" aria-label="Hear">▶</button>
    <button class="btn small" data-a="go" aria-label="Go to time">⇥</button>
    <button class="btn small" data-a="del" aria-label="Delete">✕</button></li>`).join('');
}
function soundChanged() { store.set('studio.current', state.scene); $('json').value = JSON.stringify(state.scene, null, 2); if (state.playing) { audio.play(state.scene, state.t); } }
$('mood').onchange = (e) => { state.scene.music.mood = e.target.value; soundChanged(); };
$('bpm').onchange = (e) => { state.scene.music.bpm = Math.max(0, Math.min(220, Number(e.target.value) || 0)); soundChanged(); };
$('musicVol').oninput = (e) => { state.scene.music.volume = Number(e.target.value); };
$('musicVol').onchange = soundChanged;
$('sfxVol').oninput = (e) => { state.scene.sfxVolume = Number(e.target.value); };
$('sfxVol').onchange = soundChanged;
$('musicFile').onchange = (e) => { state.scene.music.custom = e.target.value; soundChanged(); };
$('previewSound').onclick = () => audio.preview($('newSound').value);
$('addSound').onclick = () => {
  state.scene.sfx.push({ t: Math.round(state.t * 100) / 100, sound: $('newSound').value, volume: 1 });
  state.scene.sfx.sort((a, b) => a.t - b.t);
  renderSoundPanel(); soundChanged();
  toast(`Added ${$('newSound').value} at ${state.t.toFixed(2)}s`);
};
$('cues').addEventListener('change', (e) => {
  const li = e.target.closest('li'); if (!li) return;
  const cue = state.scene.sfx[Number(li.dataset.i)], f = e.target.dataset.f;
  if (!f) return;
  cue[f] = f === 'sound' ? e.target.value : Math.max(0, Number(e.target.value) || 0);
  if (f === 't') { state.scene.sfx.sort((a, b) => a.t - b.t); renderSoundPanel(); }
  soundChanged();
});
$('cues').addEventListener('click', (e) => {
  const a = e.target.dataset.a, li = e.target.closest('li'); if (!a || !li) return;
  const i = Number(li.dataset.i), cue = state.scene.sfx[i];
  if (a === 'hear') audio.preview(cue.sound);
  if (a === 'go') { pause(); state.t = cue.t; draw(); }
  if (a === 'del') { state.scene.sfx.splice(i, 1); renderSoundPanel(); soundChanged(); }
});
$('importAudio').onchange = async (e) => {
  const file = e.target.files[0]; e.target.value = '';
  if (!file) return;
  const base = file.name.replace(/\.[^.]+$/, '').replace(/[^\w -]/g, '').trim().slice(0, 40) || 'sound';
  let name = base, n = 2;
  while (state.customNames.includes(name)) name = `${base} ${n++}`;
  try {
    const data = await file.arrayBuffer();
    const buf = await audio.addCustom(name, data);
    await putSound(name, data);
    state.customNames.push(name);
    if (buf.duration > 8 && confirm(`Use “${name}” (${Math.round(buf.duration)}s) as this animation's music?`)) state.scene.music.custom = name;
    renderSoundPanel(); soundChanged();
    toast(`Imported “${name}”. It's now in every sound list, and the AI can use it too.`);
  } catch (err) {
    toast(`Could not read that audio file: ${err.message || err}`);
  }
};

// ---------- tabs ----------
document.querySelectorAll('[role=tab]').forEach((b) => (b.onclick = () => {
  document.querySelectorAll('[role=tab]').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
  document.querySelectorAll('.tab').forEach((t) => (t.hidden = t.id !== `tab-${b.dataset.tab}`));
  if (b.dataset.tab === 'library') renderLibrary();
}));

// ---------- script ----------
$('applyJson').onclick = () => {
  try { setScene(JSON.parse($('json').value), { keepTime: true }); toast('Script applied'); }
  catch (err) { toast(`Invalid JSON: ${err.message}`); }
};

// ---------- library ----------
function renderLibrary() {
  const lib = store.get('studio.library', []);
  $('library').innerHTML = lib.length ? lib.map((p, i) => `<li data-i="${i}"><span>${escapeHtml(p.scene.title)}<br><small>${new Date(p.saved).toLocaleString()} · ${p.scene.duration}s</small></span>
    <button class="btn small" data-a="open">Open</button><button class="btn small" data-a="del" aria-label="Delete">✕</button></li>`).join('') : '<li><span class="hint">Nothing saved yet.</span></li>';
}
$('saveProject').onclick = () => {
  const lib = store.get('studio.library', []);
  const i = lib.findIndex((p) => p.scene.title === state.scene.title);
  const entry = { saved: Date.now(), scene: state.scene };
  if (i >= 0) lib[i] = entry; else lib.unshift(entry);
  store.set('studio.library', lib.slice(0, 50));
  renderLibrary();
  toast(`Saved “${state.scene.title}”`);
};
$('library').addEventListener('click', (e) => {
  const a = e.target.dataset.a, li = e.target.closest('li'); if (!a || !li) return;
  const lib = store.get('studio.library', []), i = Number(li.dataset.i);
  if (a === 'open') { pause(); setScene(lib[i].scene); toast(`Opened “${lib[i].scene.title}”`); }
  if (a === 'del' && confirm(`Delete “${lib[i].scene.title}”?`)) { lib.splice(i, 1); store.set('studio.library', lib); renderLibrary(); }
});
$('loadDemo').onclick = () => { pause(); setScene(DEMO_SCENE); };
$('exportJson').onclick = async () => {
  const name = `${state.scene.title.replace(/[^\w -]/g, '').trim() || 'animation'}.json`;
  const where = await saveBlob(new Blob([JSON.stringify(state.scene, null, 2)], { type: 'application/json' }), name);
  toast(where ? `Saved to ${where}` : 'Saved');
};
$('importJson').onchange = async (e) => {
  const file = e.target.files[0]; e.target.value = '';
  if (!file) return;
  try { pause(); setScene(JSON.parse(await file.text())); toast(`Imported “${state.scene.title}”`); }
  catch (err) { toast(`Not a valid animation file: ${err.message}`); }
};

// ---------- video export ----------
function pickMime() {
  const types = ['video/mp4;codecs=avc1.42E01E,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
  return types.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || '';
}
$('exportVideo').onclick = async () => {
  if (state.exporting) return;
  if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) { toast('Video recording is not supported on this device.'); return; }
  pause();
  state.exporting = true;
  const btn = $('exportVideo'), prog = $('exportProgress');
  btn.disabled = true; prog.hidden = false; prog.value = 0;
  const scene = state.scene;
  const off = document.createElement('canvas'); off.width = 1280; off.height = 720;
  const octx = off.getContext('2d');
  drawFrame(octx, scene, 0);
  audio.ensure();
  const stream = off.captureStream(30);
  audio.recordDest?.stream.getAudioTracks().forEach((t) => stream.addTrack(t));
  const mime = pickMime();
  const chunks = [];
  try {
    const rec = new MediaRecorder(stream, { mimeType: mime || undefined, videoBitsPerSecond: 6_000_000, audioBitsPerSecond: 160_000 });
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    const done = new Promise((r) => (rec.onstop = r));
    $('exportInfo').textContent = 'Recording… keep the app open until it finishes.';
    rec.start(500);
    audio.play(scene, 0);
    await new Promise((resolve) => {
      const step = () => {
        const t = Math.min(scene.duration, audio.position() ?? 0);
        drawFrame(octx, scene, t); state.t = t; draw(); prog.value = t / scene.duration;
        if (t >= scene.duration) resolve(); else requestAnimationFrame(step);
      };
      step();
    });
    await new Promise((r) => setTimeout(r, 300));
    rec.stop(); audio.stop();
    await done;
    const type = (mime || chunks[0]?.type || 'video/webm').split(';')[0];
    const blob = new Blob(chunks, { type });
    const name = `${scene.title.replace(/[^\w -]/g, '').trim() || 'animation'}.${type.includes('mp4') ? 'mp4' : 'webm'}`;
    $('exportInfo').textContent = 'Saving…';
    const where = await saveBlob(blob, name);
    $('exportInfo').textContent = `Saved ${name} (${(blob.size / 1e6).toFixed(1)} MB)${where ? ` to ${where}` : ''}.`;
    toast('Video exported');
  } catch (err) {
    $('exportInfo').textContent = `Export failed: ${err.message || err}`;
  } finally {
    audio.stop();
    stream.getTracks().forEach((t) => t.kind === 'video' && t.stop());
    state.exporting = false; btn.disabled = false; prog.hidden = true;
  }
};

// ---------- start ----------
async function boot() {
  try {
    for (const { name, data } of await listSounds()) {
      try { await audio.addCustom(name, data); state.customNames.push(name); } catch { /* undecodable file */ }
    }
  } catch { /* IndexedDB unavailable */ }
  setScene(store.get('studio.current', null) || DEMO_SCENE);
  updateProviderHint();
  $('concept').value = store.get('studio.concept', '');
  $('concept').oninput = (e) => store.set('studio.concept', e.target.value);
}
// AudioContext needs a user gesture on some devices; unlock it on the first tap.
document.addEventListener('pointerdown', () => audio.ensure(), { once: true });
window.studio = { state, setScene };
boot();
