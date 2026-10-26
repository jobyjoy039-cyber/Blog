// A built-in animation so the app can be tried without an API key.
import { normalizeScene } from './scene.js';

export function demoScene() {
  const hero = [], rival = [], sfx = [];
  // Hero walks in from the left.
  for (let i = 0; i <= 6; i++) {
    hero.push({ t: i * 0.3, x: 0.12 + i * 0.045, pose: i % 2 ? 'walk2' : 'walk1', ease: 'linear', expr: 'happy' });
    sfx.push({ t: i * 0.3, sound: 'step', volume: 0.6 });
  }
  hero.push({ t: 2.1, x: 0.39, pose: 'stand', say: 'Hey! That was my sandwich!', expr: 'angry' });
  hero.push({ t: 3.2, x: 0.4, pose: 'crouch', expr: 'angry' });
  hero.push({ t: 3.5, x: 0.48, lift: 0.55, rot: 0, pose: 'jump', ease: 'out' });
  hero.push({ t: 3.85, x: 0.56, lift: 0.35, rot: 360, pose: 'kick', ease: 'linear' });
  hero.push({ t: 4.2, x: 0.6, lift: 0, rot: 360, pose: 'land', ease: 'in' });
  hero.push({ t: 4.6, x: 0.6, rot: 360, pose: 'stand' });
  hero.push({ t: 5.6, x: 0.6, rot: 360, pose: 'cheer', say: 'Justice!', expr: 'happy' });
  hero.push({ t: 6.2, x: 0.6, rot: 360, pose: 'dance1', expr: 'happy' });
  hero.push({ t: 6.6, x: 0.6, rot: 360, pose: 'dance2', expr: 'happy' });
  hero.push({ t: 7, x: 0.6, rot: 360, pose: 'dance1', expr: 'happy' });
  hero.push({ t: 7.4, x: 0.6, rot: 360, pose: 'celebrate', expr: 'happy' });

  rival.push({ t: 0, x: 0.72, facing: -1, pose: 'idle', expr: 'happy' });
  rival.push({ t: 1.5, x: 0.72, facing: -1, pose: 'think', expr: 'neutral' });
  rival.push({ t: 2.6, x: 0.72, facing: -1, pose: 'shrug', say: 'What sandwich?', expr: 'happy' });
  rival.push({ t: 3.6, x: 0.72, facing: -1, pose: 'block', expr: 'surprised' });
  rival.push({ t: 3.9, x: 0.74, facing: -1, pose: 'hurt', expr: 'hurt' });
  rival.push({ t: 4.3, x: 0.84, facing: -1, lift: 0.15, rot: -60, pose: 'fall', expr: 'hurt' });
  rival.push({ t: 4.7, x: 0.88, facing: -1, pose: 'lie', expr: 'hurt' });
  rival.push({ t: 8, x: 0.88, facing: -1, pose: 'lie', expr: 'hurt' });

  sfx.push(
    { t: 3.2, sound: 'whoosh' }, { t: 3.5, sound: 'jump' }, { t: 3.85, sound: 'kick' },
    { t: 3.88, sound: 'punch' }, { t: 4.2, sound: 'land' }, { t: 4.7, sound: 'crash' },
    { t: 5.6, sound: 'tada' }, { t: 7.4, sound: 'coin' },
  );

  return normalizeScene({
    title: 'The Sandwich Incident',
    concept: 'A stick figure finds their rival ate their sandwich and settles it with a flying kick.',
    duration: 8,
    background: { sky: '#bfe3ff', ground: '#9ccc65', groundY: 0.82, scenery: 'hills' },
    figures: [
      { id: 'hero', name: 'Hero', color: '#1d1d1f', keyframes: hero },
      { id: 'rival', name: 'Rival', color: '#d7263d', keyframes: rival },
    ],
    props: [
      { id: 'sandwich', type: 'box', color: '#f4a261', size: 0.5, keyframes: [
        { t: 0, x: 0.72, holder: 'rival', hand: 'r' },
        { t: 3.9, x: 0.72, holder: 'rival', hand: 'r' },
        { t: 4.0, x: 0.75, lift: 0.9, rot: 0, ease: 'out' },
        { t: 4.6, x: 0.66, lift: 0.1, rot: 540, ease: 'in' },
        { t: 5.0, x: 0.6, lift: 0, holder: 'hero', hand: 'r' },
        { t: 8, x: 0.6, holder: 'hero', hand: 'r' },
      ] },
    ],
    effects: [
      { t: 3.85, type: 'impact', x: 0.68, lift: 0.55, color: '#ffbe0b', dur: 0.35 },
      { t: 3.85, type: 'text', x: 0.7, lift: 1.25, text: 'POW!', color: '#ffbe0b', dur: 0.7 },
      { t: 3.85, type: 'shake', dur: 0.35 },
      { t: 4.2, type: 'dust', x: 0.6, lift: 0, dur: 0.5 },
      { t: 4.7, type: 'dust', x: 0.86, lift: 0, dur: 0.5 },
      { t: 4.75, type: 'stars', x: 0.93, lift: 0.15, color: '#ffd166', dur: 3 },
      { t: 5.6, type: 'hearts', x: 0.6, lift: 1.1, dur: 1.2 },
    ],
    captions: [{ t: 0.2, end: 1.8, text: 'Lunchtime in the park…' }],
    sfx,
    music: { mood: 'silly', bpm: 120, volume: 0.4 },
  });
}
