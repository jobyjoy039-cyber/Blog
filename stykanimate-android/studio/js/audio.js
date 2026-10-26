// Sound effects are synthesized with WebAudio (no sample files needed), music is
// generated per mood, and user-imported audio files can replace either.

const MIDI = (n) => 440 * Math.pow(2, (n - 69) / 12);

function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const hash = (s) => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };

export class AudioEngine {
  constructor() {
    this.ctx = null;
    this.custom = new Map(); // name -> AudioBuffer
    this.live = null; // {bus, nodes}
  }

  ensure() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AC();
      this.master = this.ctx.createDynamicsCompressor();
      this.master.threshold.value = -14; this.master.ratio.value = 4;
      this.out = this.ctx.createGain(); this.out.gain.value = 0.9;
      this.master.connect(this.out); this.out.connect(this.ctx.destination);
      this.recordDest = this.ctx.createMediaStreamDestination ? this.ctx.createMediaStreamDestination() : null;
      if (this.recordDest) this.out.connect(this.recordDest);
      const len = this.ctx.sampleRate * 2;
      this.noise = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
      const d = this.noise.getChannelData(0); for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  }

  async addCustom(name, arrayBuffer) {
    this.ensure();
    const buf = await this.ctx.decodeAudioData(arrayBuffer.slice(0));
    this.custom.set(name, buf);
    return buf;
  }

  // ---- low level helpers (all take an absolute start time `w` and a destination) ----
  tone(dest, w, { type = 'sine', f0 = 440, f1 = null, dur = 0.2, vol = 0.5, attack = 0.005, curve = 'exp', detune = 0 }) {
    const c = this.ctx, o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, w); o.detune.value = detune;
    if (f1) { if (curve === 'exp') o.frequency.exponentialRampToValueAtTime(Math.max(1, f1), w + dur); else o.frequency.linearRampToValueAtTime(f1, w + dur); }
    g.gain.setValueAtTime(0.0001, w); g.gain.exponentialRampToValueAtTime(Math.max(0.0002, vol), w + attack); g.gain.exponentialRampToValueAtTime(0.0001, w + dur);
    o.connect(g); g.connect(dest); o.start(w); o.stop(w + dur + 0.05);
    return o;
  }
  burst(dest, w, { dur = 0.2, vol = 0.5, type = 'lowpass', f0 = 1000, f1 = null, q = 1, attack = 0.002 }) {
    const c = this.ctx, s = c.createBufferSource(), fl = c.createBiquadFilter(), g = c.createGain();
    s.buffer = this.noise; fl.type = type; fl.Q.value = q; fl.frequency.setValueAtTime(f0, w);
    if (f1) fl.frequency.exponentialRampToValueAtTime(Math.max(20, f1), w + dur);
    g.gain.setValueAtTime(0.0001, w); g.gain.exponentialRampToValueAtTime(Math.max(0.0002, vol), w + attack); g.gain.exponentialRampToValueAtTime(0.0001, w + dur);
    s.connect(fl); fl.connect(g); g.connect(dest); s.start(w, Math.random()); s.stop(w + dur + 0.05);
    return s;
  }

  /** Schedule one named sound effect at absolute time w. */
  sfx(name, dest, w, vol = 1) {
    const T = (o) => this.tone(dest, w + (o.at || 0), { ...o, vol: (o.vol ?? 0.5) * vol });
    const N = (o) => this.burst(dest, w + (o.at || 0), { ...o, vol: (o.vol ?? 0.5) * vol });
    if (name.startsWith('custom:')) {
      const buf = this.custom.get(name.slice(7));
      if (!buf) return;
      const s = this.ctx.createBufferSource(), g = this.ctx.createGain();
      s.buffer = buf; g.gain.value = vol; s.connect(g); g.connect(dest); s.start(w);
      return;
    }
    switch (name) {
      case 'punch': N({ dur: 0.12, vol: 0.9, f0: 2500, f1: 300 }); T({ type: 'sine', f0: 160, f1: 50, dur: 0.18, vol: 0.9 }); break;
      case 'kick': N({ dur: 0.15, vol: 0.6, f0: 1200, f1: 200 }); T({ type: 'triangle', f0: 120, f1: 40, dur: 0.25, vol: 1 }); break;
      case 'whoosh': N({ dur: 0.35, vol: 0.5, type: 'bandpass', f0: 400, f1: 2400, q: 2, attack: 0.15 }); break;
      case 'swoosh': N({ dur: 0.22, vol: 0.5, type: 'bandpass', f0: 3000, f1: 600, q: 3, attack: 0.06 }); break;
      case 'jump': T({ type: 'square', f0: 220, f1: 660, dur: 0.18, vol: 0.25 }); break;
      case 'land': T({ type: 'sine', f0: 110, f1: 40, dur: 0.15, vol: 0.8 }); N({ dur: 0.1, vol: 0.3, f0: 800 }); break;
      case 'footstep': N({ dur: 0.06, vol: 0.35, f0: 1500, f1: 400 }); T({ f0: 90, f1: 50, dur: 0.06, vol: 0.3 }); break;
      case 'explosion': N({ dur: 1.6, vol: 1, f0: 1800, f1: 60, attack: 0.01 }); T({ type: 'sine', f0: 90, f1: 25, dur: 1.2, vol: 1 }); break;
      case 'laser': T({ type: 'sawtooth', f0: 1800, f1: 200, dur: 0.25, vol: 0.25 }); break;
      case 'pop': T({ type: 'sine', f0: 400, f1: 1200, dur: 0.07, vol: 0.6 }); break;
      case 'ding': T({ f0: 1318, dur: 1.2, vol: 0.5 }); T({ f0: 2637, dur: 0.6, vol: 0.15 }); break;
      case 'coin': T({ type: 'square', f0: 988, dur: 0.08, vol: 0.2, curve: 'lin' }); T({ at: 0.08, type: 'square', f0: 1319, dur: 0.35, vol: 0.2 }); break;
      case 'magic': for (let i = 0; i < 8; i++) T({ at: i * 0.05, f0: MIDI(76 + [0, 4, 7, 11, 12, 16, 19, 24][i]), dur: 0.4, vol: 0.15 }); N({ dur: 0.6, vol: 0.12, type: 'highpass', f0: 6000 }); break;
      case 'zap': for (let i = 0; i < 4; i++) T({ at: i * 0.04, type: 'sawtooth', f0: 1200 - i * 200, f1: 100, dur: 0.08, vol: 0.2 }); break;
      case 'crash': N({ dur: 0.9, vol: 0.8, type: 'highpass', f0: 1500, attack: 0.002 }); T({ type: 'square', f0: 140, f1: 60, dur: 0.3, vol: 0.3 }); break;
      case 'splash': N({ dur: 0.7, vol: 0.6, type: 'bandpass', f0: 1200, f1: 400, q: 0.7, attack: 0.02 }); break;
      case 'boing': { const o = T({ type: 'sine', f0: 180, f1: 420, dur: 0.5, vol: 0.5, curve: 'lin' }); const lfo = this.ctx.createOscillator(), lg = this.ctx.createGain(); lfo.frequency.value = 14; lg.gain.value = 60; lfo.connect(lg); lg.connect(o.frequency); lfo.start(w); lfo.stop(w + 0.55); break; }
      case 'bell': [1, 2.76, 5.4].forEach((m, i) => T({ f0: 523 * m, dur: 2 - i * 0.5, vol: 0.3 / (i + 1) })); break;
      case 'cheer': N({ dur: 2, vol: 0.4, type: 'bandpass', f0: 1500, q: 0.5, attack: 0.3 }); for (let i = 0; i < 6; i++) T({ at: Math.random() * 0.8, type: 'triangle', f0: 600 + Math.random() * 500, f1: 900 + Math.random() * 500, dur: 0.3, vol: 0.05 }); break;
      case 'alarm': for (let i = 0; i < 4; i++) T({ at: i * 0.4, type: 'square', f0: 880, f1: 660, dur: 0.38, vol: 0.18, curve: 'lin' }); break;
      case 'heartbeat': for (let i = 0; i < 2; i++) { T({ at: i * 0.8, f0: 70, f1: 40, dur: 0.15, vol: 0.9 }); T({ at: i * 0.8 + 0.2, f0: 60, f1: 35, dur: 0.15, vol: 0.7 }); } break;
      case 'thunder': N({ dur: 2.5, vol: 1, f0: 400, f1: 50, attack: 0.05 }); N({ at: 0.1, dur: 0.3, vol: 0.6, type: 'highpass', f0: 2000 }); break;
      case 'wind': N({ dur: 3, vol: 0.35, type: 'bandpass', f0: 500, f1: 900, q: 3, attack: 1 }); break;
      case 'glass': for (let i = 0; i < 6; i++) T({ at: i * 0.03 + Math.random() * 0.05, f0: 2000 + Math.random() * 3000, dur: 0.3, vol: 0.12 }); N({ dur: 0.4, vol: 0.4, type: 'highpass', f0: 4000 }); break;
      case 'click': N({ dur: 0.02, vol: 0.5, type: 'highpass', f0: 3000 }); break;
      case 'drumroll': for (let i = 0; i < 30; i++) N({ at: i * 0.05, dur: 0.06, vol: 0.15 + i * 0.012, f0: 2500, f1: 800 }); N({ at: 1.55, dur: 0.8, vol: 0.6, type: 'highpass', f0: 3000 }); break;
      case 'sadtrombone': [[58, 0], [57, 0.45], [56, 0.9], [55, 1.35]].forEach(([n, at], i) => T({ at, type: 'sawtooth', f0: MIDI(n), f1: i === 3 ? MIDI(n) * 0.94 : null, dur: i === 3 ? 1.1 : 0.42, vol: 0.18, attack: 0.04, curve: 'lin' })); break;
      case 'slidewhistle': T({ type: 'sine', f0: 400, f1: 1600, dur: 0.6, vol: 0.35, curve: 'lin', attack: 0.05 }); break;
      case 'powerup': for (let i = 0; i < 10; i++) T({ at: i * 0.05, type: 'square', f0: MIDI(60 + i * 2), dur: 0.08, vol: 0.12 }); break;
      case 'gameover': [67, 64, 60, 55].forEach((n, i) => T({ at: i * 0.3, type: 'triangle', f0: MIDI(n), dur: 0.35, vol: 0.3 })); break;
      case 'swordclash': [3100, 4700, 6200].forEach((f) => T({ f0: f, dur: 0.6, vol: 0.12, type: 'triangle' })); N({ dur: 0.15, vol: 0.5, type: 'highpass', f0: 3000 }); break;
      case 'gasp': N({ dur: 0.35, vol: 0.4, type: 'bandpass', f0: 1800, f1: 2600, q: 4, attack: 0.08 }); break;
      case 'tada': [[60, 0], [64, 0], [67, 0], [72, 0.18], [76, 0.18], [79, 0.18]].forEach(([n, at]) => T({ at, type: 'sawtooth', f0: MIDI(n), dur: at ? 1 : 0.16, vol: 0.08, attack: 0.01 })); break;
      default: T({ f0: 600, dur: 0.1, vol: 0.3 });
    }
  }

  preview(name) {
    this.ensure();
    const g = this.ctx.createGain(); g.gain.value = 0.9; g.connect(this.master);
    this.sfx(name, g, this.ctx.currentTime + 0.02, 1);
  }

  /** Schedule generated music covering [from, to) scene seconds; scene time `from` plays at audio time w0. */
  music(scene, dest, w0, from, to) {
    const mood = scene.music.mood;
    if (mood === 'none') return;
    const M = MOODS[mood] || MOODS.happy;
    const bpm = scene.music.bpm || M.bpm;
    const beat = 60 / bpm, bar = beat * 4;
    const r = rng(hash(scene.title + mood));
    const scale = M.scale.map((s) => s + M.root);
    const chordNotes = (deg) => [0, 2, 4, 6].map((k) => { const i = deg + k; return scale[i % 7] + 12 * Math.floor(i / 7); });
    const melody = [];
    for (let b = 0; b < 64; b++) { const notes = []; for (let s = 0; s < 8; s++) notes.push(r() < M.leadDensity ? Math.floor(r() * 5) : -1); melody.push(notes); }
    const firstBar = Math.floor(from / bar);
    for (let b = firstBar; b * bar < to; b++) {
      const deg = M.prog[b % M.prog.length];
      const ch = chordNotes(deg);
      const at = (s) => w0 + (b * bar + s - from);
      const ok = (s) => b * bar + s >= from - 0.001 && b * bar + s < to;
      // pad
      if (M.pad && ok(0)) ch.slice(0, M.seventh ? 4 : 3).forEach((n) => this.tone(dest, at(0), { type: M.pad, f0: MIDI(n), dur: bar * 1.02, vol: 0.05, attack: 0.25 * bar }));
      // bass
      M.bass.forEach((step, i) => { if (step < 0) return; const s = i * beat / 2; if (ok(s)) this.tone(dest, at(s), { type: M.bassWave, f0: MIDI(ch[0] - 24 + (step === 1 ? 7 : step === 2 ? 12 : 0)), dur: beat * 0.45, vol: 0.22, attack: 0.01 }); });
      // arpeggio
      if (M.arp) for (let s = 0; s < 8; s++) { const st = s * beat / 2; if (ok(st)) this.tone(dest, at(st), { type: M.arpWave, f0: MIDI(ch[M.arp[s % M.arp.length]] + 12), dur: beat * 0.4, vol: 0.06 }); }
      // lead
      if (M.leadDensity > 0) melody[b % 64].forEach((nIdx, s) => { if (nIdx < 0) return; const st = s * beat / 2; if (ok(st)) { const n = scale[(deg + nIdx * 2) % 7] + 12 + 12 * Math.floor((deg + nIdx * 2) / 7); this.tone(dest, at(st), { type: M.leadWave, f0: MIDI(n + 12 * (M.leadOct || 0)), dur: beat * 0.5, vol: 0.07, attack: 0.02 }); } });
      // drums: 16 steps
      for (let s = 0; s < 16; s++) {
        const st = s * beat / 4; if (!ok(st)) continue;
        if (M.kick[s] === 'x') { this.tone(dest, at(st), { f0: 150, f1: 45, dur: 0.22, vol: 0.55 }); }
        if (M.snare[s] === 'x') { this.burst(dest, at(st), { dur: 0.16, vol: 0.28, type: 'highpass', f0: 1500 }); this.tone(dest, at(st), { type: 'triangle', f0: 200, f1: 120, dur: 0.08, vol: 0.15 }); }
        if (M.hat[s] === 'x') this.burst(dest, at(st), { dur: 0.04, vol: 0.08, type: 'highpass', f0: 7000 });
      }
    }
  }

  /** Start playback from scene time `from`. Returns a handle with stop(). */
  play(scene, from = 0) {
    this.stop();
    const ctx = this.ensure();
    const bus = ctx.createGain(); bus.connect(this.master);
    const musicBus = ctx.createGain(); musicBus.gain.value = scene.music.volume; musicBus.connect(bus);
    const sfxBus = ctx.createGain(); sfxBus.gain.value = scene.sfxVolume ?? 1; sfxBus.connect(bus);
    const w0 = ctx.currentTime + 0.08;
    const to = scene.duration;
    if (scene.music.custom && this.custom.has(scene.music.custom)) {
      const s = ctx.createBufferSource(); s.buffer = this.custom.get(scene.music.custom); s.loop = true; s.connect(musicBus);
      s.start(w0, from % s.buffer.duration); s.stop(w0 + (to - from));
    } else {
      // Schedule music in chunks so long scenes don't create every node up front.
      let next = from;
      const chunk = () => {
        if (!this.live || this.live.bus !== bus || next >= to) return;
        const end = Math.min(to, next + 8);
        this.music(scene, musicBus, w0 + (next - from), next, end);
        next = end;
      };
      this.live = { bus };
      chunk(); chunk();
      this.live.timer = setInterval(chunk, 3000);
    }
    for (const c of scene.sfx) if (c.t >= from - 0.01 && c.t < to) this.sfx(c.sound, sfxBus, w0 + (c.t - from), c.volume);
    this.live = { ...(this.live || {}), bus, w0, from };
    return this.live;
  }

  /** Scene time of the running playback, or null. */
  position() {
    if (!this.live) return null;
    return this.live.from + Math.max(0, this.ctx.currentTime - this.live.w0);
  }

  stop() {
    if (!this.live) return;
    clearInterval(this.live.timer);
    const bus = this.live.bus;
    try { bus.gain.setValueAtTime(bus.gain.value, this.ctx.currentTime); bus.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 0.03); } catch { /* closed */ }
    setTimeout(() => bus.disconnect(), 60);
    this.live = null;
  }
}

const S = (k, sn, h) => ({ kick: k, snare: sn, hat: h });
const MAJOR = [0, 2, 4, 5, 7, 9, 11], MINOR = [0, 2, 3, 5, 7, 8, 10], HARM = [0, 2, 3, 5, 7, 8, 11];
export const MOODS = {
  happy: { root: 60, scale: MAJOR, bpm: 120, prog: [0, 4, 5, 3], pad: 'triangle', bassWave: 'triangle', bass: [0, -1, 1, -1, 0, -1, 1, -1], arp: [0, 1, 2, 1], arpWave: 'square', leadWave: 'square', leadDensity: 0.35, ...S('x---x---x---x---', '----x-------x---', 'x-x-x-x-x-x-x-x-') },
  epic: { root: 50, scale: MINOR, bpm: 140, prog: [0, 5, 2, 6], pad: 'sawtooth', bassWave: 'sawtooth', bass: [0, 0, 0, 0, 0, 0, 2, 0], arp: [0, 1, 2, 3, 2, 1], arpWave: 'sawtooth', leadWave: 'sawtooth', leadDensity: 0.25, ...S('x--x--x-x--x--x-', '----x-------x--x', 'x-xxx-xxx-xxx-xx') },
  tense: { root: 52, scale: HARM, bpm: 100, prog: [0, 0, 1, 0], pad: 'sawtooth', bassWave: 'square', bass: [0, 0, 0, 0, 0, 0, 0, 0], arp: [0, 2, 0, 1], arpWave: 'triangle', leadWave: 'sine', leadDensity: 0.08, ...S('x-------x-------', '----------------', '--x---x---x---x-') },
  calm: { root: 62, scale: MAJOR, bpm: 78, prog: [0, 3, 5, 4], seventh: true, pad: 'sine', bassWave: 'sine', bass: [0, -1, -1, -1, 1, -1, -1, -1], arp: [0, 1, 2, 3], arpWave: 'sine', leadWave: 'triangle', leadDensity: 0.18, ...S('----------------', '----------------', '----------------') },
  funny: { root: 60, scale: MAJOR, bpm: 132, prog: [0, 3, 4, 0], pad: null, bassWave: 'square', bass: [0, -1, 1, -1, 0, -1, 1, -1], arp: [2, 1], arpWave: 'square', leadWave: 'square', leadDensity: 0.45, leadOct: 1, ...S('x---x---x---x---', '--x---x---x---x-', '----------------') },
  sad: { root: 57, scale: MINOR, bpm: 68, prog: [0, 3, 5, 4], seventh: true, pad: 'sine', bassWave: 'sine', bass: [0, -1, -1, -1, -1, -1, -1, -1], arp: [0, 2, 1, 2], arpWave: 'triangle', leadWave: 'sine', leadDensity: 0.15, ...S('----------------', '----------------', '----------------') },
  action: { root: 52, scale: MINOR, bpm: 160, prog: [0, 0, 5, 6], pad: null, bassWave: 'sawtooth', bass: [0, 0, 2, 0, 0, 0, 2, 0], arp: [0, 1, 2, 1], arpWave: 'square', leadWave: 'sawtooth', leadDensity: 0.3, ...S('x-x---x-x-x---x-', '----x-------x---', 'xxxxxxxxxxxxxxxx') },
  spooky: { root: 50, scale: HARM, bpm: 90, prog: [0, 1, 0, 4], seventh: true, pad: 'triangle', bassWave: 'sine', bass: [0, -1, -1, 0, -1, -1, 0, -1], arp: null, arpWave: 'sine', leadWave: 'sine', leadDensity: 0.12, leadOct: 1, ...S('x---------------', '----------------', '------x-------x-') },
  heroic: { root: 55, scale: MAJOR, bpm: 112, prog: [0, 4, 5, 3], pad: 'sawtooth', bassWave: 'triangle', bass: [0, -1, 0, 1, 0, -1, 0, 1], arp: [0, 1, 2, 3], arpWave: 'triangle', leadWave: 'sawtooth', leadDensity: 0.22, ...S('x-----x-x-------', '----x-------x---', 'x---x---x---x---') },
  chill: { root: 58, scale: MAJOR, bpm: 84, prog: [1, 4, 0, 5], seventh: true, pad: 'sine', bassWave: 'sine', bass: [0, -1, -1, 1, -1, -1, 0, -1], arp: null, arpWave: 'sine', leadWave: 'triangle', leadDensity: 0.15, ...S('x-----x---x-----', '----x-------x---', 'x-x-x-x-x-x-x-x-') },
};
