// Canvas renderer for scenes: background, scenery, stick figures, props, effects and captions.
import { BONES, FIGURE_HEIGHT, figureStateAt, propStateAt } from './scene.js';

const rad = (d) => (d * Math.PI) / 180;
// Unit vector for an angle measured from straight down, positive toward +x.
const down = (a) => [Math.sin(rad(a)), Math.cos(rad(a))];

export function unitFor(H, fig) {
  return (H / 430) * (fig ? fig.scale : 1);
}

// Computes canvas-space joint positions for a figure state. Used for drawing and for hit testing.
export function skeleton(state, fig, W, H, groundY) {
  const u = unitFor(H, fig);
  const f = state.facing;
  const p = state.pose;
  const T = p.torso;
  const pts = {};
  const add = (from, angle, len) => {
    const [dx, dy] = down(angle);
    return [from[0] + dx * len * f, from[1] + dy * len];
  };
  pts.hip = [0, 0];
  pts.neck = add(pts.hip, 180 - T, BONES.torso);
  pts.shoulder = add(pts.hip, 180 - T, BONES.torso * 0.9);
  pts.head = add(pts.neck, 180 - T - p.head, BONES.neck + BONES.head);
  for (const side of ['l', 'r']) {
    const arm = p[`${side}Shoulder`] - T;
    pts[`${side}Elbow`] = add(pts.shoulder, arm, BONES.upperArm);
    pts[`${side}Hand`] = add(pts[`${side}Elbow`], arm + p[`${side}Elbow`], BONES.forearm);
    const leg = p[`${side}Hip`];
    pts[`${side}Knee`] = add(pts.hip, leg, BONES.thigh);
    pts[`${side}Foot`] = add(pts[`${side}Knee`], leg - p[`${side}Knee`], BONES.shin);
  }
  // Whole-body rotation (flips, falls) around the hip.
  if (state.rot) {
    const c = Math.cos(rad(state.rot * f)), s = Math.sin(rad(state.rot * f));
    for (const k in pts) {
      const [x, y] = pts[k];
      pts[k] = [x * c - y * s, x * s + y * c];
    }
  }
  // Ground the figure: the lowest point (including the head's bottom) rests on the ground line.
  let lowest = -Infinity;
  for (const k in pts) lowest = Math.max(lowest, pts[k][1] + (k === 'head' ? BONES.head : 0));
  const ox = state.x * W;
  const oy = groundY * H - lowest * u - state.lift * FIGURE_HEIGHT * u;
  const out = {};
  for (const k in pts) out[k] = [ox + pts[k][0] * u, oy + pts[k][1] * u];
  out.unit = u;
  return out;
}

function rand(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function shade(hex, amt) {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const n = parseInt(h, 16);
  const ch = (v) => Math.max(0, Math.min(255, Math.round(v + amt * 255)));
  return `rgb(${ch(n >> 16)},${ch((n >> 8) & 255)},${ch(n & 255)})`;
}

function luminance(hex) {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const n = parseInt(h, 16);
  return (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
}

function drawBackground(ctx, bg, W, H) {
  const gy = bg.groundY * H;
  const sky = ctx.createLinearGradient(0, 0, 0, gy);
  sky.addColorStop(0, shade(bg.sky, 0.06));
  sky.addColorStop(1, shade(bg.sky, -0.04));
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, W, gy);
  const r = rand(7);
  ctx.save();
  switch (bg.scenery) {
    case 'night':
    case 'space':
      ctx.fillStyle = '#fff';
      for (let i = 0; i < 90; i++) {
        ctx.globalAlpha = 0.3 + r() * 0.7;
        ctx.fillRect(r() * W, r() * gy, 1.5 + r() * 2, 1.5 + r() * 2);
      }
      ctx.globalAlpha = 1;
      ctx.fillStyle = bg.scenery === 'space' ? '#c9b6ff' : '#fdf6c3';
      ctx.beginPath();
      ctx.arc(W * 0.82, H * 0.16, H * 0.06, 0, Math.PI * 2);
      ctx.fill();
      break;
    case 'city': {
      let x = 0;
      while (x < W) {
        const w = W * (0.05 + r() * 0.07), h = gy * (0.25 + r() * 0.45);
        ctx.fillStyle = shade(bg.sky, -0.18 - r() * 0.12);
        ctx.fillRect(x, gy - h, w, h);
        ctx.fillStyle = 'rgba(255,240,170,0.55)';
        for (let wy = gy - h + 10; wy < gy - 12; wy += 18)
          for (let wx = x + 6; wx < x + w - 8; wx += 14) if (r() > 0.45) ctx.fillRect(wx, wy, 6, 9);
        x += w + 4;
      }
      break;
    }
    case 'forest':
      for (let i = 0; i < 14; i++) {
        const x = r() * W, h = gy * (0.25 + r() * 0.3);
        ctx.fillStyle = '#6b4f2a';
        ctx.fillRect(x - 5, gy - h * 0.35, 10, h * 0.35);
        ctx.fillStyle = shade('#2f7d32', -r() * 0.15);
        ctx.beginPath();
        ctx.moveTo(x - h * 0.28, gy - h * 0.3);
        ctx.lineTo(x, gy - h);
        ctx.lineTo(x + h * 0.28, gy - h * 0.3);
        ctx.fill();
      }
      break;
    case 'hills':
      ctx.fillStyle = shade(bg.ground, 0.05);
      ctx.beginPath();
      ctx.moveTo(0, gy);
      for (let x = 0; x <= W; x += W / 40) ctx.lineTo(x, gy - gy * (0.12 + 0.08 * Math.sin(x / W * 7) + 0.05 * Math.sin(x / W * 17)));
      ctx.lineTo(W, gy);
      ctx.fill();
      ctx.fillStyle = '#ffd166';
      ctx.beginPath();
      ctx.arc(W * 0.15, H * 0.15, H * 0.06, 0, Math.PI * 2);
      ctx.fill();
      break;
    case 'beach':
      ctx.fillStyle = '#4fa3d9';
      ctx.fillRect(0, gy - gy * 0.14, W, gy * 0.14);
      ctx.fillStyle = '#ffd166';
      ctx.beginPath();
      ctx.arc(W * 0.8, H * 0.14, H * 0.07, 0, Math.PI * 2);
      ctx.fill();
      break;
    case 'room':
      ctx.fillStyle = shade(bg.sky, -0.08);
      ctx.fillRect(W * 0.12, gy * 0.22, W * 0.2, gy * 0.35);
      ctx.strokeStyle = shade(bg.sky, -0.3);
      ctx.lineWidth = 6;
      ctx.strokeRect(W * 0.12, gy * 0.22, W * 0.2, gy * 0.35);
      ctx.fillStyle = shade(bg.sky, -0.22);
      ctx.fillRect(W * 0.62, gy * 0.35, W * 0.12, gy * 0.65);
      break;
    case 'arena':
      ctx.fillStyle = shade(bg.sky, -0.25);
      for (let i = 0; i < 160; i++) {
        ctx.beginPath();
        ctx.arc(r() * W, gy * (0.35 + r() * 0.55), 4 + r() * 4, 0, Math.PI * 2);
        ctx.fill();
      }
      break;
    default:
  }
  ctx.restore();
  ctx.fillStyle = bg.ground;
  ctx.fillRect(0, gy, W, H - gy);
  ctx.fillStyle = shade(bg.ground, -0.12);
  ctx.fillRect(0, gy, W, Math.max(2, H * 0.004));
}

function drawFace(ctx, head, r, facing, expr, color) {
  const [hx, hy] = head;
  const ex = hx + facing * r * 0.38;
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(1.5, r * 0.12);
  const eye = (dx) => {
    ctx.beginPath();
    if (expr === 'hurt') {
      const s = r * 0.12;
      ctx.moveTo(ex + dx - s, hy - r * 0.2 - s); ctx.lineTo(ex + dx + s, hy - r * 0.2 + s);
      ctx.moveTo(ex + dx + s, hy - r * 0.2 - s); ctx.lineTo(ex + dx - s, hy - r * 0.2 + s);
      ctx.stroke();
    } else {
      ctx.arc(ex + dx, hy - r * 0.18, r * (expr === 'surprised' ? 0.13 : 0.09), 0, Math.PI * 2);
      ctx.fill();
    }
  };
  eye(-r * 0.22);
  eye(r * 0.18);
  if (expr === 'angry') {
    ctx.beginPath();
    ctx.moveTo(ex - r * 0.4, hy - r * 0.45); ctx.lineTo(ex - r * 0.05, hy - r * 0.3);
    ctx.moveTo(ex + r * 0.35, hy - r * 0.45); ctx.lineTo(ex + r * 0.02, hy - r * 0.3);
    ctx.stroke();
  }
  ctx.beginPath();
  const my = hy + r * 0.3;
  if (expr === 'happy') ctx.arc(ex, my - r * 0.12, r * 0.3, 0.15 * Math.PI, 0.85 * Math.PI);
  else if (expr === 'sad' || expr === 'hurt') ctx.arc(ex, my + r * 0.18, r * 0.25, 1.15 * Math.PI, 1.85 * Math.PI);
  else if (expr === 'surprised') ctx.arc(ex, my, r * 0.14, 0, Math.PI * 2);
  else if (expr === 'angry') { ctx.moveTo(ex - r * 0.25, my + r * 0.05); ctx.lineTo(ex + r * 0.25, my - r * 0.03); }
  else return;
  ctx.stroke();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawBubble(ctx, text, head, r, W, H) {
  const fs = Math.max(14, H * 0.032);
  ctx.font = `600 ${fs}px system-ui, sans-serif`;
  const w = Math.min(W * 0.5, ctx.measureText(text).width + fs * 1.2);
  const h = fs * 1.8;
  const x = Math.max(6, Math.min(W - w - 6, head[0] - w / 2));
  const y = Math.max(6, head[1] - r * 2.4 - h);
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = '#1d1d1f';
  ctx.lineWidth = 2.5;
  roundRect(ctx, x, y, w, h, h / 2.5);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(head[0] - 8, y + h - 1);
  ctx.lineTo(head[0], head[1] - r * 1.3);
  ctx.lineTo(head[0] + 8, y + h - 1);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = '#1d1d1f';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x + w / 2, y + h / 2, w - fs * 0.6);
}

export function drawFigure(ctx, fig, state, W, H, groundY, opts = {}) {
  const j = skeleton(state, fig, W, H, groundY);
  const u = j.unit;
  const lw = fig.lineWidth * u * 0.9;
  ctx.save();
  ctx.globalAlpha = opts.alpha ?? 1;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  const seg = (pts, col) => {
    ctx.strokeStyle = col;
    ctx.lineWidth = lw;
    ctx.beginPath();
    ctx.moveTo(...pts[0]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(...pts[i]);
    ctx.stroke();
  };
  // A light outline keeps dark figures readable on dark skies.
  if (opts.sky && luminance(opts.sky) < 0.35 && luminance(fig.color) < 0.35) {
    ctx.save();
    ctx.lineWidth = lw + 5;
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    for (const pts of [[j.shoulder, j.lElbow, j.lHand], [j.hip, j.lKnee, j.lFoot], [j.hip, j.neck], [j.hip, j.rKnee, j.rFoot], [j.shoulder, j.rElbow, j.rHand]]) {
      ctx.beginPath();
      ctx.moveTo(...pts[0]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(...pts[i]);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(j.head[0], j.head[1], BONES.head * u + 2.5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
  const back = shade(fig.color, 0.18);
  seg([j.shoulder, j.lElbow, j.lHand], back);
  seg([j.hip, j.lKnee, j.lFoot], back);
  seg([j.hip, j.neck], fig.color);
  seg([j.hip, j.rKnee, j.rFoot], fig.color);
  seg([j.shoulder, j.rElbow, j.rHand], fig.color);
  const hr = BONES.head * u;
  ctx.lineWidth = lw;
  ctx.strokeStyle = fig.color;
  ctx.fillStyle = fig.headFill ? fig.color : '#fff';
  ctx.beginPath();
  ctx.arc(j.head[0], j.head[1], hr, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  if (!fig.headFill) drawFace(ctx, j.head, hr, state.facing, state.expr, fig.color);
  if (opts.joints) {
    for (const k of ['head', 'hip', 'lElbow', 'lHand', 'rElbow', 'rHand', 'lKnee', 'lFoot', 'rKnee', 'rFoot']) {
      ctx.beginPath();
      ctx.fillStyle = k === 'hip' ? '#ff006e' : k.startsWith('l') ? '#3a86ff' : '#fb5607';
      ctx.arc(j[k][0], j[k][1], Math.max(6, lw * 0.9), 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();
  if (state.say && opts.bubbles !== false) drawBubble(ctx, state.say, j.head, hr, W, H);
  return j;
}

function star(ctx, x, y, r1, r2, n) {
  ctx.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const a = (i * Math.PI) / n - Math.PI / 2;
    const r = i % 2 ? r2 : r1;
    ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
  }
  ctx.closePath();
}

function heart(ctx, x, y, s) {
  ctx.beginPath();
  ctx.moveTo(x, y + s * 0.3);
  ctx.bezierCurveTo(x, y, x - s * 0.5, y, x - s * 0.5, y + s * 0.3);
  ctx.bezierCurveTo(x - s * 0.5, y + s * 0.6, x, y + s * 0.8, x, y + s);
  ctx.bezierCurveTo(x, y + s * 0.8, x + s * 0.5, y + s * 0.6, x + s * 0.5, y + s * 0.3);
  ctx.bezierCurveTo(x + s * 0.5, y, x, y, x, y + s * 0.3);
  ctx.fill();
}

function drawProp(ctx, prop, st, W, H, groundY, skels) {
  if (!st.visible) return;
  const u = unitFor(H) * prop.size;
  let x = st.x * W, y = groundY * H - st.lift * FIGURE_HEIGHT * unitFor(H);
  let rot = rad(st.rot);
  const holder = st.holder && skels[st.holder];
  if (holder) {
    const hand = holder[`${st.hand}Hand`], elbow = holder[`${st.hand}Elbow`];
    [x, y] = hand;
    rot += Math.atan2(hand[1] - elbow[1], hand[0] - elbow[0]) - Math.PI / 2;
  }
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.fillStyle = prop.color;
  ctx.strokeStyle = '#1d1d1f';
  ctx.lineWidth = 2.5;
  const s = 12 * u;
  switch (prop.type) {
    case 'ball':
      ctx.beginPath(); ctx.arc(0, holder ? 0 : -s, s, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
    case 'rock':
      ctx.beginPath(); ctx.ellipse(0, holder ? 0 : -s * 0.7, s * 1.3, s * 0.8, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); break;
    case 'box':
      ctx.fillRect(-s * 1.4, holder ? -s * 1.4 : -s * 2.8, s * 2.8, s * 2.8);
      ctx.strokeRect(-s * 1.4, holder ? -s * 1.4 : -s * 2.8, s * 2.8, s * 2.8); break;
    case 'sword':
      ctx.fillStyle = '#c0c6cf'; ctx.fillRect(-s * 0.2, s * 0.4, s * 0.4, s * 4.2); ctx.strokeRect(-s * 0.2, s * 0.4, s * 0.4, s * 4.2);
      ctx.fillStyle = prop.color; ctx.fillRect(-s * 0.8, s * 0.2, s * 1.6, s * 0.35); ctx.fillRect(-s * 0.15, -s * 0.6, s * 0.3, s * 0.8); break;
    case 'bat':
      ctx.fillStyle = '#b5835a'; ctx.beginPath(); ctx.moveTo(-s * 0.15, -s * 0.3); ctx.lineTo(s * 0.15, -s * 0.3); ctx.lineTo(s * 0.45, s * 4); ctx.lineTo(-s * 0.45, s * 4); ctx.closePath(); ctx.fill(); ctx.stroke(); break;
    case 'flag':
      ctx.fillStyle = '#6b4f2a'; ctx.fillRect(-s * 0.1, -s * 0.4, s * 0.2, s * 5);
      ctx.fillStyle = prop.color; ctx.beginPath(); ctx.moveTo(0, s * 3.4); ctx.lineTo(s * 2.4, s * 3.9); ctx.lineTo(0, s * 4.5); ctx.fill(); break;
    case 'star':
      star(ctx, 0, holder ? 0 : -s, s * 1.2, s * 0.5, 5); ctx.fill(); ctx.stroke(); break;
    case 'heart':
      heart(ctx, 0, holder ? -s : -s * 2, s * 2); break;
    default:
  }
  ctx.restore();
}

function drawEffect(ctx, e, t, W, H, groundY) {
  const p = (t - e.t) / e.dur;
  if (p < 0 || p > 1) return;
  const x = e.x * W, y = groundY * H - e.lift * FIGURE_HEIGHT * unitFor(H);
  const s = H * 0.08;
  ctx.save();
  ctx.fillStyle = e.color;
  ctx.strokeStyle = e.color;
  ctx.globalAlpha = 1 - p * p;
  switch (e.type) {
    case 'impact':
      star(ctx, x, y, s * (0.5 + p), s * (0.25 + p * 0.4), 9); ctx.fill();
      ctx.strokeStyle = '#1d1d1f'; ctx.lineWidth = 2; ctx.stroke(); break;
    case 'burst':
      ctx.lineWidth = 6 * (1 - p) + 1;
      for (let i = 0; i < 3; i++) { ctx.beginPath(); ctx.arc(x, y, s * (0.3 + p * (1 + i * 0.6)), 0, Math.PI * 2); ctx.stroke(); }
      break;
    case 'speedlines': {
      const r = rand(Math.floor(e.t * 100) + 3);
      ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(30,30,30,0.6)';
      for (let i = 0; i < 9; i++) {
        const yy = y - s * 1.2 + r() * s * 2.2, len = s * (1 + r() * 1.5);
        ctx.beginPath(); ctx.moveTo(x - len - p * s, yy); ctx.lineTo(x - p * s * 2, yy); ctx.stroke();
      }
      break;
    }
    case 'text': {
      const sc = p < 0.2 ? p / 0.2 * 1.2 : 1.2 - Math.min(0.2, (p - 0.2));
      ctx.font = `900 ${Math.round(H * 0.09 * sc)}px Impact, "Arial Black", system-ui, sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = Math.max(3, H * 0.008); ctx.strokeStyle = '#1d1d1f';
      ctx.translate(x, y); ctx.rotate(-0.12);
      ctx.strokeText(e.text || 'POW!', 0, 0); ctx.fillText(e.text || 'POW!', 0, 0); break;
    }
    case 'dust': {
      const r = rand(Math.floor(e.t * 100) + 9);
      ctx.fillStyle = 'rgba(150,140,120,0.7)';
      for (let i = 0; i < 8; i++) {
        const dir = r() > 0.5 ? 1 : -1;
        ctx.beginPath(); ctx.arc(x + dir * (s * 0.2 + p * s * (0.5 + r())), groundY * H - p * s * 0.4 * r(), s * 0.18 * (1 + p), 0, Math.PI * 2); ctx.fill();
      }
      break;
    }
    case 'stars':
      for (let i = 0; i < 5; i++) {
        const a = p * Math.PI * 4 + (i * Math.PI * 2) / 5;
        star(ctx, x + Math.cos(a) * s * 0.7, y + Math.sin(a) * s * 0.25, s * 0.18, s * 0.08, 5); ctx.fill();
      }
      break;
    case 'hearts':
      ctx.fillStyle = '#ff4d6d';
      for (let i = 0; i < 4; i++) heart(ctx, x + (i - 1.5) * s * 0.5, y - p * s * 1.5 - i * s * 0.2, s * 0.35);
      break;
    case 'flash':
      ctx.globalAlpha = (1 - p) * 0.85; ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H); break;
    default:
  }
  ctx.restore();
}

function drawCaption(ctx, text, W, H) {
  const fs = Math.max(16, H * 0.042);
  ctx.save();
  ctx.font = `700 ${fs}px system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const w = Math.min(W * 0.92, ctx.measureText(text).width + fs * 1.4);
  ctx.fillStyle = 'rgba(0,0,0,0.62)';
  roundRect(ctx, (W - w) / 2, H - fs * 2.4, w, fs * 1.7, 10);
  ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.fillText(text, W / 2, H - fs * 1.55, w - fs);
  ctx.restore();
}

// Renders the whole scene at time t. Returns joint maps per figure id for hit testing.
export function renderScene(ctx, scene, t, opts = {}) {
  const { width: W, height: H } = ctx.canvas;
  const gy = scene.background.groundY;
  ctx.save();
  ctx.clearRect(0, 0, W, H);
  // Camera shake from active "shake" effects.
  for (const e of scene.effects) {
    if (e.type === 'shake' && t >= e.t && t <= e.t + e.dur) {
      const k = (1 - (t - e.t) / e.dur) * H * 0.015;
      ctx.translate(Math.sin(t * 90) * k, Math.cos(t * 73) * k);
    }
  }
  drawBackground(ctx, scene.background, W, H);
  if (opts.onion != null) {
    const fig = scene.figures[opts.onion];
    if (fig) {
      const ks = fig.keyframes;
      const prev = [...ks].reverse().find((k) => k.t < t - 1e-3);
      const next = ks.find((k) => k.t > t + 1e-3);
      for (const k of [prev, next]) if (k) drawFigure(ctx, fig, figureStateAt(fig, k.t), W, H, gy, { alpha: 0.18, bubbles: false, sky: scene.background.sky });
    }
  }
  const skels = {};
  scene.figures.forEach((fig, i) => {
    skels[fig.id] = drawFigure(ctx, fig, figureStateAt(fig, t), W, H, gy, { joints: opts.joints && (opts.selected == null || opts.selected === i), sky: scene.background.sky });
  });
  for (const prop of scene.props) drawProp(ctx, prop, propStateAt(prop, t), W, H, gy, skels);
  for (const e of scene.effects) if (e.type !== 'shake') drawEffect(ctx, e, t, W, H, gy);
  const cap = scene.captions.find((c) => t >= c.t && t <= c.end);
  if (cap) drawCaption(ctx, cap.text, W, H);
  ctx.restore();
  return skels;
}
