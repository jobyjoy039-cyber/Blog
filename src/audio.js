// Web Audio engine: synthesized sound effects, mood-based generated music and imported audio files.

const MOODS = {
  //        root  scale             chords (scale degrees, one per bar)   drums   lead style
  epic:   { root: 45, scale: 'minor', prog: [0, 5, 2, 6], drums: 'big', lead: 'pad', bass: 'eighths' },
  happy:  { root: 48, scale: 'major', prog: [0, 4, 5, 3], drums: 'pop', lead: 'arp', bass: 'quarters' },
  tense:  { root: 40, scale: 'minor', prog: [0, 0, 1, 0], drums: 'tick', lead: 'pulse', bass: 'eighths' },
  calm:   { root: 50, scale: 'major', prog: [0, 3, 5, 4], drums: 'none', lead: 'arpSoft', bass: 'whole' },
  silly:  { root: 53, scale: 'major', prog: [0, 4, 0, 4], drums: 'silly', lead: 'bounce', bass: 'oompah' },
  sad:    { root: 45, scale: 'minor', prog: [0, 3, 5, 4], drums: 'none', lead: 'arpSoft', bass: 'whole' },
  action: { root: 40, scale: 'minor', prog: [0, 5, 6, 4], drums: 'drive', lead: 'pulse', bass: 'sixteenths' },
};
const SCALES = { major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10] };
const midiHz = (m) => 440 * Math.pow(2, (m - 69) / 12);

function chordNotes(mood, degree) {
  const sc = SCALES[mood.scale];
  return [0, 2, 4].map((step) => {
    const i = degree + step;
    return mood.root + sc[i % 7] + 12 * Math.floor(i / 7);
  });
}

// Small IndexedDB wrapper so imported sounds survive app restarts.
const DB = 'stickai-audio';
function db() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore('files');
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
async function dbOp(mode, fn) {
  const d = await db();
  return new Promise((res, rej) => {
    const tx = d.transaction('files', mode);
    const req = fn(tx.objectStore('files'));
    tx.oncomplete = () => res(req && req.result);
    tx.onerror = () => rej(tx.error);
  });
}

export class AudioEngine {
  constructor() {
    this.ctx = null;
    this.buffers = new Map(); // "custom:name" or "music:name" -> AudioBuffer
    this.session = null;
  }

  ensure() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.9;
      const comp = this.ctx.createDynamicsCompressor();
      this.master.connect(comp);
      comp.connect(this.ctx.destination);
      this.out = comp;
      this.noise = this.ctx.createBuffer(1, this.ctx.sampleRate * 2, this.ctx.sampleRate);
      const d = this.noise.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  }

  // Returns a MediaStream carrying everything the engine plays, for video export.
  recordStream() {
    this.ensure();
    if (!this.recDest) {
      this.recDest = this.ctx.createMediaStreamDestination();
      this.out.connect(this.recDest);
    }
    return this.recDest.stream;
  }

  async loadSaved() {
    try {
      const keys = await dbOp('readonly', (s) => s.getAllKeys());
      for (const k of keys || []) {
        const data = await dbOp('readonly', (s) => s.get(k));
        if (data) await this.decode(k, data, false);
      }
    } catch (e) {
      console.warn('Could not restore saved audio', e);
    }
    return this.list();
  }

  list() {
    const custom = [], music = [];
    for (const k of this.buffers.keys()) (k.startsWith('music:') ? music : custom).push(k);
    return { custom, music };
  }

  async decode(key, arrayBuffer, persist = true) {
    this.ensure();
    const buf = await this.ctx.decodeAudioData(arrayBuffer.slice(0));
    this.buffers.set(key, buf);
    if (persist) {
      try { await dbOp('readwrite', (s) => s.put(arrayBuffer, key)); } catch (e) { console.warn(e); }
    }
    return buf;
  }

  async importFile(file, kind) {
    const name = file.name.replace(/\.[^.]+$/, '').replace(/[^\w\- ]+/g, '').slice(0, 40) || 'sound';
    const key = `${kind}:${name}`;
    await this.decode(key, await file.arrayBuffer());
    return key;
  }

  async remove(key) {
    this.buffers.delete(key);
    try { await dbOp('readwrite', (s) => s.delete(key)); } catch (e) { console.warn(e); }
  }

  env(dest, when, attack, hold, release, peak = 1) {
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.0001, when);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), when + attack);
    g.gain.setValueAtTime(Math.max(0.0002, peak), when + attack + hold);
    g.gain.exponentialRampToValueAtTime(0.0001, when + attack + hold + release);
    g.connect(dest);
    return g;
  }

  osc(type, freq, when, dur, dest, freqEnd) {
    const o = this.ctx.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(freq, when);
    if (freqEnd) o.frequency.exponentialRampToValueAtTime(freqEnd, when + dur);
    o.connect(dest);
    o.start(when);
    o.stop(when + dur + 0.05);
    return o;
  }

  noiseSrc(when, dur, dest, filterType, freq, freqEnd, q = 1) {
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    const f = this.ctx.createBiquadFilter();
    f.type = filterType;
    f.frequency.setValueAtTime(freq, when);
    if (freqEnd) f.frequency.exponentialRampToValueAtTime(freqEnd, when + dur);
    f.Q.value = q;
    src.connect(f);
    f.connect(dest);
    src.start(when, Math.random());
    src.stop(when + dur + 0.05);
    return src;
  }

  // Synthesizes one named sound effect at audio-context time `when`.
  sfx(name, when, dest, vol = 1) {
    const c = this.ctx;
    if (name.startsWith('custom:')) {
      const buf = this.buffers.get(name);
      if (!buf) return;
      const s = c.createBufferSource();
      const g = c.createGain();
      g.gain.value = vol;
      s.buffer = buf;
      s.connect(g);
      g.connect(dest);
      s.start(when);
      return;
    }
    const E = (a, h, r, p) => this.env(dest, when, a, h, r, p * vol);
    switch (name) {
      case 'punch':
        this.osc('sine', 160, when, 0.15, E(0.002, 0.02, 0.15, 1), 45);
        this.noiseSrc(when, 0.08, E(0.001, 0.01, 0.08, 0.7), 'lowpass', 2500, 400);
        break;
      case 'kick':
        this.osc('triangle', 220, when, 0.12, E(0.002, 0.01, 0.12, 0.8), 60);
        this.noiseSrc(when, 0.12, E(0.001, 0.02, 0.1, 0.6), 'bandpass', 1800, 600, 2);
        break;
      case 'whoosh':
        this.noiseSrc(when, 0.45, E(0.15, 0.05, 0.25, 0.6), 'bandpass', 300, 3000, 3);
        break;
      case 'jump':
        this.osc('square', 220, when, 0.25, E(0.005, 0.1, 0.15, 0.25), 880);
        break;
      case 'land':
        this.osc('sine', 120, when, 0.25, E(0.002, 0.03, 0.22, 1), 35);
        this.noiseSrc(when, 0.2, E(0.002, 0.02, 0.18, 0.4), 'lowpass', 900, 200);
        break;
      case 'step':
        this.noiseSrc(when, 0.06, E(0.001, 0.01, 0.05, 0.35), 'bandpass', 1200, 500, 1.5);
        break;
      case 'explosion':
        this.noiseSrc(when, 1.6, E(0.005, 0.15, 1.4, 1), 'lowpass', 3000, 80);
        this.osc('sine', 90, when, 0.8, E(0.005, 0.1, 0.7, 1), 25);
        break;
      case 'pop':
        this.osc('sine', 600, when, 0.08, E(0.001, 0.01, 0.07, 0.7), 1400);
        break;
      case 'ding':
        [1, 2.76, 5.4].forEach((m, i) => this.osc('sine', 1046 * m, when, 1.2, E(0.002, 0.02, 1.2 / (i + 1), 0.4 / (i + 1))));
        break;
      case 'boing': {
        const g = E(0.005, 0.2, 0.4, 0.5);
        const o = this.osc('sine', 180, when, 0.6, g, 420);
        const lfo = c.createOscillator();
        const lg = c.createGain();
        lfo.frequency.value = 18;
        lg.gain.value = 40;
        lfo.connect(lg);
        lg.connect(o.frequency);
        lfo.start(when);
        lfo.stop(when + 0.65);
        break;
      }
      case 'laser':
        this.osc('sawtooth', 1800, when, 0.3, E(0.002, 0.05, 0.25, 0.25), 150);
        break;
      case 'crash':
        this.noiseSrc(when, 1, E(0.002, 0.05, 0.9, 0.7), 'highpass', 3000);
        this.noiseSrc(when, 0.3, E(0.002, 0.02, 0.25, 0.6), 'bandpass', 800, 300, 1);
        break;
      case 'coin':
        this.osc('square', 988, when, 0.08, E(0.001, 0.06, 0.02, 0.2));
        this.osc('square', 1319, when + 0.08, 0.35, this.env(dest, when + 0.08, 0.001, 0.1, 0.3, 0.2 * vol));
        break;
      case 'splat':
        this.noiseSrc(when, 0.25, E(0.002, 0.03, 0.2, 0.8), 'lowpass', 1200, 150);
        this.osc('sine', 300, when, 0.15, E(0.002, 0.02, 0.12, 0.4), 80);
        break;
      case 'clang':
        [523, 1187, 1753, 2489].forEach((f) => this.osc('triangle', f, when, 0.9, E(0.001, 0.01, 0.9, 0.18)));
        this.noiseSrc(when, 0.05, E(0.001, 0.005, 0.05, 0.5), 'highpass', 4000);
        break;
      case 'zap':
        for (let i = 0; i < 4; i++) this.osc('square', 300 + Math.random() * 900, when + i * 0.04, 0.05, this.env(dest, when + i * 0.04, 0.001, 0.02, 0.03, 0.25 * vol));
        break;
      case 'drumroll':
        for (let i = 0; i < 24; i++) this.noiseSrc(when + i * 0.045, 0.05, this.env(dest, when + i * 0.045, 0.001, 0.005, 0.05, (0.2 + i / 60) * vol), 'bandpass', 1800, null, 1);
        break;
      case 'tada':
        [[523, 0], [659, 0.12], [784, 0.24], [1046, 0.36]].forEach(([f, d]) =>
          this.osc('sawtooth', f, when + d, 0.9 - d, this.env(dest, when + d, 0.005, 0.2, 0.6, 0.12 * vol)));
        break;
      case 'scream': {
        const g = E(0.05, 0.6, 0.3, 0.25);
        const o = this.osc('sawtooth', 700, when, 0.95, g, 500);
        const lfo = c.createOscillator();
        const lg = c.createGain();
        lfo.frequency.value = 7;
        lg.gain.value = 60;
        lfo.connect(lg);
        lg.connect(o.frequency);
        lfo.start(when);
        lfo.stop(when + 1);
        break;
      }
      case 'laugh':
        for (let i = 0; i < 5; i++) this.osc('triangle', 420 - i * 20, when + i * 0.14, 0.1, this.env(dest, when + i * 0.14, 0.005, 0.05, 0.06, 0.35 * vol), 300 - i * 20);
        break;
      default:
    }
  }

  preview(name) {
    this.ensure();
    this.sfx(name, this.ctx.currentTime + 0.02, this.master, 1);
  }

  // Schedules every note of generated music between song times [from, to) onto `dest`.
  scheduleMusic(music, from, to, start, dest) {
    const mood = MOODS[music.mood];
    if (!mood) return;
    const beat = 60 / music.bpm;
    const bar = beat * 4;
    const at = (songT) => start + (songT - from);
    const note = (type, midi, t, dur, peak, filt) => {
      if (t + dur < from || t >= to) return;
      const when = Math.max(start, at(t));
      let d = dest;
      if (filt) {
        const f = this.ctx.createBiquadFilter();
        f.type = 'lowpass';
        f.frequency.value = filt;
        f.connect(dest);
        d = f;
      }
      this.osc(type, midiHz(midi), when, dur, this.env(d, when, Math.min(0.03, dur / 4), dur * 0.4, dur * 0.6, peak));
    };
    const drum = (kind, t) => {
      if (t < from || t >= to) return;
      const when = at(t);
      if (kind === 'k') this.osc('sine', 150, when, 0.3, this.env(dest, when, 0.002, 0.02, 0.28, 0.9), 40);
      if (kind === 's') {
        this.noiseSrc(when, 0.18, this.env(dest, when, 0.001, 0.02, 0.16, 0.35), 'highpass', 1500);
        this.osc('triangle', 200, when, 0.1, this.env(dest, when, 0.001, 0.01, 0.1, 0.3), 120);
      }
      if (kind === 'h') this.noiseSrc(when, 0.04, this.env(dest, when, 0.001, 0.005, 0.035, 0.15), 'highpass', 7000);
      if (kind === 'w') this.osc('sine', 900, when, 0.05, this.env(dest, when, 0.001, 0.005, 0.05, 0.3), 700);
      if (kind === 't') this.osc('sine', 110, when, 0.35, this.env(dest, when, 0.002, 0.05, 0.3, 0.6), 70);
    };
    const firstBar = Math.max(0, Math.floor(from / bar));
    for (let b = firstBar; b * bar < to; b++) {
      const t0 = b * bar;
      const ch = chordNotes(mood, mood.prog[b % mood.prog.length]);
      const root = ch[0] - 12;
      // Bass
      if (mood.bass === 'whole') note('sine', root, t0, bar * 0.95, 0.35);
      if (mood.bass === 'quarters') for (let i = 0; i < 4; i++) note('triangle', root, t0 + i * beat, beat * 0.8, 0.35);
      if (mood.bass === 'eighths') for (let i = 0; i < 8; i++) note('sawtooth', root, t0 + i * beat / 2, beat * 0.4, 0.18, 600);
      if (mood.bass === 'sixteenths') for (let i = 0; i < 16; i++) note('sawtooth', root + (i % 8 === 7 ? 7 : 0), t0 + i * beat / 4, beat * 0.2, 0.16, 900);
      if (mood.bass === 'oompah') for (let i = 0; i < 4; i++) note('square', i % 2 ? ch[2] - 12 : root, t0 + i * beat, beat * 0.3, 0.12, 1200);
      // Harmony / lead
      if (mood.lead === 'pad') ch.forEach((m) => { note('sawtooth', m, t0, bar, 0.06, 1400); note('sawtooth', m + 0.08, t0, bar, 0.05, 1400); });
      if (mood.lead === 'arp' || mood.lead === 'arpSoft') {
        const soft = mood.lead === 'arpSoft';
        const seq = [ch[0], ch[1], ch[2], ch[1] + 12, ch[2], ch[1], ch[0] + 12, ch[2]];
        seq.forEach((m, i) => note(soft ? 'sine' : 'square', m + 12, t0 + i * beat / 2, beat * (soft ? 0.9 : 0.35), soft ? 0.12 : 0.06, soft ? null : 2500));
        if (soft) ch.forEach((m) => note('triangle', m, t0, bar, 0.05));
      }
      if (mood.lead === 'pulse') for (let i = 0; i < 8; i++) note('square', ch[i % 3] + 12, t0 + i * beat / 2, beat * 0.2, 0.05, 1800);
      if (mood.lead === 'bounce') [0, 1.5, 2, 3].forEach((p, i) => note('square', ch[i % 3] + 12, t0 + p * beat, beat * 0.25, 0.07, 2600));
      // Drums
      for (let i = 0; i < 4; i++) {
        const t = t0 + i * beat;
        switch (mood.drums) {
          case 'big': if (i % 2 === 0) drum('k', t); else drum('s', t); if (i === 3) drum('t', t + beat / 2); break;
          case 'pop': if (i % 2 === 0) drum('k', t); else drum('s', t); drum('h', t); drum('h', t + beat / 2); break;
          case 'drive': drum('k', t); if (i % 2) drum('s', t); for (let j = 0; j < 4; j++) drum('h', t + j * beat / 4); break;
          case 'tick': drum('h', t); drum('h', t + beat / 2); if (i === 0) drum('t', t); break;
          case 'silly': drum('w', t + beat / 2); if (i === 0) drum('k', t); break;
          default:
        }
      }
    }
  }

  // Plays the scene's audio from scene time `from`. Returns a function that stops it.
  play(scene, from = 0) {
    this.stop();
    const c = this.ensure();
    const start = c.currentTime + 0.06;
    const bus = c.createGain();
    bus.connect(this.master);
    const sfxBus = c.createGain();
    sfxBus.gain.value = scene.sfxVolume;
    sfxBus.connect(bus);
    for (const e of scene.sfx) if (e.t >= from - 0.01) this.sfx(e.sound, start + Math.max(0, e.t - from), sfxBus, e.volume);
    const musicBus = c.createGain();
    musicBus.gain.value = scene.music.volume;
    musicBus.connect(bus);
    const end = scene.duration;
    const file = scene.music.file && this.buffers.get(scene.music.file);
    if (file) {
      const s = c.createBufferSource();
      s.buffer = file;
      s.loop = true;
      s.connect(musicBus);
      s.start(start, from % file.duration);
      s.stop(start + (end - from));
    } else if (scene.music.mood !== 'none') {
      this.scheduleMusic(scene.music, from, end, start, musicBus);
    }
    // Fade the music out over the final half second.
    musicBus.gain.setValueAtTime(scene.music.volume, start + Math.max(0, end - from - 0.5));
    musicBus.gain.linearRampToValueAtTime(0.0001, start + Math.max(0.01, end - from));
    this.session = { bus, start, from };
    return start;
  }

  stop() {
    if (!this.session) return;
    const { bus } = this.session;
    const now = this.ctx.currentTime;
    bus.gain.setTargetAtTime(0, now, 0.02);
    setTimeout(() => bus.disconnect(), 150);
    this.session = null;
  }
}
