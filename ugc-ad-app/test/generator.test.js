import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  beatTimings, buildScript, buildBatch, buildVideoPrompt, checkClaims, scriptChecks,
  normalizeBrief, toMarkdown, HOOK_TYPES,
} from '../src/generator.js';
import { PRESETS } from '../src/presets.js';

const grip = PRESETS.gripmount.brief;

test('beat timings match the academy template for a 28s ad', () => {
  assert.deepEqual(beatTimings(28), [[0, 2], [2, 15], [15, 25], [25, 28]]);
});

test('script has four beats and fits the target length', () => {
  const s = buildScript(grip, 'surprise');
  assert.deepEqual(s.beats.map((b) => b.beat), ['Hook', 'Problem / Pitch', 'Proof / Demo', 'Call to Action']);
  assert.match(s.beats[0].line, /phone falling off the dash/);
  assert.match(s.beats[1].line, /suction cup/);
  assert.match(s.beats[3].line, /\$28/);
  assert.ok(s.readSeconds <= 28, `read time ${s.readSeconds}s`);
});

test('batch locks constants and varies only the hook', () => {
  const batch = buildBatch(grip);
  assert.equal(batch.variants.length, 5);
  const hooks = new Set(batch.variants.map((v) => v.hook));
  assert.equal(hooks.size, 5);
  for (const v of batch.variants) {
    assert.deepEqual(v.script.beats.slice(1), batch.variants[0].script.beats.slice(1));
    assert.deepEqual(Object.keys(v.prompts), ['tiktok', 'reels']);
  }
});

test('explicit hook types are honoured', () => {
  const batch = buildBatch({ ...grip, hookTypes: ['pov', 'founder'], variantCount: 2 });
  assert.deepEqual(batch.variants.map((v) => v.hookType), ['pov', 'founder']);
});

test('every hook type produces a line', () => {
  for (const k of Object.keys(HOOK_TYPES)) {
    assert.ok(buildScript(grip, k).beats[0].line.length > 5, k);
  }
});

test('video prompt includes platform, honesty and restrictions', () => {
  const p = buildVideoPrompt(grip, 'surprise', 'reels');
  assert.match(p, /9:16/);
  assert.match(p, /Instagram Reels/);
  assert.match(p, /Do not present the creator as a real customer/);
  assert.match(p, /no label distortion/);
  assert.match(p, /can't claim unbreakable/);
  assert.match(p, /Disclosure/);
});

test('founder role skips the not-a-customer line; app category adds UI rules', () => {
  const p = buildVideoPrompt({ ...PRESETS.pantry.brief, creatorRole: 'founder' }, 'founder', 'tiktok');
  assert.doesNotMatch(p, /real customer/);
  assert.match(p, /abstract UI cards/);
});

test('claim checker flags risky copy and passes clean copy', () => {
  const f = checkClaims('Clinically proven and guaranteed! I lost 20 pounds. Doctor recommended, 100% unbreakable.');
  const matches = f.map((x) => x.match.toLowerCase());
  for (const m of ['clinically proven', 'guaranteed', 'lost 20 pounds', 'doctor recommended', '100%', 'unbreakable']) {
    assert.ok(matches.some((x) => x.includes(m.toLowerCase())), `expected ${m}`);
  }
  assert.equal(checkClaims('It held through two weeks of daily driving.').length, 0);
});

test('generated preset scripts pass their own checks', () => {
  for (const [name, { brief }] of Object.entries(PRESETS)) {
    const b = normalizeBrief(brief);
    for (const v of buildBatch(brief).variants) {
      const failed = scriptChecks(v.script, b).filter((c) => !c.ok).map((c) => c.label);
      assert.deepEqual(failed, [], `${name} ad ${v.id}`);
    }
  }
});

test('normalizeBrief clamps and defaults', () => {
  const b = normalizeBrief({ duration: 999, variantCount: 0, platforms: ['nope'] });
  assert.equal(b.duration, 60);
  assert.equal(b.variantCount, 5);
  assert.deepEqual(b.platforms, ['tiktok']);
});

test('markdown export contains brief, matrix, scripts and QA', () => {
  const md = toMarkdown(buildBatch(grip));
  for (const s of ['# UGC Ad Batch: GripMount', '## Batch matrix', '## Ad 5', '```text', '## QA checklist']) {
    assert.ok(md.includes(s), s);
  }
});

test('viewer-facing hooks switch to second person', () => {
  assert.equal(buildScript(grip, 'pov').beats[0].line, 'POV: you finally stop dealing with your phone falling off the dash.');
});
