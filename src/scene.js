// Scene model: normalizing AI/user scenes, pose presets and keyframe interpolation.

// Joint angles in degrees. Convention (for a figure facing right, facing = 1):
//   torso    lean of the spine from vertical, positive = leaning forward
//   head     head tilt relative to the spine
//   lShoulder/rShoulder  upper arm angle from hanging straight down, relative to the spine,
//                        positive = swung forward (90 = pointing straight ahead, 180 = straight up)
//   lElbow/rElbow        forearm bend relative to the upper arm, positive = bends forward/up
//   lHip/rHip            thigh angle from straight down, positive = forward
//   lKnee/rKnee          shin bend relative to the thigh, positive = bends backward (natural knee)
export const JOINTS = [
  'torso', 'head',
  'lShoulder', 'lElbow', 'rShoulder', 'rElbow',
  'lHip', 'lKnee', 'rHip', 'rKnee',
];

const P = (torso, head, lS, lE, rS, rE, lH, lK, rH, rK) => ({
  torso, head, lShoulder: lS, lElbow: lE, rShoulder: rS, rElbow: rE,
  lHip: lH, lKnee: lK, rHip: rH, rKnee: rK,
});

export const POSES = {
  stand:     P(0, 0, -8, 10, 8, 10, -4, 2, 4, 2),
  idle:      P(2, 4, -12, 20, 12, 20, -6, 4, 6, 4),
  walk1:     P(4, 0, -30, 20, 30, 20, 25, 10, -20, 25),
  walk2:     P(4, 0, 30, 20, -30, 20, -20, 25, 25, 10),
  run1:      P(15, 0, -50, 90, 60, 90, 55, 40, -35, 90),
  run2:      P(15, 0, 60, 90, -50, 90, -35, 90, 55, 40),
  jump:      P(5, -5, 150, 10, 160, 10, 30, 60, 10, 40),
  crouch:    P(25, -10, 40, 60, 30, 60, 80, 130, 70, 120),
  land:      P(20, 5, 50, 30, 40, 30, 60, 100, 50, 90),
  punch:     P(15, 0, 40, 120, 90, 0, 30, 20, -25, 15),
  punch2:    P(15, 0, 90, 0, 40, 120, 30, 20, -25, 15),
  kick:      P(-15, 0, 60, 40, -40, 30, 95, 0, -15, 10),
  block:     P(-5, -5, 70, 130, 80, 130, 10, 20, -15, 20),
  wave:      P(0, 10, -8, 10, 160, 40, -4, 2, 4, 2),
  cheer:     P(-5, -15, 165, 15, 165, 15, -8, 4, 8, 4),
  point:     P(0, 0, -8, 10, 90, 0, -4, 2, 4, 2),
  think:     P(0, 15, -10, 10, 30, 150, -4, 2, 4, 2),
  sit:       P(-5, 0, 20, 30, 25, 30, 90, 90, 85, 90),
  fall:      P(-35, -20, 120, 20, 150, 30, 40, 20, 70, 30),
  hurt:      P(-25, -20, 40, 60, 60, 60, 20, 30, -10, 20),
  lie:       P(-90, 0, 170, 0, 160, 10, 0, 0, 10, 5),
  dance1:    P(-8, 10, 140, 60, 30, 100, 40, 60, -10, 5),
  dance2:    P(8, -10, 30, 100, 140, 60, -10, 5, 40, 60),
  bow:       P(60, 20, -20, 10, 30, 30, -10, 5, 0, 5),
  throw:     P(-15, 0, 30, 40, 170, 60, 20, 10, -25, 15),
  hands_on_hips: P(0, 0, -40, -110, 40, -110, -6, 2, 6, 2),
  shrug:     P(0, 10, -30, 130, 30, 130, -4, 2, 4, 2),
  celebrate: P(-5, -15, 165, 15, 165, 15, 50, 90, -10, 30),
};

export const POSE_NAMES = Object.keys(POSES);

// Skeleton segment lengths in figure units. A standing figure is ~118 units tall.
export const BONES = { torso: 40, neck: 6, head: 11, upperArm: 23, forearm: 22, thigh: 28, shin: 28 };
export const FIGURE_HEIGHT = BONES.thigh + BONES.shin + BONES.torso + BONES.neck + BONES.head * 2;

export const SOUND_NAMES = [
  'punch', 'kick', 'whoosh', 'jump', 'land', 'step', 'explosion', 'pop', 'ding', 'boing',
  'laser', 'crash', 'coin', 'splat', 'clang', 'zap', 'drumroll', 'tada', 'scream', 'laugh',
];
export const MUSIC_MOODS = ['epic', 'happy', 'tense', 'calm', 'silly', 'sad', 'action', 'none'];
export const SCENERY = ['none', 'city', 'forest', 'hills', 'night', 'beach', 'room', 'arena', 'space'];
export const EFFECTS = ['impact', 'burst', 'speedlines', 'text', 'dust', 'stars', 'hearts', 'flash', 'shake'];
export const PROPS = ['ball', 'box', 'sword', 'star', 'heart', 'rock', 'flag', 'bat'];

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const num = (v, d) => (typeof v === 'number' && isFinite(v) ? v : (typeof v === 'string' && v.trim() !== '' && isFinite(+v) ? +v : d));
const color = (v, d) => (typeof v === 'string' && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v.trim()) ? v.trim() : d);
const pick = (v, list, d) => (typeof v === 'string' && list.includes(v.toLowerCase()) ? v.toLowerCase() : d);
const str = (v, d = '', max = 140) => (typeof v === 'string' ? v.slice(0, max) : d);

const FIGURE_COLORS = ['#1d1d1f', '#d7263d', '#1b6ca8', '#2a9d3c', '#8e44ad', '#e67e22'];

// Resolves a keyframe pose (preset name, object with preset + overrides, or raw angles) to angles.
export function resolvePose(pose) {
  if (typeof pose === 'string') return { ...(POSES[pose.toLowerCase()] || POSES.stand) };
  if (pose && typeof pose === 'object') {
    const base = { ...(POSES[String(pose.preset || '').toLowerCase()] || POSES.stand) };
    for (const j of JOINTS) base[j] = clamp(num(pose[j], base[j]), -360, 360);
    return base;
  }
  return { ...POSES.stand };
}

function normKeyframes(list, duration, mapper) {
  const out = (Array.isArray(list) ? list : [])
    .map(mapper)
    .filter(Boolean)
    .map((k) => ({ ...k, t: clamp(k.t, 0, duration) }))
    .sort((a, b) => a.t - b.t);
  return out;
}

// Turns any loosely-shaped scene (from an AI model, a saved file or the editor) into a safe, complete scene.
export function normalizeScene(raw) {
  const s = raw && typeof raw === 'object' ? raw : {};
  const duration = clamp(num(s.duration, 6), 1, 60);
  const bg = s.background && typeof s.background === 'object' ? s.background : {};
  const scene = {
    title: str(s.title, 'Untitled', 80),
    concept: str(s.concept, '', 2000),
    duration,
    aspect: s.aspect === '9:16' ? '9:16' : '16:9',
    background: {
      sky: color(bg.sky, '#f4f1ea'),
      ground: color(bg.ground, '#d9d2c3'),
      groundY: clamp(num(bg.groundY, 0.82), 0.5, 0.97),
      scenery: pick(bg.scenery, SCENERY, 'none'),
    },
    figures: [],
    props: [],
    effects: [],
    captions: [],
    sfx: [],
    music: { mood: 'happy', bpm: 110, volume: 0.5, file: null },
    sfxVolume: clamp(num(s.sfxVolume, 0.9), 0, 1),
  };

  const figs = Array.isArray(s.figures) ? s.figures.slice(0, 8) : [];
  figs.forEach((f, i) => {
    if (!f || typeof f !== 'object') return;
    const keyframes = normKeyframes(f.keyframes, duration, (k) => {
      if (!k || typeof k !== 'object') return null;
      return {
        t: num(k.t, 0),
        x: clamp(num(k.x, 0.5), -0.3, 1.3),
        lift: clamp(num(k.lift, 0), -1, 4),
        facing: num(k.facing, 1) < 0 ? -1 : 1,
        rot: clamp(num(k.rot, 0), -720, 720),
        pose: resolvePose(k.pose),
        ease: pick(k.ease, ['linear', 'ease', 'in', 'out', 'step'], 'ease'),
        say: str(k.say, '', 80),
        expr: pick(k.expr, ['neutral', 'happy', 'sad', 'angry', 'surprised', 'hurt'], ''),
      };
    });
    if (!keyframes.length) keyframes.push({ t: 0, x: 0.2 + 0.6 * (i / Math.max(1, figs.length - 1 || 1)), lift: 0, facing: 1, rot: 0, pose: resolvePose('stand'), ease: 'ease', say: '', expr: '' });
    scene.figures.push({
      id: str(f.id, `fig${i + 1}`, 40) || `fig${i + 1}`,
      name: str(f.name, `Figure ${i + 1}`, 40),
      color: color(f.color, FIGURE_COLORS[i % FIGURE_COLORS.length]),
      scale: clamp(num(f.scale, 1), 0.3, 3),
      lineWidth: clamp(num(f.lineWidth, 6), 2, 14),
      headFill: f.headFill === true,
      keyframes,
    });
  });

  const props = Array.isArray(s.props) ? s.props.slice(0, 16) : [];
  props.forEach((p, i) => {
    if (!p || typeof p !== 'object') return;
    const keyframes = normKeyframes(p.keyframes, duration, (k) => k && typeof k === 'object' ? ({
      t: num(k.t, 0),
      x: clamp(num(k.x, 0.5), -0.3, 1.3),
      lift: clamp(num(k.lift, 0), -1, 6),
      rot: clamp(num(k.rot, 0), -3600, 3600),
      holder: str(k.holder, '', 40),
      hand: k.hand === 'l' ? 'l' : 'r',
      visible: k.visible !== false,
      ease: pick(k.ease, ['linear', 'ease', 'in', 'out', 'step'], 'ease'),
    }) : null);
    if (!keyframes.length) return;
    scene.props.push({
      id: str(p.id, `prop${i + 1}`, 40),
      type: pick(p.type, PROPS, 'ball'),
      color: color(p.color, '#e63946'),
      size: clamp(num(p.size, 1), 0.2, 5),
      keyframes,
    });
  });

  (Array.isArray(s.effects) ? s.effects.slice(0, 80) : []).forEach((e) => {
    if (!e || typeof e !== 'object') return;
    scene.effects.push({
      t: clamp(num(e.t, 0), 0, duration),
      type: pick(e.type, EFFECTS, 'impact'),
      x: clamp(num(e.x, 0.5), 0, 1),
      lift: clamp(num(e.lift, 0.5), -1, 5),
      text: str(e.text, '', 24),
      color: color(e.color, '#ffbe0b'),
      dur: clamp(num(e.dur, 0.5), 0.1, 3),
    });
  });

  (Array.isArray(s.captions) ? s.captions.slice(0, 40) : []).forEach((c) => {
    if (!c || typeof c !== 'object' || typeof c.text !== 'string') return;
    const t = clamp(num(c.t, 0), 0, duration);
    scene.captions.push({ t, end: clamp(num(c.end, t + 2), t + 0.1, duration), text: str(c.text, '', 120) });
  });

  (Array.isArray(s.sfx) ? s.sfx.slice(0, 200) : []).forEach((e) => {
    if (!e || typeof e !== 'object') return;
    const sound = typeof e.sound === 'string' ? e.sound : '';
    if (!SOUND_NAMES.includes(sound) && !sound.startsWith('custom:')) return;
    scene.sfx.push({ t: clamp(num(e.t, 0), 0, duration), sound, volume: clamp(num(e.volume, 1), 0, 1) });
  });
  scene.sfx.sort((a, b) => a.t - b.t);

  const m = s.music && typeof s.music === 'object' ? s.music : {};
  scene.music = {
    mood: pick(m.mood, MUSIC_MOODS, 'happy'),
    bpm: clamp(Math.round(num(m.bpm, 110)), 50, 200),
    volume: clamp(num(m.volume, 0.45), 0, 1),
    file: typeof m.file === 'string' ? m.file.slice(0, 120) : null,
  };
  return scene;
}

function easeFn(kind, u) {
  switch (kind) {
    case 'linear': return u;
    case 'in': return u * u;
    case 'out': return 1 - (1 - u) * (1 - u);
    case 'step': return u < 1 ? 0 : 1;
    default: return u * u * (3 - 2 * u);
  }
}

const lerp = (a, b, u) => a + (b - a) * u;

// Returns the bracketing keyframes and the eased blend factor at time t.
export function bracket(keyframes, t) {
  if (t <= keyframes[0].t) return [keyframes[0], keyframes[0], 0];
  const last = keyframes[keyframes.length - 1];
  if (t >= last.t) return [last, last, 0];
  for (let i = 0; i < keyframes.length - 1; i++) {
    const a = keyframes[i], b = keyframes[i + 1];
    if (t >= a.t && t <= b.t) {
      const span = b.t - a.t || 1;
      return [a, b, easeFn(b.ease, (t - a.t) / span)];
    }
  }
  return [last, last, 0];
}

export function figureStateAt(fig, t) {
  const [a, b, u] = bracket(fig.keyframes, t);
  const pose = {};
  for (const j of JOINTS) pose[j] = lerp(a.pose[j], b.pose[j], u);
  // Speech and expression come from the latest keyframe at or before t; speech lasts until the next keyframe.
  let say = '', expr = 'neutral';
  for (const k of fig.keyframes) {
    if (k.t > t) break;
    if (k.say !== undefined) say = k.say;
    if (k.expr) expr = k.expr;
  }
  return {
    x: lerp(a.x, b.x, u),
    lift: lerp(a.lift, b.lift, u),
    rot: lerp(a.rot, b.rot, u),
    facing: u < 0.5 ? a.facing : b.facing,
    pose, say, expr,
  };
}

export function propStateAt(prop, t) {
  const [a, b, u] = bracket(prop.keyframes, t);
  const held = u < 0.5 ? a : b;
  return {
    x: lerp(a.x, b.x, u),
    lift: lerp(a.lift, b.lift, u),
    rot: lerp(a.rot, b.rot, u),
    holder: held.holder,
    hand: held.hand,
    visible: held.visible,
  };
}

// Inserts or replaces the keyframe at time t (within half a frame) and keeps the list sorted.
export function upsertKeyframe(fig, t, patch) {
  const near = fig.keyframes.find((k) => Math.abs(k.t - t) < 1 / 60);
  if (near) {
    Object.assign(near, patch);
    return near;
  }
  const s = figureStateAt(fig, t);
  const k = { t, x: s.x, lift: s.lift, rot: s.rot, facing: s.facing, pose: { ...s.pose }, ease: 'ease', say: '', expr: '', ...patch };
  fig.keyframes.push(k);
  fig.keyframes.sort((p, q) => p.t - q.t);
  return k;
}
