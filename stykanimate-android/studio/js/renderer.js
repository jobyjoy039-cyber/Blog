// Draws a normalized scene at any time t onto a 2D canvas. Everything is a pure
// function of (scene, t) so scrubbing, playback and video export agree exactly.
import { POSES, JOINTS, STAGE_W as W, STAGE_H as H } from './scene.js';

const EASE = {
  linear: (x) => x,
  in: (x) => x * x,
  out: (x) => 1 - (1 - x) * (1 - x),
  inOut: (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2),
};
const lerp = (a, b, k) => a + (b - a) * k;
const rad = (d) => (d * Math.PI) / 180;
const smooth = (x) => x * x * (3 - 2 * x);

/** Find the segment around t: returns [a, b, k] with k already eased. */
function segment(keys, t) {
  if (t <= keys[0].t || keys.length === 1) return [keys[0], keys[0], 0, 0];
  const last = keys[keys.length - 1];
  if (t >= last.t) return [last, last, 0, 0];
  let i = 0;
  while (i < keys.length - 2 && keys[i + 1].t <= t) i++;
  const a = keys[i], b = keys[i + 1];
  const raw = b.t > a.t ? (t - a.t) / (b.t - a.t) : 1;
  const moving = a.action === 'walk' || a.action === 'run';
  return [a, b, (EASE[moving ? 'linear' : a.ease] || EASE.inOut)(raw), raw];
}

function poseAngles(key) {
  const base = POSES[key.pose] || POSES.stand;
  return JOINTS.map((j) => (key.joints && key.joints[j] !== undefined ? key.joints[j] : base[j]));
}

function cyclePose(p1, p2, phase) {
  const w = (1 - Math.cos(phase * Math.PI)) / 2;
  const a = JOINTS.map((j) => POSES[p1][j]), b = JOINTS.map((j) => POSES[p2][j]);
  return a.map((v, i) => lerp(v, b[i], w));
}

/** Character state at time t. */
export function evalCharacter(scene, track, t) {
  const [a, b, k, raw] = segment(track.keys, t);
  let angles = poseAngles(a).map((v, i) => lerp(v, poseAngles(b)[i], k));
  let x = lerp(a.x, b.x, k), y = lerp(a.y, b.y, k);
  let bob = 0;
  if (a !== b && (a.action === 'walk' || a.action === 'run')) {
    const run = a.action === 'run';
    const dist = Math.abs(b.x - a.x) * W * raw;
    const stride = run ? 120 : 75;
    const phase = dist > 1 ? dist / stride : (t - a.t) * (run ? 3.2 : 2);
    const cyc = run ? cyclePose('run1', 'run2', phase) : cyclePose('walk1', 'walk2', phase);
    const edge = Math.min(1, raw / 0.12, (1 - raw) / 0.12);
    const w = smooth(Math.max(0, edge));
    angles = angles.map((v, i) => lerp(v, cyc[i], w));
    bob = -Math.abs(Math.sin(phase * Math.PI)) * (run ? 10 : 4) * w;
  } else if (a.action === 'dance') {
    const bpm = scene.music.bpm || 120;
    const phase = ((t - a.t) * bpm) / 60;
    const cyc = cyclePose('dance1', 'dance2', phase);
    const w = a === b ? 1 : smooth(Math.min(1, Math.min(raw, 1 - raw) / 0.1));
    angles = angles.map((v, i) => lerp(v, cyc[i], w));
    bob = -Math.abs(Math.sin(phase * Math.PI)) * 8 * w;
  } else if (a.action === 'idle' || (a === b && a.action === 'none')) {
    const breathe = Math.sin(t * 2.4);
    angles[0] += breathe * 1.5;
    angles[2] += breathe * 3;
    angles[4] -= breathe * 3;
  }
  const facing = raw < 0.5 || a === b ? a.facing : b.facing;
  const rot = lerp(a.rot, b.rot, k);
  return { x, y, angles, facing, rot, bob };
}

const L = { torso: 62, neck: 4, head: 17, upper: 40, fore: 38, thigh: 48, shin: 48 };

/** Joint positions relative to the hip, at scale 1, rotated by rot. */
export function skeleton(angles, facing, rot) {
  const [torso, head, bS, bE, fS, fE, bH, bK, fH, fK] = angles;
  const f = facing;
  const up = (d) => ({ x: Math.sin(rad(d)) * f, y: -Math.cos(rad(d)) });
  const down = (d) => ({ x: Math.sin(rad(d)) * f, y: Math.cos(rad(d)) });
  const add = (p, v, len) => ({ x: p.x + v.x * len, y: p.y + v.y * len });
  const hip = { x: 0, y: 0 };
  const neck = add(hip, up(torso), L.torso);
  const headC = add(neck, up(torso + head), L.neck + L.head);
  const arm = (s, e) => { const A = s - torso; const el = add(neck, down(A), L.upper); return [el, add(el, down(A + e), L.fore)]; };
  const leg = (h, kn) => { const kp = add(hip, down(h), L.thigh); return [kp, add(kp, down(h - kn), L.shin)]; };
  const [bElb, bHand] = arm(bS, bE), [fElb, fHand] = arm(fS, fE);
  const [bKnee, bFoot] = leg(bH, bK), [fKnee, fFoot] = leg(fH, fK);
  const pts = { hip, neck, headC, bElb, bHand, fElb, fHand, bKnee, bFoot, fKnee, fFoot };
  if (rot) {
    const c = Math.cos(rad(rot * f)), s = Math.sin(rad(rot * f));
    const center = { x: neck.x / 2, y: neck.y / 2 };
    for (const k in pts) {
      const p = pts[k], dx = p.x - center.x, dy = p.y - center.y;
      pts[k] = { x: center.x + dx * c - dy * s, y: center.y + dx * s + dy * c };
    }
  }
  return pts;
}

/** World-space joints for a character at time t (feet on the key's y). */
export function placeCharacter(scene, ch, t) {
  const track = scene.tracks.find((tr) => tr.character === ch.id);
  const st = evalCharacter(scene, track, t);
  const pts = skeleton(st.angles, st.facing, st.rot);
  let maxY = -Infinity;
  for (const k in pts) maxY = Math.max(maxY, pts[k].y + (k === 'headC' ? L.head : 0));
  const sc = ch.scale;
  const ox = st.x * W, oy = st.y * H - maxY * sc + st.bob * sc;
  const world = {};
  for (const k in pts) world[k] = { x: ox + pts[k].x * sc, y: oy + pts[k].y * sc };
  return { st, pts: world, scale: sc, feetY: st.y * H };
}

function rng(seed) {
  let a = seed >>> 0;
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const hash = (s) => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };

function shade(hex, amt) {
  let c = hex.replace('#', '');
  if (c.length === 3) c = c.split('').map((x) => x + x).join('');
  const n = parseInt(c, 16);
  const f = (v) => Math.max(0, Math.min(255, Math.round(v + amt * 255)));
  return `rgb(${f(n >> 16)},${f((n >> 8) & 255)},${f(n & 255)})`;
}

function drawSky(ctx, bg) {
  const g = ctx.createLinearGradient(0, 0, 0, H);
  bg.sky.forEach((c, i) => g.addColorStop(bg.sky.length === 1 ? 0 : i / (bg.sky.length - 1), c));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
}

function drawScenery(ctx, bg, t) {
  const gy = bg.groundY * H;
  const r = rng(hash(bg.scenery));
  const x0 = -W, x1 = 2 * W;
  ctx.save();
  switch (bg.scenery) {
    case 'city': {
      for (let layer = 0; layer < 2; layer++) {
        let x = x0;
        ctx.fillStyle = layer ? '#2b2d42' : '#8d99ae';
        while (x < x1) {
          const w = 60 + r() * 90, h = (layer ? 120 : 200) + r() * (layer ? 160 : 220);
          ctx.fillRect(x, gy - h, w - 6, h);
          if (layer) {
            ctx.fillStyle = '#ffd166';
            for (let wy = gy - h + 14; wy < gy - 20; wy += 26) for (let wx = x + 10; wx < x + w - 20; wx += 20) if (r() > 0.45) ctx.fillRect(wx, wy, 8, 12);
            ctx.fillStyle = '#2b2d42';
          }
          x += w;
        }
      }
      break;
    }
    case 'forest': case 'mountains': {
      if (bg.scenery === 'mountains') {
        ctx.fillStyle = '#6c757d';
        for (let x = x0; x < x1; x += 260) { const h = 180 + r() * 220; ctx.beginPath(); ctx.moveTo(x - 60, gy); ctx.lineTo(x + 130, gy - h); ctx.lineTo(x + 320, gy); ctx.fill(); ctx.fillStyle = '#f8f9fa'; ctx.beginPath(); ctx.moveTo(x + 130, gy - h); ctx.lineTo(x + 95, gy - h + 60); ctx.lineTo(x + 165, gy - h + 60); ctx.fill(); ctx.fillStyle = '#6c757d'; }
      }
      for (let x = x0; x < x1; x += 70 + r() * 90) {
        const h = 120 + r() * 140;
        ctx.fillStyle = '#5e3a1a'; ctx.fillRect(x - 8, gy - h * 0.4, 16, h * 0.4);
        ctx.fillStyle = r() > 0.5 ? '#2d6a4f' : '#40916c';
        ctx.beginPath(); ctx.moveTo(x - 50, gy - h * 0.3); ctx.lineTo(x, gy - h); ctx.lineTo(x + 50, gy - h * 0.3); ctx.fill();
      }
      break;
    }
    case 'desert': {
      ctx.fillStyle = '#ffb703'; ctx.beginPath(); ctx.arc(W * 0.8, H * 0.2, 60, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#e9c46a';
      for (let x = x0; x < x1; x += 400) { ctx.beginPath(); ctx.ellipse(x, gy, 300, 70 + r() * 50, 0, Math.PI, 0); ctx.fill(); }
      ctx.strokeStyle = '#2a9d8f'; ctx.lineWidth = 18; ctx.lineCap = 'round';
      for (let x = x0 + 200; x < x1; x += 500 + r() * 300) { ctx.beginPath(); ctx.moveTo(x, gy); ctx.lineTo(x, gy - 110); ctx.moveTo(x, gy - 60); ctx.lineTo(x - 30, gy - 60); ctx.lineTo(x - 30, gy - 85); ctx.moveTo(x, gy - 50); ctx.lineTo(x + 28, gy - 50); ctx.lineTo(x + 28, gy - 80); ctx.stroke(); }
      break;
    }
    case 'space': case 'night': {
      ctx.fillStyle = '#ffffff';
      for (let i = 0; i < 260; i++) { const tw = 0.5 + 0.5 * Math.sin(t * 3 + i); ctx.globalAlpha = 0.4 + 0.6 * tw; ctx.fillRect(x0 + r() * (x1 - x0), r() * gy, 2 + r() * 2, 2 + r() * 2); }
      ctx.globalAlpha = 1;
      if (bg.scenery === 'space') { ctx.fillStyle = '#e76f51'; ctx.beginPath(); ctx.arc(W * 0.78, H * 0.22, 70, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = '#f4a261'; ctx.lineWidth = 6; ctx.beginPath(); ctx.ellipse(W * 0.78, H * 0.22, 120, 22, -0.3, 0, Math.PI * 2); ctx.stroke(); }
      else { ctx.fillStyle = '#f1faee'; ctx.beginPath(); ctx.arc(W * 0.82, H * 0.18, 45, 0, Math.PI * 2); ctx.fill(); }
      break;
    }
    case 'room': case 'dojo': {
      ctx.fillStyle = bg.scenery === 'dojo' ? '#d4a373' : '#f1e3d3'; ctx.fillRect(x0, 0, x1 - x0, gy);
      ctx.strokeStyle = 'rgba(0,0,0,0.12)'; ctx.lineWidth = 4;
      for (let x = x0; x < x1; x += bg.scenery === 'dojo' ? 160 : 90) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, gy); ctx.stroke(); }
      ctx.fillStyle = '#bde0fe'; ctx.fillRect(W * 0.62, H * 0.18, 220, 150); ctx.strokeStyle = '#6b4f3a'; ctx.lineWidth = 10; ctx.strokeRect(W * 0.62, H * 0.18, 220, 150); ctx.beginPath(); ctx.moveTo(W * 0.62 + 110, H * 0.18); ctx.lineTo(W * 0.62 + 110, H * 0.18 + 150); ctx.stroke();
      if (bg.scenery === 'dojo') { ctx.fillStyle = '#9d0208'; ctx.beginPath(); ctx.arc(W * 0.25, H * 0.3, 50, 0, Math.PI * 2); ctx.fill(); }
      break;
    }
    case 'beach': {
      ctx.fillStyle = '#0096c7'; ctx.fillRect(x0, gy - 80, x1 - x0, 80);
      ctx.strokeStyle = '#caf0f8'; ctx.lineWidth = 4;
      for (let x = x0; x < x1; x += 80) { ctx.beginPath(); ctx.arc(x + ((t * 30) % 80), gy - 80, 20, 0, Math.PI); ctx.stroke(); }
      ctx.fillStyle = '#ffd60a'; ctx.beginPath(); ctx.arc(W * 0.15, H * 0.2, 55, 0, Math.PI * 2); ctx.fill();
      break;
    }
    case 'stage': {
      ctx.fillStyle = '#7b2cbf'; ctx.fillRect(x0, 0, x1 - x0, gy);
      ctx.fillStyle = '#9d0208'; ctx.fillRect(-40, 0, 200, gy); ctx.fillRect(W - 160, 0, 200, gy);
      ctx.fillStyle = 'rgba(255,255,200,0.15)'; ctx.beginPath(); ctx.moveTo(W / 2 - 40, 0); ctx.lineTo(W / 2 + 40, 0); ctx.lineTo(W / 2 + 260, gy); ctx.lineTo(W / 2 - 260, gy); ctx.fill();
      break;
    }
  }
  ctx.restore();
  ctx.fillStyle = bg.ground;
  ctx.fillRect(x0, gy, x1 - x0, H * 2);
  ctx.fillStyle = shade(bg.ground, -0.12);
  ctx.fillRect(x0, gy, x1 - x0, 6);
}

function drawCharacter(ctx, ch, placed, t) {
  const { pts: p, scale: s, st } = placed;
  const lw = 9 * s;
  const line = (a, b, c) => { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(c.x, c.y); ctx.stroke(); };
  ctx.save();
  ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = lw; ctx.strokeStyle = ch.color;
  // shadow
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  const lift = Math.max(0, placed.feetY - Math.max(p.bFoot.y, p.fFoot.y));
  ctx.beginPath(); ctx.ellipse(p.hip.x, placed.feetY + 3, Math.max(8, 34 * s - lift * 0.1), 6 * s, 0, 0, Math.PI * 2); ctx.fill();
  if (ch.accessory === 'cape') {
    const wave = Math.sin(t * 6) * 8 * s;
    ctx.fillStyle = ch.accessoryColor;
    ctx.beginPath(); ctx.moveTo(p.neck.x, p.neck.y);
    ctx.quadraticCurveTo(p.hip.x - 30 * s * st.facing + wave, (p.neck.y + p.hip.y) / 2, p.hip.x - 40 * s * st.facing + wave, p.hip.y + 20 * s);
    ctx.lineTo(p.hip.x - 5 * s * st.facing, p.hip.y + 5 * s); ctx.closePath(); ctx.fill();
  }
  ctx.globalAlpha = 0.85; ctx.strokeStyle = shade(ch.color, ch.color === '#111111' || ch.color === '#000000' ? 0.25 : -0.15);
  line(p.neck, p.bElb, p.bHand); line(p.hip, p.bKnee, p.bFoot);
  ctx.globalAlpha = 1; ctx.strokeStyle = ch.color;
  ctx.beginPath(); ctx.moveTo(p.hip.x, p.hip.y); ctx.lineTo(p.neck.x, p.neck.y); ctx.stroke();
  line(p.hip, p.fKnee, p.fFoot); line(p.neck, p.fElb, p.fHand);
  const r = 17 * s;
  ctx.fillStyle = ch.headColor;
  ctx.beginPath(); ctx.arc(p.headC.x, p.headC.y, r, 0, Math.PI * 2); ctx.fill();
  const hx = p.headC.x, hy = p.headC.y, f = st.facing;
  switch (ch.accessory) {
    case 'hat': ctx.fillStyle = ch.accessoryColor; ctx.fillRect(hx - r * 1.3, hy - r * 0.9, r * 2.6, r * 0.35); ctx.fillRect(hx - r * 0.8, hy - r * 2.1, r * 1.6, r * 1.3); break;
    case 'crown': ctx.fillStyle = '#ffd60a'; ctx.beginPath(); ctx.moveTo(hx - r, hy - r * 0.7); for (let i = 0; i <= 4; i++) { ctx.lineTo(hx - r + (i * r) / 2, hy - r * (i % 2 ? 1.2 : 1.9)); } ctx.lineTo(hx + r, hy - r * 0.7); ctx.fill(); break;
    case 'headband': {
      ctx.strokeStyle = ch.accessoryColor; ctx.lineWidth = 5 * s; ctx.beginPath(); ctx.moveTo(hx - r, hy - r * 0.35); ctx.lineTo(hx + r, hy - r * 0.35); ctx.stroke();
      const w = Math.sin(t * 9) * 6 * s; ctx.beginPath(); ctx.moveTo(hx - r * f, hy - r * 0.35); ctx.quadraticCurveTo(hx - r * 2 * f, hy - r * 0.2 + w, hx - r * 3 * f, hy + w); ctx.stroke(); break;
    }
    case 'bow': ctx.fillStyle = ch.accessoryColor; ctx.beginPath(); ctx.ellipse(hx - r * 0.6 * f, hy - r * 0.9, r * 0.5, r * 0.3, 0.6, 0, Math.PI * 2); ctx.ellipse(hx - r * 0.1 * f, hy - r * 1.1, r * 0.5, r * 0.3, -0.6, 0, Math.PI * 2); ctx.fill(); break;
    case 'glasses': ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.5 * s; ctx.beginPath(); ctx.arc(hx + r * 0.45 * f, hy - r * 0.1, r * 0.3, 0, Math.PI * 2); ctx.stroke(); break;
    case 'sword': {
      const dx = p.fHand.x - p.fElb.x, dy = p.fHand.y - p.fElb.y, len = Math.hypot(dx, dy) || 1;
      ctx.strokeStyle = '#adb5bd'; ctx.lineWidth = 5 * s; ctx.beginPath(); ctx.moveTo(p.fHand.x, p.fHand.y); ctx.lineTo(p.fHand.x + (dx / len) * 80 * s, p.fHand.y + (dy / len) * 80 * s); ctx.stroke();
      ctx.strokeStyle = ch.accessoryColor; ctx.lineWidth = 6 * s; ctx.beginPath(); ctx.moveTo(p.fHand.x - (dy / len) * 10 * s, p.fHand.y + (dx / len) * 10 * s); ctx.lineTo(p.fHand.x + (dy / len) * 10 * s, p.fHand.y - (dx / len) * 10 * s); ctx.stroke(); break;
    }
  }
  ctx.restore();
}

function propState(scene, prop, t, placed) {
  const [a, b, k] = segment(prop.keys, t);
  const pos = (key) => {
    if (key.holder && placed[key.holder]) { const h = placed[key.holder].pts[key.hand === 'back' ? 'bHand' : 'fHand']; return { x: h.x, y: h.y, held: true }; }
    return { x: key.x * W, y: key.y * H, held: false };
  };
  const pa = pos(a), pb = pos(b);
  return { x: lerp(pa.x, pb.x, k), y: lerp(pa.y, pb.y, k), held: k < 0.5 ? pa.held : pb.held, rot: lerp(a.rot, b.rot, k), scale: lerp(a.scale, b.scale, k), opacity: lerp(a.opacity, b.opacity, k) };
}

function drawProp(ctx, prop, st) {
  if (st.opacity <= 0.01 || st.scale <= 0.01) return;
  const s = prop.size * st.scale;
  ctx.save();
  ctx.globalAlpha = st.opacity;
  ctx.translate(st.x, st.held ? st.y : st.y - s / 2);
  ctx.rotate(rad(st.rot));
  ctx.fillStyle = prop.color; ctx.strokeStyle = shade(prop.color, -0.3); ctx.lineWidth = Math.max(2, s * 0.06); ctx.lineJoin = 'round';
  const star = (n, r1, r2) => { ctx.beginPath(); for (let i = 0; i < n * 2; i++) { const r = i % 2 ? r2 : r1, a = (i * Math.PI) / n - Math.PI / 2; ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); } ctx.closePath(); };
  switch (prop.type) {
    case 'ball': ctx.beginPath(); ctx.arc(0, 0, s / 2, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
    case 'box': ctx.fillRect(-s / 2, -s / 2, s, s); ctx.strokeRect(-s / 2, -s / 2, s, s); break;
    case 'rock': ctx.beginPath(); ctx.ellipse(0, s * 0.1, s * 0.6, s * 0.4, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
    case 'star': star(5, s / 2, s / 4.5); ctx.fill(); ctx.stroke(); break;
    case 'coin': ctx.fillStyle = '#ffd60a'; ctx.beginPath(); ctx.ellipse(0, 0, s * 0.35, s / 2, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
    case 'heart': ctx.beginPath(); ctx.moveTo(0, s * 0.35); ctx.bezierCurveTo(-s * 0.7, -s * 0.1, -s * 0.3, -s * 0.6, 0, -s * 0.2); ctx.bezierCurveTo(s * 0.3, -s * 0.6, s * 0.7, -s * 0.1, 0, s * 0.35); ctx.fill(); break;
    case 'bomb': ctx.fillStyle = '#222'; ctx.beginPath(); ctx.arc(0, s * 0.05, s * 0.45, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = '#8d6e63'; ctx.beginPath(); ctx.moveTo(s * 0.2, -s * 0.35); ctx.quadraticCurveTo(s * 0.4, -s * 0.6, s * 0.5, -s * 0.5); ctx.stroke(); ctx.fillStyle = '#ff9f1c'; ctx.beginPath(); ctx.arc(s * 0.5, -s * 0.5, s * 0.08, 0, Math.PI * 2); ctx.fill(); break;
    case 'tree': ctx.fillStyle = '#6f4518'; ctx.fillRect(-s * 0.08, -s * 0.1, s * 0.16, s * 0.6); ctx.fillStyle = prop.color; ctx.beginPath(); ctx.arc(0, -s * 0.25, s * 0.35, 0, Math.PI * 2); ctx.fill(); break;
    case 'sign': {
      ctx.fillStyle = '#6f4518'; ctx.fillRect(-s * 0.04, -s * 0.1, s * 0.08, s * 0.6);
      ctx.fillStyle = prop.color; ctx.fillRect(-s * 0.6, -s * 0.5, s * 1.2, s * 0.45); ctx.strokeRect(-s * 0.6, -s * 0.5, s * 1.2, s * 0.45);
      if (prop.text) { ctx.fillStyle = '#fff'; ctx.font = `bold ${Math.max(10, s * 0.16)}px sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(prop.text, 0, -s * 0.275, s * 1.1); }
      break;
    }
    case 'car': ctx.fillRect(-s, -s * 0.1, s * 2, s * 0.45); ctx.fillRect(-s * 0.55, -s * 0.45, s * 1.1, s * 0.38); ctx.fillStyle = '#bde0fe'; ctx.fillRect(-s * 0.45, -s * 0.4, s * 0.4, s * 0.28); ctx.fillRect(s * 0.05, -s * 0.4, s * 0.4, s * 0.28); ctx.fillStyle = '#222'; ctx.beginPath(); ctx.arc(-s * 0.55, s * 0.35, s * 0.17, 0, Math.PI * 2); ctx.arc(s * 0.55, s * 0.35, s * 0.17, 0, Math.PI * 2); ctx.fill(); break;
    case 'chair': ctx.fillStyle = prop.color; ctx.fillRect(-s * 0.4, 0, s * 0.8, s * 0.1); ctx.fillRect(-s * 0.4, -s * 0.5, s * 0.1, s * 0.5); ctx.fillRect(-s * 0.4, 0, s * 0.08, s * 0.5); ctx.fillRect(s * 0.32, 0, s * 0.08, s * 0.5); break;
    case 'sword': ctx.fillStyle = '#adb5bd'; ctx.fillRect(-s * 0.04, -s * 0.5, s * 0.08, s * 0.75); ctx.fillStyle = prop.color; ctx.fillRect(-s * 0.18, s * 0.22, s * 0.36, s * 0.06); ctx.fillRect(-s * 0.04, s * 0.25, s * 0.08, s * 0.2); break;
    case 'cup': ctx.beginPath(); ctx.moveTo(-s * 0.3, -s * 0.4); ctx.lineTo(s * 0.3, -s * 0.4); ctx.lineTo(s * 0.22, s * 0.4); ctx.lineTo(-s * 0.22, s * 0.4); ctx.closePath(); ctx.fill(); ctx.stroke(); break;
    case 'door': ctx.fillRect(-s * 0.35, -s * 0.5, s * 0.7, s); ctx.strokeRect(-s * 0.35, -s * 0.5, s * 0.7, s); ctx.fillStyle = '#ffd60a'; ctx.beginPath(); ctx.arc(s * 0.22, 0, s * 0.05, 0, Math.PI * 2); ctx.fill(); break;
  }
  ctx.restore();
}

function wrap(ctx, text, maxW) {
  const words = text.split(/\s+/), lines = [];
  let line = '';
  for (const w of words) { const test = line ? `${line} ${w}` : w; if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test; }
  if (line) lines.push(line);
  return lines.slice(0, 4);
}

function drawBubble(ctx, text, x, y, alpha) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = 'bold 26px sans-serif';
  const lines = wrap(ctx, text, 300);
  const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 32, h = lines.length * 32 + 20;
  const bx = Math.min(W * 2, Math.max(-W, x - w / 2)), by = y - h - 30;
  ctx.fillStyle = '#fff'; ctx.strokeStyle = '#111'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.roundRect(bx, by, w, h, 18); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x - 10, by + h - 2); ctx.lineTo(x, y - 8); ctx.lineTo(x + 12, by + h - 2); ctx.fill();
  ctx.beginPath(); ctx.moveTo(x - 10, by + h); ctx.lineTo(x, y - 8); ctx.lineTo(x + 12, by + h); ctx.stroke();
  ctx.fillStyle = '#111'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  lines.forEach((l, i) => ctx.fillText(l, bx + w / 2, by + 12 + i * 32));
  ctx.restore();
}

function drawEffect(ctx, e, t) {
  const p = (t - e.t) / e.d;
  if (p < 0 || p > 1) return;
  const x = e.x * W, y = e.y * H, s = e.size, r = rng(hash(`${e.type}${e.t}${e.x}`));
  ctx.save();
  switch (e.type) {
    case 'explosion': {
      ctx.globalAlpha = 1 - p;
      const g = ctx.createRadialGradient(x, y, 0, x, y, 160 * s * (0.3 + p));
      g.addColorStop(0, '#fff3b0'); g.addColorStop(0.4, e.color); g.addColorStop(1, 'rgba(230,57,70,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 160 * s * (0.3 + p), 0, Math.PI * 2); ctx.fill();
      for (let i = 0; i < 24; i++) { const a = r() * Math.PI * 2, d = (60 + r() * 220) * s * p; ctx.fillStyle = i % 2 ? '#555' : e.color; ctx.fillRect(x + Math.cos(a) * d, y + Math.sin(a) * d + 200 * p * p, 8 * s, 8 * s); }
      break;
    }
    case 'impact': {
      ctx.globalAlpha = 1 - p; ctx.fillStyle = e.color; ctx.translate(x, y); ctx.scale(s * (0.6 + p), s * (0.6 + p));
      ctx.beginPath(); for (let i = 0; i < 16; i++) { const rr = i % 2 ? 22 : 60, a = (i * Math.PI) / 8; ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); } ctx.closePath(); ctx.fill();
      break;
    }
    case 'dust': case 'smoke': {
      for (let i = 0; i < 10; i++) { const a = r() * Math.PI - Math.PI, d = (20 + r() * 80) * s * p; ctx.globalAlpha = (1 - p) * 0.6; ctx.fillStyle = e.type === 'smoke' ? '#6c757d' : '#c8b6a6'; ctx.beginPath(); ctx.arc(x + Math.cos(a) * d * 1.5, y + Math.sin(a) * d * (e.type === 'smoke' ? 2 : 0.5) - (e.type === 'smoke' ? 120 * p : 0), (12 + 20 * p) * s, 0, Math.PI * 2); ctx.fill(); }
      break;
    }
    case 'sparkle': case 'confetti': {
      for (let i = 0; i < 30; i++) {
        const a = r() * Math.PI * 2, d = r() * 160 * s, px = x + Math.cos(a) * d, py = y + Math.sin(a) * d * 0.7 + (e.type === 'confetti' ? 260 * p * p : 0);
        ctx.globalAlpha = (1 - p) * (0.5 + 0.5 * Math.sin(t * 20 + i));
        ctx.fillStyle = e.type === 'confetti' ? ['#e63946', '#ffd166', '#06d6a0', '#118ab2', '#c77dff'][i % 5] : e.color;
        ctx.save(); ctx.translate(px, py); ctx.rotate(t * 6 + i); ctx.fillRect(-5 * s, -2 * s, 10 * s, e.type === 'confetti' ? 5 * s : 10 * s); ctx.restore();
      }
      break;
    }
    case 'fire': {
      for (let i = 0; i < 18; i++) { const ph = (t * 2 + r()) % 1; ctx.globalAlpha = (1 - ph) * 0.8 * Math.min(1, (1 - p) * 4); ctx.fillStyle = ph < 0.3 ? '#ffd166' : ph < 0.6 ? '#f77f00' : '#d62828'; ctx.beginPath(); ctx.arc(x + (r() - 0.5) * 60 * s, y - ph * 120 * s, (18 - ph * 12) * s, 0, Math.PI * 2); ctx.fill(); }
      break;
    }
  }
  ctx.restore();
}

function drawScreenEffect(ctx, e, t) {
  const p = (t - e.t) / e.d;
  if (p < 0 || p > 1) return;
  const r = rng(hash(`${e.type}${e.t}`));
  ctx.save();
  switch (e.type) {
    case 'flash': ctx.globalAlpha = 1 - p; ctx.fillStyle = e.color || '#fff'; ctx.fillRect(0, 0, W, H); break;
    case 'lightning': if (p < 0.5 && Math.floor(p * 10) % 2 === 0) { ctx.globalAlpha = 0.7; ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1; ctx.strokeStyle = '#fff'; ctx.lineWidth = 6; ctx.beginPath(); let lx = e.x * W, ly = 0; ctx.moveTo(lx, ly); while (ly < H * 0.8) { lx += (r() - 0.5) * 80; ly += 40 + r() * 40; ctx.lineTo(lx, ly); } ctx.stroke(); } break;
    case 'speedlines': ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 3; for (let i = 0; i < 30; i++) { const yy = r() * H, len = 100 + r() * 300, xx = ((r() * W + t * 2400) % (W + len)) - len; ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx + len, yy); ctx.stroke(); } break;
    case 'rain': ctx.strokeStyle = 'rgba(180,200,255,0.6)'; ctx.lineWidth = 2; for (let i = 0; i < 140; i++) { const xx = r() * W, yy = (r() * H + t * 900) % H; ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx - 6, yy + 22); ctx.stroke(); } break;
    case 'snow': ctx.fillStyle = 'rgba(255,255,255,0.9)'; for (let i = 0; i < 120; i++) { const xx = (r() * W + Math.sin(t + i) * 30) % W, yy = (r() * H + t * 80) % H; ctx.beginPath(); ctx.arc(xx, yy, 2 + r() * 3, 0, Math.PI * 2); ctx.fill(); } break;
  }
  ctx.restore();
}
const SCREEN_EFFECTS = new Set(['flash', 'lightning', 'speedlines', 'rain', 'snow']);

function cameraAt(scene, t) {
  const [a, b, k] = segment(scene.camera, t);
  const shake = lerp(a.shake, b.shake, k);
  return { x: lerp(a.x, b.x, k), y: lerp(a.y, b.y, k), zoom: lerp(a.zoom, b.zoom, k), sx: shake ? (Math.sin(t * 91) + Math.sin(t * 53)) * 10 * shake : 0, sy: shake ? (Math.cos(t * 77) + Math.sin(t * 41)) * 10 * shake : 0 };
}

/** Draw the whole frame. ctx's canvas may be any size; we scale to fit. */
export function drawFrame(ctx, scene, t) {
  const cw = ctx.canvas.width, chh = ctx.canvas.height;
  ctx.save();
  ctx.setTransform(cw / W, 0, 0, chh / H, 0, 0);
  drawSky(ctx, scene.background);
  const cam = cameraAt(scene, t);
  ctx.save();
  ctx.translate(W / 2 + cam.sx, H / 2 + cam.sy);
  ctx.scale(cam.zoom, cam.zoom);
  ctx.translate(-cam.x * W, -cam.y * H);
  drawScenery(ctx, scene.background, t);
  const placed = {};
  for (const ch of scene.characters) placed[ch.id] = placeCharacter(scene, ch, t);
  const props = scene.props.map((p) => [p, propState(scene, p, t, placed)]);
  for (const [p, st] of props) if (!st.held) drawProp(ctx, p, st);
  for (const ch of scene.characters) drawCharacter(ctx, ch, placed[ch.id], t);
  for (const [p, st] of props) if (st.held) drawProp(ctx, p, st);
  for (const e of scene.effects) if (!SCREEN_EFFECTS.has(e.type)) drawEffect(ctx, e, t);
  for (const sp of scene.speech) {
    if (t < sp.t || t > sp.t + sp.d) continue;
    const pl = placed[sp.character];
    const fade = Math.min(1, (t - sp.t) / 0.15, (sp.t + sp.d - t) / 0.15);
    drawBubble(ctx, sp.text, pl.pts.headC.x, pl.pts.headC.y - 20 * pl.scale, fade);
  }
  ctx.restore();
  for (const e of scene.effects) if (SCREEN_EFFECTS.has(e.type)) drawScreenEffect(ctx, e, t);
  for (const c of scene.captions) {
    if (t < c.t || t > c.t + c.d) continue;
    ctx.save();
    ctx.globalAlpha = Math.min(1, (t - c.t) / 0.2, (c.t + c.d - t) / 0.2);
    ctx.font = 'bold 34px sans-serif';
    const lines = wrap(ctx, c.text, W - 200);
    const h = lines.length * 42 + 20;
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, H - h - 30, W, h);
    ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    lines.forEach((l, i) => ctx.fillText(l, W / 2, H - h - 20 + i * 42));
    ctx.restore();
  }
  ctx.restore();
}
