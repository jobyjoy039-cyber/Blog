// End-to-end smoke test of the web build in headless Chromium.
// The Claude and OpenAI endpoints are mocked, so no API keys are needed.
import { createRequire } from 'node:module';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

// Uses the globally installed Playwright (or a local one if present).
const { chromium } = createRequire(import.meta.url)('playwright');

const root = path.resolve('www');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.map': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname.replace(/\/$/, '/index.html')));
  if (!p.startsWith(root) || !fs.existsSync(p)) { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' }).end(fs.readFileSync(p));
}).listen(0);
const base = `http://localhost:${server.address().port}/`;

const aiScene = {
  title: 'Mock Duel', duration: 3, aspect: '16:9',
  background: { sky: '#223355', ground: '#445566', groundY: 0.8, scenery: 'night' },
  figures: [
    { id: 'a', name: 'Ninja', color: '#111111', keyframes: [
      { t: 0, x: 0.3, pose: 'stand' }, { t: 1, x: 0.4, pose: 'punch', say: 'Hi-ya!' }, { t: 2, x: 0.4, lift: 0.5, rot: 360, pose: 'jump' }, { t: 3, x: 0.4, pose: 'land' }] },
    { id: 'b', name: 'Robot', color: '#3366ff', keyframes: [
      { t: 0, x: 0.7, facing: -1, pose: 'idle' }, { t: 1.05, x: 0.72, facing: -1, pose: 'hurt', expr: 'hurt' }, { t: 2, x: 0.8, facing: -1, pose: 'lie' }] },
  ],
  effects: [{ t: 1, type: 'impact', x: 0.6, lift: 0.6 }],
  sfx: [{ t: 1, sound: 'punch' }, { t: 2, sound: 'jump' }, { t: 3, sound: 'land' }],
  music: { mood: 'action', bpm: 140 },
};

function claudeSSE(text) {
  const ev = (type, data) => `event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`;
  const half = Math.floor(text.length / 2);
  return [
    ev('message_start', { message: { id: 'msg_1', type: 'message', role: 'assistant', model: 'claude-opus-5-5', content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 10, output_tokens: 0 } } }),
    ev('content_block_start', { index: 0, content_block: { type: 'text', text: '' } }),
    ev('content_block_delta', { index: 0, delta: { type: 'text_delta', text: text.slice(0, half) } }),
    ev('content_block_delta', { index: 0, delta: { type: 'text_delta', text: text.slice(half) } }),
    ev('content_block_stop', { index: 0 }),
    ev('message_delta', { delta: { stop_reason: 'end_turn', stop_sequence: null }, usage: { output_tokens: 100 } }),
    ev('message_stop', {}),
  ].join('');
}

function openaiSSE(text) {
  const chunk = (content) => `data: ${JSON.stringify({ id: 'c1', object: 'chat.completion.chunk', created: 0, model: 'gpt-5', choices: [{ index: 0, delta: { content }, finish_reason: null }] })}\n\n`;
  return chunk(text.slice(0, 50)) + chunk(text.slice(50)) + 'data: [DONE]\n\n';
}

let failures = 0;
const check = (cond, msg) => { console.log(`${cond ? '✔' : '✘'} ${msg}`); if (!cond) failures++; };

const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2 });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));

const requests = [];
await page.route('https://api.anthropic.com/**', async (route) => {
  const req = route.request();
  requests.push({ provider: 'claude', headers: req.headers(), body: JSON.parse(req.postData()) });
  await route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream', 'access-control-allow-origin': '*' }, body: claudeSSE(JSON.stringify(aiScene)) });
});
await page.route('https://api.openai.com/**', async (route) => {
  const req = route.request();
  requests.push({ provider: 'openai', headers: req.headers(), body: JSON.parse(req.postData()) });
  await route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream', 'access-control-allow-origin': '*' }, body: openaiSSE(JSON.stringify({ ...aiScene, title: 'OpenAI Duel' })) });
});

await page.goto(base);
await page.waitForFunction(() => window.__stickai);
await page.screenshot({ path: 'tests/out/01-demo.png' });

const pixels = () => page.evaluate(() => {
  const c = document.getElementById('canvas');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let dark = 0;
  for (let i = 0; i < d.length; i += 16) if (d[i] + d[i + 1] + d[i + 2] < 120) dark++;
  return dark;
});
check((await pixels()) > 200, 'demo scene draws stick figures on the canvas');
check(await page.textContent('#sceneTitle') === 'The Sandwich Incident', 'demo scene loads by default');

// Playback advances time.
await page.click('#btnPlay');
await page.waitForTimeout(1200);
const t1 = await page.evaluate(() => window.__stickai.state.t);
check(t1 > 0.5, `playback advances (t=${t1.toFixed(2)})`);
await page.click('#btnPlay');
check(await page.evaluate(() => window.__stickai.audio.ctx && window.__stickai.audio.ctx.state) === 'running', 'audio context is running');

// Scrub to the kick and capture it.
await page.evaluate(() => { const s = window.__stickai.state; s.t = 3.9; window.__stickai.draw(); });
await page.screenshot({ path: 'tests/out/02-kick.png' });

// Claude generation (mocked).
await page.click('#btnSettings');
await page.fill('#claudeKey', 'sk-ant-test');
await page.fill('#openaiKey', 'sk-test');
await page.click('#btnSaveSettings');
await page.fill('#concept', 'A ninja punches a robot');
await page.selectOption('#provider', 'claude');
await page.click('#btnGenerate');
await page.waitForFunction(() => window.__stickai.state.scene.title === 'Mock Duel', null, { timeout: 15000 });
check(true, 'Claude reply becomes the current scene');
const creq = requests.find((r) => r.provider === 'claude');
check(creq.body.model === 'claude-opus-5-5' && creq.body.stream === true, 'Claude request streams with claude-opus-5-5');
check(creq.body.fallbacks === 'default' && String(creq.headers['anthropic-beta']).includes('server-side-fallback-2026-07-01'), 'Claude request opts into refusal fallbacks');
check(creq.headers.authorization === 'Bearer sk-ant-test' && creq.headers['anthropic-dangerous-direct-browser-access'] === 'true', 'Claude request uses the saved key from the app');
check(creq.body.system.includes('"sfx"') && creq.body.messages[0].content.includes('A ninja punches a robot'), 'prompt carries schema and concept');
await page.waitForTimeout(700);
await page.screenshot({ path: 'tests/out/03-claude.png' });

// Refine with OpenAI (mocked).
await page.selectOption('#provider', 'openai');
await page.fill('#refine', 'make it funnier');
await page.click('#btnRefine');
await page.waitForFunction(() => window.__stickai.state.scene.title === 'OpenAI Duel', null, { timeout: 15000 });
const oreq = requests.find((r) => r.provider === 'openai');
check(oreq.body.model === 'gpt-5' && oreq.body.response_format.type === 'json_object', 'OpenAI request uses JSON mode');
check(oreq.body.messages[1].content.includes('Mock Duel'), 'refine sends the current scene back to the AI');
await page.click('#btnPlay');

// Edit: drag a hand joint and check a keyframe changes.
await page.click('.tab[data-tab=edit]');
await page.evaluate(() => { const s = window.__stickai.state; s.t = 0.5; s.selected = 0; window.__stickai.draw(); });
const before = await page.evaluate(() => window.__stickai.state.scene.figures[0].keyframes.length);
const handPos = await page.evaluate(() => {
  const sk = window.__stickai.state.skels.a;
  const c = document.getElementById('canvas').getBoundingClientRect();
  const s = c.width / 1280;
  return [c.left + sk.rHand[0] * s, c.top + sk.rHand[1] * s];
});
await page.mouse.move(handPos[0], handPos[1]);
await page.mouse.down();
await page.mouse.move(handPos[0] + 10, handPos[1] - 40, { steps: 5 });
await page.mouse.up();
const after = await page.evaluate(() => window.__stickai.state.scene.figures[0].keyframes.length);
check(after === before + 1, `dragging a joint adds a keyframe (${before} → ${after})`);
await page.screenshot({ path: 'tests/out/04-edit.png' });

// Sound: add an effect at the playhead.
await page.click('.tab[data-tab=sound]');
const sfxBefore = await page.evaluate(() => window.__stickai.state.scene.sfx.length);
await page.selectOption('#sfxSelect', 'explosion');
await page.click('#btnAddSfx');
check(await page.evaluate(() => window.__stickai.state.scene.sfx.length) === sfxBefore + 1, 'sound effect added at the playhead');
await page.selectOption('#musicSource', 'mood:epic');
check(await page.evaluate(() => window.__stickai.state.scene.music.mood) === 'epic', 'music mood can be changed');

// Import a generated WAV file as a custom sound effect.
const wav = (() => {
  const n = 4410, b = Buffer.alloc(44 + n * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(44100, 24); b.writeUInt32LE(88200, 28);
  b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(Math.sin(i / 10) * 8000), 44 + i * 2);
  return b;
})();
await page.setInputFiles('#sfxFile', { name: 'beep.wav', mimeType: 'audio/wav', buffer: wav });
await page.waitForFunction(() => window.__stickai.audio.buffers.has('custom:beep'));
check(true, 'custom sound effect imported');
await page.screenshot({ path: 'tests/out/05-sound.png' });

// Export: record a short video.
await page.evaluate(() => { const s = window.__stickai.state; s.scene.duration = 1.5; });
await page.click('.tab[data-tab=export]');
const [download] = await Promise.all([page.waitForEvent('download', { timeout: 20000 }), page.click('#btnVideo')]);
const file = await download.path();
const size = fs.statSync(file).size;
check(size > 10000, `video exported: ${download.suggestedFilename()} (${(size / 1024).toFixed(0)} KB)`);

// Vertical layout.
await page.evaluate(() => { const s = window.__stickai.state; s.scene.aspect = '9:16'; s.t = 1; window.__stickai.draw(); });
await page.screenshot({ path: 'tests/out/06-vertical.png' });

check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
await browser.close();
server.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nAll checks passed');
process.exit(failures ? 1 : 0);
