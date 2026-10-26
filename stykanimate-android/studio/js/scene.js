// Scene model: pose presets, vocabulary the AI may use, and normalization of
// whatever JSON comes back into a scene the renderer and audio engine can trust.

export const STAGE_W = 1280;
export const STAGE_H = 720;

/** Joint angles in degrees. "front" limbs are drawn on top, "back" limbs behind.
 * torso: lean forward (+) / back (-). head: nod down (+) / up (-).
 * shoulders (relative to the torso): 0 = arm along the body, 90 = straight forward, 180 = overhead.
 * elbows: bend forearm forward/up (+). hips: 0 = leg straight down, 90 = forward.
 * knees: bend shin backward (+). */
export const JOINTS = ['torso', 'head', 'backShoulder', 'backElbow', 'frontShoulder', 'frontElbow', 'backHip', 'backKnee', 'frontHip', 'frontKnee'];

const P = (torso, head, bS, bE, fS, fE, bH, bK, fH, fK) => ({ torso, head, backShoulder: bS, backElbow: bE, frontShoulder: fS, frontElbow: fE, backHip: bH, backKnee: bK, frontHip: fH, frontKnee: fK });

export const POSES = {
  stand: P(0, 0, -10, 10, 10, 10, -5, 0, 5, 0),
  idle: P(0, 0, -8, 15, 8, 15, -4, 2, 4, 2),
  walk1: P(3, 0, -25, 15, 25, 20, -20, 10, 25, 5),
  walk2: P(3, 0, 25, 20, -25, 15, 25, 5, -20, 10),
  run1: P(15, -5, -50, 80, 60, 90, -40, 70, 50, 30),
  run2: P(15, -5, 60, 90, -50, 80, 50, 30, -40, 70),
  jump: P(5, -10, 150, 10, 160, 10, 40, 90, 10, 60),
  crouch: P(30, -10, 40, 40, 50, 40, 80, 140, 90, 130),
  sit: P(0, 0, 20, 40, 25, 40, 90, 90, 85, 90),
  punch: P(15, -5, 70, 120, 105, 0, -20, 10, 25, 10),
  kick: P(-20, 5, -30, 30, 40, 60, -10, 5, 95, 0),
  wave: P(0, -5, -10, 10, 160, 30, -5, 0, 5, 0),
  cheer: P(-5, -15, 160, 10, 165, 10, -8, 0, 8, 0),
  fall: P(-40, -10, 120, 20, 140, 30, 30, 20, 60, 10),
  lie: P(-90, 0, 5, 0, 10, 0, 90, 0, 85, 5),
  think: P(0, 10, 10, 20, 30, 140, -5, 0, 5, 0),
  point: P(0, 0, -10, 10, 90, 0, -5, 0, 5, 0),
  block: P(-5, 5, 70, 110, 80, 120, -15, 10, 15, 10),
  dance1: P(10, -5, 130, -40, -40, 60, -25, 20, 35, 30),
  dance2: P(-10, 5, -40, 60, 130, -40, 30, 30, -25, 20),
  hurt: P(-25, -20, 40, 60, 60, 80, -10, 20, 20, 30),
  victory: P(0, -10, -20, 30, 170, 0, -8, 0, 8, 0),
  sad: P(15, 30, -5, 5, 5, 5, -3, 0, 3, 0),
  throw: P(10, -5, 60, 30, 130, 20, -20, 10, 25, 5),
  fly: P(80, -40, 170, 0, 175, 0, -10, 10, -5, 20),
  kneel: P(5, 0, 10, 20, 15, 20, 90, 90, 0, 90),
  bow: P(60, 20, 10, 10, 15, 10, -5, 0, 5, 0),
  shrug: P(0, 5, 40, 120, 40, 120, -5, 0, 5, 0),
  push: P(25, 0, 110, 10, 115, 5, -30, 10, 30, 20),
  climb: P(0, -20, 170, 20, 140, 60, 60, 100, 10, 30),
};

export const ACTIONS = ['none', 'walk', 'run', 'dance', 'idle'];
export const EASES = ['linear', 'in', 'out', 'inOut'];
export const SCENERY = ['none', 'city', 'forest', 'desert', 'space', 'room', 'beach', 'mountains', 'night', 'dojo', 'stage'];
export const PROP_TYPES = ['ball', 'box', 'rock', 'star', 'coin', 'tree', 'sign', 'car', 'chair', 'sword', 'cup', 'heart', 'bomb', 'door'];
export const EFFECTS = ['flash', 'explosion', 'dust', 'sparkle', 'impact', 'smoke', 'confetti', 'speedlines', 'rain', 'snow', 'lightning', 'fire'];
export const ACCESSORIES = ['none', 'hat', 'cape', 'headband', 'sword', 'crown', 'bow', 'glasses'];
export const SOUNDS = ['punch', 'kick', 'whoosh', 'swoosh', 'jump', 'land', 'footstep', 'explosion', 'laser', 'pop', 'ding', 'coin', 'magic', 'zap', 'crash', 'splash', 'boing', 'bell', 'cheer', 'alarm', 'heartbeat', 'thunder', 'wind', 'glass', 'click', 'drumroll', 'sadtrombone', 'slidewhistle', 'powerup', 'gameover', 'swordclash', 'gasp', 'tada'];
export const MOODS = ['none', 'epic', 'happy', 'tense', 'calm', 'funny', 'sad', 'action', 'spooky', 'heroic', 'chill'];

const num = (v, d, min = -Infinity, max = Infinity) => { const n = Number(v); return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : d; };
const str = (v, d) => (typeof v === 'string' && v.trim() ? v.trim() : d);
const color = (v, d) => (typeof v === 'string' && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v.trim()) ? v.trim() : d);
const pick = (v, list, d) => (list.includes(v) ? v : d);
const arr = (v) => (Array.isArray(v) ? v : []);

/** Pull the first JSON object out of a model reply (tolerates code fences and prose). */
export function extractJson(text) {
  if (typeof text !== 'string') throw new Error('The AI returned no text.');
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  const body = fenced ? fenced[1] : text;
  const start = body.indexOf('{'), end = body.lastIndexOf('}');
  if (start < 0 || end <= start) throw new Error('The AI reply did not contain a scene (no JSON object found).');
  return JSON.parse(body.slice(start, end + 1));
}

function normalizeJoints(j) {
  const out = {};
  if (j && typeof j === 'object') for (const k of JOINTS) if (Number.isFinite(Number(j[k]))) out[k] = num(j[k], 0, -360, 360);
  return out;
}

/** Make any scene-shaped object safe to play. Returns {scene, warnings}. */
export function normalizeScene(input, customSounds = []) {
  const warnings = [];
  const s = input && typeof input === 'object' ? input : {};
  const duration = num(s.duration, 10, 2, 120);
  const bg = s.background && typeof s.background === 'object' ? s.background : {};
  const sky = arr(bg.sky).map((c) => color(c, null)).filter(Boolean);
  const scene = {
    version: 1,
    title: str(s.title, 'Untitled animation'),
    duration,
    background: {
      sky: sky.length ? sky.slice(0, 3) : ['#8ecae6', '#e0f4ff'],
      ground: color(bg.ground, '#6a994e'),
      groundY: num(bg.groundY, 0.82, 0.3, 1),
      scenery: pick(bg.scenery, SCENERY, 'none'),
    },
    characters: [],
    tracks: [],
    props: [],
    camera: [],
    sfx: [],
    music: { mood: 'happy', bpm: 0, volume: 0.45, custom: '' },
    captions: [],
    speech: [],
    effects: [],
  };

  const ids = new Set();
  for (const c of arr(s.characters).slice(0, 8)) {
    const id = str(c?.id, `char${ids.size + 1}`);
    if (ids.has(id)) continue;
    ids.add(id);
    scene.characters.push({
      id,
      name: str(c.name, id),
      color: color(c.color, '#111111'),
      headColor: color(c.headColor, color(c.color, '#111111')),
      scale: num(c.scale, 1, 0.3, 3),
      accessory: pick(c.accessory, ACCESSORIES, 'none'),
      accessoryColor: color(c.accessoryColor, '#d62828'),
    });
  }

  const sortKeys = (keys) => keys.sort((a, b) => a.t - b.t);
  for (const tr of arr(s.tracks)) {
    const id = str(tr?.character, '');
    if (!ids.has(id)) { if (id) warnings.push(`Track for unknown character "${id}" ignored.`); continue; }
    let prev = { x: 0.5, y: scene.background.groundY, pose: 'stand', facing: 1, rot: 0 };
    const keys = sortKeys(arr(tr.keys).filter((k) => k && typeof k === 'object').map((k) => ({ ...k, t: num(k.t, 0, 0, duration) })));
    const out = keys.map((k) => {
      if (k.pose && !POSES[k.pose]) warnings.push(`Unknown pose "${k.pose}" replaced by previous pose.`);
      const key = {
        t: k.t,
        x: num(k.x, prev.x, -1, 2),
        y: num(k.y, prev.y, -1, 2),
        pose: POSES[k.pose] ? k.pose : prev.pose,
        joints: normalizeJoints(k.joints),
        facing: k.facing === undefined ? prev.facing : Number(k.facing) < 0 ? -1 : 1,
        rot: num(k.rot, 0, -720, 720),
        action: pick(k.action, ACTIONS, 'none'),
        ease: pick(k.ease, EASES, 'inOut'),
        expression: str(k.expression, ''),
      };
      prev = key;
      return key;
    });
    if (!out.length) out.push({ t: 0, x: 0.5, y: scene.background.groundY, pose: 'stand', joints: {}, facing: 1, rot: 0, action: 'idle', ease: 'inOut' });
    const existing = scene.tracks.find((t) => t.character === id);
    if (existing) existing.keys = sortKeys(existing.keys.concat(out));
    else scene.tracks.push({ character: id, keys: out });
  }
  for (const c of scene.characters) if (!scene.tracks.some((t) => t.character === c.id)) {
    scene.tracks.push({ character: c.id, keys: [{ t: 0, x: 0.5, y: scene.background.groundY, pose: 'stand', joints: {}, facing: 1, rot: 0, action: 'idle', ease: 'inOut' }] });
  }

  const propIds = new Set();
  for (const p of arr(s.props).slice(0, 20)) {
    const id = str(p?.id, `prop${propIds.size + 1}`);
    if (propIds.has(id)) continue;
    propIds.add(id);
    let prev = { x: 0.5, y: scene.background.groundY, rot: 0, scale: 1, opacity: 1, holder: '', hand: 'front' };
    const keys = sortKeys(arr(p.keys).filter((k) => k && typeof k === 'object').map((k) => {
      const key = {
        t: num(k.t, 0, 0, duration),
        x: num(k.x, prev.x, -1, 2),
        y: num(k.y, prev.y, -1, 2),
        rot: num(k.rot, prev.rot, -3600, 3600),
        scale: num(k.scale, prev.scale, 0, 10),
        opacity: num(k.opacity, prev.opacity, 0, 1),
        holder: ids.has(k.holder) ? k.holder : '',
        hand: k.hand === 'back' ? 'back' : 'front',
        ease: pick(k.ease, EASES, 'inOut'),
      };
      prev = key;
      return key;
    }));
    if (!keys.length) keys.push({ t: 0, ...prev, ease: 'inOut' });
    scene.props.push({ id, type: pick(p.type, PROP_TYPES, 'box'), color: color(p.color, '#e63946'), size: num(p.size, 40, 4, 600), text: str(p.text, ''), keys });
  }

  scene.camera = arr(s.camera).map((k) => ({ t: num(k?.t, 0, 0, duration), x: num(k?.x, 0.5, -1, 2), y: num(k?.y, 0.5, -1, 2), zoom: num(k?.zoom, 1, 0.2, 5), shake: num(k?.shake, 0, 0, 3), ease: pick(k?.ease, EASES, 'inOut') })).sort((a, b) => a.t - b.t);
  if (!scene.camera.length) scene.camera.push({ t: 0, x: 0.5, y: 0.5, zoom: 1, shake: 0, ease: 'inOut' });

  const soundOk = (n) => SOUNDS.includes(n) || (n?.startsWith?.('custom:') && customSounds.includes(n.slice(7)));
  scene.sfx = arr(s.sfx).filter((c) => {
    if (!soundOk(c?.sound)) { warnings.push(`Unknown sound "${c?.sound}" skipped.`); return false; }
    return true;
  }).map((c) => ({ t: num(c.t, 0, 0, duration), sound: c.sound, volume: num(c.volume, 1, 0, 2) })).sort((a, b) => a.t - b.t).slice(0, 300);

  const m = s.music && typeof s.music === 'object' ? s.music : {};
  scene.music = {
    mood: pick(m.mood, MOODS, 'happy'),
    bpm: num(m.bpm, 0, 0, 220),
    volume: num(m.volume, 0.45, 0, 1.5),
    custom: typeof m.custom === 'string' && customSounds.includes(m.custom) ? m.custom : '',
  };

  scene.captions = arr(s.captions).map((c) => ({ t: num(c?.t, 0, 0, duration), d: num(c?.d, 2, 0.2, duration), text: str(c?.text, '') })).filter((c) => c.text).slice(0, 60);
  scene.speech = arr(s.speech).filter((c) => ids.has(c?.character)).map((c) => ({ t: num(c.t, 0, 0, duration), d: num(c.d, 1.5, 0.2, duration), character: c.character, text: str(c.text, '') })).filter((c) => c.text).slice(0, 100);
  scene.effects = arr(s.effects).filter((e) => EFFECTS.includes(e?.type)).map((e) => ({ t: num(e.t, 0, 0, duration), d: num(e.d, 0.8, 0.1, duration), type: e.type, x: num(e.x, 0.5, -1, 2), y: num(e.y, 0.5, -1, 2), color: color(e.color, '#ffd166'), size: num(e.size, 1, 0.1, 5) })).slice(0, 120);

  return { scene, warnings };
}
