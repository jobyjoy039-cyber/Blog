// App shell: wires the UI, playback loop, joint dragging, sound editing, AI generation and export.
import { normalizeScene, figureStateAt, upsertKeyframe, resolvePose, POSE_NAMES, SOUND_NAMES, MUSIC_MOODS, SCENERY, FIGURE_HEIGHT } from './scene.js';
import { renderScene } from './renderer.js';
import { AudioEngine } from './audio.js';
import { generateScene, DEFAULT_MODELS } from './ai.js';
import { demoScene } from './demo.js';
import { recordVideo, saveBlob, safeName } from './exporter.js';

const $ = (id) => document.getElementById(id);
const canvas = $('canvas');
const ctx = canvas.getContext('2d');
const audio = new AudioEngine();

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage full or blocked */ } },
};

const state = {
  scene: normalizeScene(store.get('stickai.scene', null) || demoScene()),
  t: 0,
  playing: false,
  playFrom: 0,
  playStart: 0,
  onDone: null,
  selected: 0,
  drag: null,
  skels: {},
  busy: false,
};
const settings = Object.assign({ provider: 'claude', claudeKey: '', openaiKey: '', claudeModel: DEFAULT_MODELS.claude, openaiModel: DEFAULT_MODELS.openai }, store.get('stickai.settings', {}));

function toast(msg, ms = 2600) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add('hidden'), ms);
}

let saveTimer;
function changed({ ui = true } = {}) {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => store.set('stickai.scene', state.scene), 400);
  if (ui) refreshUI();
  draw();
}

// ---------- Rendering & playback ----------
function sizeCanvas() {
  const [w, h] = state.scene.aspect === '9:16' ? [720, 1280] : [1280, 720];
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
}

function draw() {
  sizeCanvas();
  const editing = !state.playing && currentTab === 'edit';
  state.skels = renderScene(ctx, state.scene, state.t, {
    joints: editing && $('showJoints').checked,
    selected: state.selected,
    onion: editing && $('onion').checked ? state.selected : null,
  });
  $('scrub').value = state.t;
  $('time').textContent = `${state.t.toFixed(1)} / ${state.scene.duration.toFixed(1)}s`;
}

function now() {
  return audio.ctx ? audio.ctx.currentTime : performance.now() / 1000;
}

function frame() {
  if (!state.playing) return;
  const t = state.playFrom + (now() - state.playStart);
  if (t >= state.scene.duration) {
    state.t = state.scene.duration;
    stop();
    const done = state.onDone;
    state.onDone = null;
    done?.();
    return;
  }
  state.t = Math.max(0, t);
  draw();
  requestAnimationFrame(frame);
}

function play(fromStart = false, onDone = null) {
  if (state.t >= state.scene.duration - 0.05 || fromStart) state.t = 0;
  state.playFrom = state.t;
  try {
    state.playStart = audio.play(state.scene, state.t);
  } catch (e) {
    console.warn('Audio unavailable', e);
    state.playStart = now();
  }
  state.playing = true;
  state.onDone = onDone;
  $('btnPlay').textContent = '❚❚';
  requestAnimationFrame(frame);
}

function stop() {
  state.playing = false;
  audio.stop();
  $('btnPlay').textContent = '▶';
  draw();
}

$('btnPlay').onclick = () => (state.playing ? stop() : play());
$('scrub').oninput = (e) => {
  if (state.playing) stop();
  state.t = +e.target.value;
  draw();
  refreshKeyInfo();
};

// ---------- Tabs ----------
let currentTab = 'create';
document.querySelectorAll('.tab').forEach((b) => {
  b.onclick = () => {
    currentTab = b.dataset.tab;
    document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('active', x === b));
    document.querySelectorAll('.panel').forEach((p) => p.classList.toggle('hidden', p.id !== `panel-${currentTab}`));
    draw();
  };
});

// ---------- UI refresh ----------
function fillSelect(sel, items, value) {
  sel.innerHTML = '';
  for (const it of items) {
    const [v, label] = Array.isArray(it) ? it : [it, it];
    const o = document.createElement('option');
    o.value = v;
    o.textContent = label;
    sel.appendChild(o);
  }
  if (value != null) sel.value = value;
}

function soundLabel(s) {
  return s.startsWith('custom:') ? `🎵 ${s.slice(7)}` : s;
}

function refreshUI() {
  const s = state.scene;
  $('sceneTitle').textContent = s.title;
  $('scrub').max = s.duration;
  if (state.selected >= s.figures.length) state.selected = s.figures.length - 1;
  fillSelect($('figSelect'), s.figures.map((f, i) => [i, f.name]), state.selected);
  const fig = s.figures[state.selected];
  $('figName').value = fig ? fig.name : '';
  $('figColor').value = fig ? fig.color.length === 4 ? `#${[...fig.color.slice(1)].map((c) => c + c).join('')}` : fig.color : '#000000';
  $('duration').value = s.duration;
  $('scenery').value = s.background.scenery;
  $('sky').value = expandHex(s.background.sky);
  $('ground').value = expandHex(s.background.ground);
  $('aspect').value = s.aspect;
  $('sfxVol').value = s.sfxVolume;
  $('musicVol').value = s.music.volume;
  $('bpm').value = s.music.bpm;
  const { custom, music } = audio.list();
  fillSelect($('sfxSelect'), [...SOUND_NAMES, ...custom].map((n) => [n, soundLabel(n)]), $('sfxSelect').value || 'punch');
  fillSelect($('musicSource'), [
    ...MUSIC_MOODS.filter((m) => m !== 'none').map((m) => [`mood:${m}`, `♪ Generated: ${m}`]),
    ...music.map((k) => [k, `🎵 ${k.slice(6)}`]),
    ['mood:none', 'No music'],
  ], s.music.file && audio.buffers.has(s.music.file) ? s.music.file : `mood:${s.music.mood}`);
  renderSfxList();
  renderTicks();
  refreshKeyInfo();
}

function expandHex(c) {
  return c.length === 4 ? `#${[...c.slice(1)].map((x) => x + x).join('')}` : c;
}

function renderTicks() {
  const el = $('ticks');
  el.innerHTML = '';
  const d = state.scene.duration;
  const fig = state.scene.figures[state.selected];
  for (const k of fig ? fig.keyframes : []) {
    const sp = document.createElement('span');
    sp.style.left = `${(k.t / d) * 100}%`;
    sp.title = `Keyframe ${k.t.toFixed(2)}s`;
    sp.onclick = () => { stop(); state.t = k.t; draw(); refreshKeyInfo(); };
    el.appendChild(sp);
  }
  for (const e of state.scene.sfx) {
    const sp = document.createElement('span');
    sp.className = 'sfx';
    sp.style.left = `${(e.t / d) * 100}%`;
    el.appendChild(sp);
  }
}

function keyAtPlayhead(fig) {
  return fig && fig.keyframes.find((k) => Math.abs(k.t - state.t) < 1 / 60);
}

function refreshKeyInfo() {
  const fig = state.scene.figures[state.selected];
  const k = keyAtPlayhead(fig);
  const st = fig ? figureStateAt(fig, state.t) : null;
  $('btnDelKey').disabled = !k;
  if (st) {
    $('exprSelect').value = st.expr || 'neutral';
    $('sayText').value = k ? k.say : '';
  }
}

function renderSfxList() {
  const ul = $('sfxList');
  ul.innerHTML = '';
  if (!state.scene.sfx.length) {
    const li = document.createElement('li');
    li.className = 'empty';
    li.textContent = 'No sound effects yet';
    ul.appendChild(li);
    return;
  }
  state.scene.sfx.forEach((e, i) => {
    const li = document.createElement('li');
    const t = document.createElement('input');
    t.type = 'number'; t.step = '0.05'; t.min = '0'; t.max = String(state.scene.duration); t.value = e.t.toFixed(2);
    t.setAttribute('aria-label', 'Time in seconds');
    t.onchange = () => { e.t = Math.max(0, Math.min(state.scene.duration, +t.value || 0)); state.scene.sfx.sort((a, b) => a.t - b.t); changed(); };
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = soundLabel(e.sound);
    const go = document.createElement('button');
    go.textContent = '▶';
    go.setAttribute('aria-label', 'Preview');
    go.onclick = () => audio.preview(e.sound);
    const del = document.createElement('button');
    del.textContent = '✕';
    del.className = 'danger';
    del.setAttribute('aria-label', 'Remove');
    del.onclick = () => { state.scene.sfx.splice(i, 1); changed(); };
    li.append(t, name, go, del);
    ul.appendChild(li);
  });
}

// ---------- Create (AI) ----------
function setBusy(on, text = 'Animating…') {
  state.busy = on;
  $('busy').classList.toggle('hidden', !on);
  $('busyText').textContent = text;
  for (const id of ['btnGenerate', 'btnRefine', 'btnVideo']) $(id).disabled = on;
}

async function runAI(concept, current) {
  const provider = $('provider').value;
  settings.provider = provider;
  store.set('stickai.settings', settings);
  const apiKey = provider === 'openai' ? settings.openaiKey : settings.claudeKey;
  if (!apiKey) {
    toast(`Add your ${provider === 'openai' ? 'OpenAI' : 'Anthropic'} API key first.`);
    $('settings').showModal();
    return;
  }
  stop();
  const name = provider === 'openai' ? 'OpenAI' : 'Claude';
  setBusy(true, `${name} is directing your animation…`);
  $('aiStatus').textContent = '';
  try {
    const scene = await generateScene({
      provider,
      apiKey,
      model: provider === 'openai' ? settings.openaiModel : settings.claudeModel,
      concept,
      current,
      aspect: $('aspect').value,
      customSounds: audio.list().custom,
      onProgress: (n) => { $('busyText').textContent = `${name} is directing your animation… (${Math.round(n / 100) / 10}k chars)`; },
    });
    if (current?.music?.file) scene.music.file = current.music.file;
    state.scene = scene;
    state.t = 0;
    state.selected = 0;
    changed();
    $('aiStatus').textContent = `“${scene.title}” · ${scene.figures.length} figure(s), ${scene.sfx.length} sound effects, ${scene.music.mood} music.`;
    play(true);
  } catch (e) {
    console.error(e);
    $('aiStatus').textContent = `⚠ ${e.message}`;
    toast(e.message, 5000);
  } finally {
    setBusy(false);
  }
}

$('btnGenerate').onclick = () => {
  const c = $('concept').value.trim();
  if (!c) { toast('Describe your animation idea first.'); $('concept').focus(); return; }
  runAI(c, null);
};
$('btnRefine').onclick = () => {
  const c = $('refine').value.trim();
  if (!c) { toast('Describe what to change.'); return; }
  runAI(c, state.scene);
};
$('btnDemo').onclick = () => { stop(); state.scene = demoScene(); state.t = 0; changed(); play(true); };
$('btnBlank').onclick = () => {
  stop();
  state.scene = normalizeScene({ title: 'Untitled', duration: 6, aspect: $('aspect').value, figures: [{ name: 'Stick', keyframes: [{ t: 0, x: 0.5, pose: 'stand' }] }] });
  state.t = 0;
  state.selected = 0;
  changed();
};
$('aspect').onchange = () => { state.scene.aspect = $('aspect').value; changed(); };

// ---------- Settings ----------
$('btnSettings').onclick = () => {
  $('claudeKey').value = settings.claudeKey;
  $('openaiKey').value = settings.openaiKey;
  $('claudeModel').value = settings.claudeModel;
  $('openaiModel').value = settings.openaiModel;
  $('settings').showModal();
};
$('btnSaveSettings').onclick = () => {
  settings.claudeKey = $('claudeKey').value.trim();
  settings.openaiKey = $('openaiKey').value.trim();
  settings.claudeModel = $('claudeModel').value.trim() || DEFAULT_MODELS.claude;
  settings.openaiModel = $('openaiModel').value.trim() || DEFAULT_MODELS.openai;
  store.set('stickai.settings', settings);
  toast('Settings saved');
};

// ---------- Edit ----------
const selFig = () => state.scene.figures[state.selected];
$('figSelect').onchange = () => { state.selected = +$('figSelect').value; refreshUI(); draw(); };
$('figName').onchange = () => { if (selFig()) { selFig().name = $('figName').value.slice(0, 40) || 'Figure'; changed(); } };
$('figColor').oninput = () => { if (selFig()) { selFig().color = $('figColor').value; changed({ ui: false }); } };
$('btnAddFig').onclick = () => {
  const n = state.scene.figures.length + 1;
  const raw = JSON.parse(JSON.stringify(state.scene));
  raw.figures.push({ id: `fig${Date.now() % 100000}`, name: `Figure ${n}`, keyframes: [{ t: state.t, x: 0.3 + Math.random() * 0.4, pose: 'stand' }] });
  state.scene = normalizeScene(raw);
  state.selected = state.scene.figures.length - 1;
  changed();
};
$('btnDelFig').onclick = () => {
  if (!selFig()) return;
  if (!confirm(`Delete ${selFig().name}?`)) return;
  state.scene.figures.splice(state.selected, 1);
  state.selected = Math.max(0, state.selected - 1);
  changed();
};
fillSelect($('poseSelect'), POSE_NAMES);
fillSelect($('scenery'), SCENERY);
$('btnApplyPose').onclick = () => {
  if (!selFig()) return;
  upsertKeyframe(selFig(), state.t, { pose: resolvePose($('poseSelect').value) });
  changed();
};
$('exprSelect').onchange = () => { if (selFig()) { upsertKeyframe(selFig(), state.t, { expr: $('exprSelect').value }); changed(); } };
$('btnFlip').onclick = () => {
  if (!selFig()) return;
  const st = figureStateAt(selFig(), state.t);
  upsertKeyframe(selFig(), state.t, { facing: -st.facing });
  changed();
};
$('btnSay').onclick = () => { if (selFig()) { upsertKeyframe(selFig(), state.t, { say: $('sayText').value.slice(0, 80) }); changed(); } };
$('btnPrevKey').onclick = () => {
  const k = selFig() && [...selFig().keyframes].reverse().find((x) => x.t < state.t - 1e-3);
  if (k) { stop(); state.t = k.t; draw(); refreshKeyInfo(); }
};
$('btnNextKey').onclick = () => {
  const k = selFig() && selFig().keyframes.find((x) => x.t > state.t + 1e-3);
  if (k) { stop(); state.t = k.t; draw(); refreshKeyInfo(); }
};
$('btnDelKey').onclick = () => {
  const fig = selFig();
  const k = keyAtPlayhead(fig);
  if (!k || fig.keyframes.length < 2) { toast('A figure needs at least one keyframe.'); return; }
  fig.keyframes.splice(fig.keyframes.indexOf(k), 1);
  changed();
};
$('onion').onchange = draw;
$('showJoints').onchange = draw;
$('duration').onchange = () => {
  const d = Math.max(1, Math.min(60, +$('duration').value || 6));
  const raw = JSON.parse(JSON.stringify(state.scene));
  raw.duration = d;
  state.scene = normalizeScene(raw);
  state.t = Math.min(state.t, d);
  changed();
};
$('scenery').onchange = () => { state.scene.background.scenery = $('scenery').value; changed({ ui: false }); };
$('sky').oninput = () => { state.scene.background.sky = $('sky').value; changed({ ui: false }); };
$('ground').oninput = () => { state.scene.background.ground = $('ground').value; changed({ ui: false }); };

// Joint dragging on the stage.
const deg = (r) => (r * 180) / Math.PI;
const wrap = (a) => ((a + 540) % 360) - 180;
const near = (prev, next) => prev + wrap(next - prev);
// Angle of the vector from a to b, measured from straight down, positive toward the figure's front.
const downAngle = (a, b, facing) => deg(Math.atan2((b[0] - a[0]) * facing, b[1] - a[1]));

function canvasPoint(ev) {
  const r = canvas.getBoundingClientRect();
  // The canvas keeps its aspect ratio inside the element box (object-fit: contain).
  const scale = Math.min(r.width / canvas.width, r.height / canvas.height);
  const ox = (r.width - canvas.width * scale) / 2, oy = (r.height - canvas.height * scale) / 2;
  return [(ev.clientX - r.left - ox) / scale, (ev.clientY - r.top - oy) / scale];
}

const DRAGGABLE = ['head', 'hip', 'lElbow', 'lHand', 'rElbow', 'rHand', 'lKnee', 'lFoot', 'rKnee', 'rFoot'];
canvas.addEventListener('pointerdown', (ev) => {
  if (currentTab !== 'edit' || state.playing) return;
  const p = canvasPoint(ev);
  let best = null;
  state.scene.figures.forEach((fig, i) => {
    const sk = state.skels[fig.id];
    if (!sk) return;
    for (const j of DRAGGABLE) {
      const d = Math.hypot(sk[j][0] - p[0], sk[j][1] - p[1]);
      // Prefer the selected figure when joints overlap.
      const score = d - (i === state.selected ? 12 : 0);
      if (d < 36 && (!best || score < best.score)) best = { i, j, score };
    }
  });
  if (!best) return;
  if (best.i !== state.selected) { state.selected = best.i; refreshUI(); }
  const fig = selFig();
  const st = figureStateAt(fig, state.t);
  state.drag = { joint: best.j, start: p, startState: st };
  canvas.setPointerCapture(ev.pointerId);
  ev.preventDefault();
});

canvas.addEventListener('pointermove', (ev) => {
  const drag = state.drag;
  if (!drag) return;
  const fig = selFig();
  const p = canvasPoint(ev);
  const st = drag.startState;
  const sk = state.skels[fig.id];
  const f = st.facing;
  const pose = { ...figureStateAt(fig, state.t).pose };
  const patch = {};
  // Converts world angles into the figure's own frame when it is rotated (flips, falls).
  const rot = st.rot;
  const j = drag.joint;
  if (j === 'hip') {
    patch.x = Math.max(-0.2, Math.min(1.2, st.x + (p[0] - drag.start[0]) / canvas.width));
    patch.lift = Math.max(0, st.lift + (drag.start[1] - p[1]) / (FIGURE_HEIGHT * sk.unit));
  } else if (j === 'head') {
    pose.torso = near(pose.torso, 180 - downAngle(sk.hip, p, f) - rot);
  } else {
    const side = j[0];
    if (j.endsWith('Elbow')) {
      const world = downAngle(sk.shoulder, p, f) + rot;
      pose[`${side}Shoulder`] = near(pose[`${side}Shoulder`], world + pose.torso);
    } else if (j.endsWith('Hand')) {
      const arm = downAngle(sk.shoulder, sk[`${side}Elbow`], f);
      pose[`${side}Elbow`] = near(pose[`${side}Elbow`], downAngle(sk[`${side}Elbow`], p, f) - arm);
    } else if (j.endsWith('Knee')) {
      pose[`${side}Hip`] = near(pose[`${side}Hip`], downAngle(sk.hip, p, f) + rot);
    } else if (j.endsWith('Foot')) {
      const leg = downAngle(sk.hip, sk[`${side}Knee`], f);
      pose[`${side}Knee`] = near(pose[`${side}Knee`], leg - downAngle(sk[`${side}Knee`], p, f));
    }
  }
  patch.pose = pose;
  upsertKeyframe(fig, state.t, patch);
  draw();
});

const endDrag = () => {
  if (!state.drag) return;
  state.drag = null;
  changed();
};
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);

// ---------- Sound ----------
$('btnPreviewSfx').onclick = () => audio.preview($('sfxSelect').value);
$('btnAddSfx').onclick = () => {
  state.scene.sfx.push({ t: state.t, sound: $('sfxSelect').value, volume: 1 });
  state.scene.sfx.sort((a, b) => a.t - b.t);
  audio.preview($('sfxSelect').value);
  changed();
};
$('sfxVol').oninput = () => { state.scene.sfxVolume = +$('sfxVol').value; changed({ ui: false }); };
$('musicVol').oninput = () => { state.scene.music.volume = +$('musicVol').value; changed({ ui: false }); };
$('bpm').onchange = () => { state.scene.music.bpm = Math.max(50, Math.min(200, Math.round(+$('bpm').value || 110))); changed(); };
$('musicSource').onchange = () => {
  const v = $('musicSource').value;
  if (v.startsWith('mood:')) { state.scene.music.mood = v.slice(5); state.scene.music.file = null; }
  else state.scene.music.file = v;
  changed();
};
$('sfxFile').onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  try {
    const key = await audio.importFile(file, 'custom');
    refreshUI();
    $('sfxSelect').value = key;
    toast(`Imported ${file.name}`);
  } catch (err) {
    toast(`Could not read that audio file (${err.message})`, 4000);
  }
};
$('musicFile').onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  try {
    const key = await audio.importFile(file, 'music');
    state.scene.music.file = key;
    changed();
    toast(`Music set to ${file.name}`);
  } catch (err) {
    toast(`Could not read that audio file (${err.message})`, 4000);
  }
};

// ---------- Export ----------
$('btnVideo').onclick = async () => {
  stop();
  setBusy(true, 'Recording video… 0%');
  try {
    const blob = await recordVideo({
      canvas,
      audio,
      duration: state.scene.duration,
      play: (done) => play(true, done),
      onProgress: (p) => { $('busyText').textContent = `Recording video… ${Math.round(p * 100)}%`; },
    });
    const ext = blob.type.includes('mp4') ? 'mp4' : 'webm';
    const where = await saveBlob(blob, `${safeName(state.scene.title)}.${ext}`);
    $('exportStatus').textContent = `Saved ${(blob.size / 1e6).toFixed(1)} MB video (${ext}) → ${where}`;
  } catch (e) {
    console.error(e);
    toast(e.message, 5000);
    $('exportStatus').textContent = `⚠ ${e.message}`;
  } finally {
    setBusy(false);
  }
};
$('btnSaveProject').onclick = async () => {
  const blob = new Blob([JSON.stringify(state.scene, null, 2)], { type: 'application/json' });
  try { await saveBlob(blob, `${safeName(state.scene.title)}.stick.json`); } catch (e) { toast(e.message, 4000); }
};
$('projectFile').onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  try {
    stop();
    state.scene = normalizeScene(JSON.parse(await file.text()));
    state.t = 0;
    state.selected = 0;
    changed();
    toast(`Opened ${state.scene.title}`);
  } catch {
    toast('That file is not a valid project.', 4000);
  }
};
$('btnCopyJson').onclick = async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(state.scene));
    toast('Scene JSON copied');
  } catch {
    toast('Clipboard is not available here.');
  }
};

// ---------- Boot ----------
$('provider').value = settings.provider;
refreshUI();
draw();
audio.loadSaved().then(refreshUI);
// Browsers only allow audio after a user gesture; unlock it on the first touch.
window.addEventListener('pointerdown', () => audio.ensure(), { once: true });

// Exposed for automated tests.
window.__stickai = { state, audio, draw, normalizeScene };
