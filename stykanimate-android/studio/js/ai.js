// Turns a concept into a scene by asking Claude or OpenAI for scene JSON.
// HTTP goes through the Android bridge when present (no CORS limits), else fetch.
import { POSES, ACTIONS, SCENERY, PROP_TYPES, EFFECTS, ACCESSORIES, SOUNDS, MOODS, extractJson } from './scene.js';

export const PROVIDERS = {
  claude: { label: 'Claude (Anthropic)', models: ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'], keyHint: 'sk-ant-…' },
  openai: { label: 'OpenAI', models: ['gpt-5', 'gpt-5-mini', 'gpt-4.1'], keyHint: 'sk-…' },
};

export function systemPrompt(customSounds = []) {
  return `You are the animation director inside a stick-figure animation app (Pivot / StykAnimate style).
Given a concept, you write a complete, lively animation as ONE JSON object. Reply with only the JSON, no prose.

STAGE: 16:9. Coordinates are normalized: x 0 = left edge, 1 = right edge; y 0 = top, 1 = bottom.
The ground line is background.groundY (default 0.82). A character's (x, y) is where its FEET are, so standing on the ground means y = groundY; jumping means a smaller y (e.g. groundY - 0.25).
A character at scale 1 is about 0.27 of the stage height tall.

JSON SCHEMA
{
  "title": string,
  "duration": seconds (3-60, fit the story; default 10-20),
  "background": { "sky": [2-3 hex colors top→bottom], "ground": hex, "groundY": 0.82, "scenery": one of ${JSON.stringify(SCENERY)} },
  "characters": [ { "id": short id, "name": string, "color": hex (body), "headColor": hex, "scale": 1, "accessory": one of ${JSON.stringify(ACCESSORIES)}, "accessoryColor": hex } ],
  "tracks": [ { "character": id, "keys": [ { "t": seconds, "x": 0-1, "y": feet y, "pose": pose name, "facing": 1 (right) or -1 (left), "rot": whole-body rotation degrees (for flips/spins, e.g. 360), "action": one of ${JSON.stringify(ACTIONS)}, "ease": "linear"|"in"|"out"|"inOut", "joints": { optional angle overrides } } ] } ],
  "props": [ { "id": string, "type": one of ${JSON.stringify(PROP_TYPES)}, "color": hex, "size": pixels (~20-200, stage is 1280x720), "text": for signs, "keys": [ { "t", "x", "y" (bottom of prop), "rot", "scale", "opacity", "holder": character id to hold it in a hand, "hand": "front"|"back" } ] } ],
  "camera": [ { "t", "x": center 0-1 (0.5 = default), "y": center (0.5 default), "zoom": 1 default (2 = close-up), "shake": 0-3 } ],
  "sfx": [ { "t": seconds, "sound": one of ${JSON.stringify(SOUNDS.concat(customSounds.map((n) => `custom:${n}`)))}, "volume": 0-2 } ],
  "music": { "mood": one of ${JSON.stringify(MOODS)}, "bpm": 0 for the mood default or 60-180, "volume": 0-1 (0.4 typical) },
  "captions": [ { "t", "d": seconds shown, "text" } ],
  "speech": [ { "t", "d", "character": id, "text": short line for a speech bubble } ],
  "effects": [ { "t", "d", "type": one of ${JSON.stringify(EFFECTS)}, "x", "y", "color": hex, "size": 1 } ]
}

POSES (name → meaning): ${Object.keys(POSES).join(', ')}.
Joint override names (degrees): torso (lean forward +), head (nod +), backShoulder/frontShoulder (relative to torso: 0 arm along body, 90 forward, 180 overhead), backElbow/frontElbow (bend forward +), backHip/frontHip (0 leg down, 90 forward), backKnee/frontKnee (bend back +). Use overrides only to fine-tune.

ANIMATION RULES
- Keys interpolate between each other; give each character a key at t=0 and keys every 0.2-1.0 s during action. Hold a pose by repeating it at a later t.
- To travel, set "action": "walk" or "run" on the key where the movement STARTS and put the destination x on the next key; legs animate automatically. "dance" loops a dance to the beat; "idle" adds breathing.
- Hits need anticipation and follow-through: wind-up pose (~0.2 s), strike (~0.1 s), impact (hurt/fall on the target + "impact" effect + "punch" sound + small camera shake), recovery.
- Jumps: crouch → jump with y raised over ~0.3 s → land back at groundY with "land" sound and "dust" effect.
- Sync every sound to the exact moment of the action (footsteps optional, hits/jumps/explosions required). Use music that fits the mood.
- Use speech bubbles or captions so the story reads without narration. Keep text short.
- Move the camera for drama (zoom in on key moments, follow travel) but keep everything important in frame.
- Characters face each other in conversations and fights (facing 1 looks right, -1 looks left).
- Make it entertaining with a clear beginning, middle and end.`;
}

const ANTHROPIC_FALLBACK_MODELS = /^claude-(opus-5|fable-5|sonnet-5-5)/;

async function post(url, headers, body) {
  if (window.Android?.httpPost) {
    return new Promise((resolve, reject) => {
      const id = `h${Date.now()}${Math.random().toString(36).slice(2)}`;
      (window.__androidHttp ||= {})[id] = (status, text) => { delete window.__androidHttp[id]; status > 0 ? resolve({ status, text }) : reject(new Error(text || 'Network error')); };
      window.Android.httpPost(id, url, JSON.stringify(headers), JSON.stringify(body));
    });
  }
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: res.status, text: await res.text() };
}

function apiError(status, text) {
  let msg = text;
  try { const j = JSON.parse(text); msg = j.error?.message || j.message || text; } catch { /* plain text */ }
  if (status === 401) return new Error(`The API key was rejected (401). Check it in Settings.\n${msg}`);
  if (status === 429) return new Error(`Rate limited or out of credit (429).\n${msg}`);
  return new Error(`API error ${status}: ${String(msg).slice(0, 400)}`);
}

async function callClaude({ key, model, system, user }) {
  const body = { model, max_tokens: 16000, system, messages: [{ role: 'user', content: user }] };
  const headers = { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true' };
  if (/^claude-(opus|sonnet|fable|haiku-5)/.test(model)) body.output_config = { effort: 'medium' };
  if (ANTHROPIC_FALLBACK_MODELS.test(model)) { body.fallbacks = 'default'; headers['anthropic-beta'] = 'server-side-fallback-2026-07-01'; }
  const { status, text } = await post('https://api.anthropic.com/v1/messages', headers, body);
  if (status < 200 || status >= 300) throw apiError(status, text);
  const res = JSON.parse(text);
  if (res.stop_reason === 'refusal') throw new Error(`Claude declined this concept${res.stop_details?.explanation ? `: ${res.stop_details.explanation}` : '.'} Try rephrasing it.`);
  const out = (res.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('\n');
  if (res.stop_reason === 'max_tokens' && !out.includes('}')) throw new Error('The reply was cut off. Try a shorter duration.');
  return out;
}

async function callOpenAI({ key, model, system, user }) {
  const body = { model, messages: [{ role: 'system', content: system }, { role: 'user', content: user }], response_format: { type: 'json_object' } };
  const { status, text } = await post('https://api.openai.com/v1/chat/completions', { 'content-type': 'application/json', authorization: `Bearer ${key}` }, body);
  if (status < 200 || status >= 300) throw apiError(status, text);
  const res = JSON.parse(text);
  const choice = res.choices?.[0];
  if (choice?.message?.refusal) throw new Error(`OpenAI declined: ${choice.message.refusal}`);
  return choice?.message?.content || '';
}

/** Generate a new scene, or revise `current` when given. Returns raw scene JSON. */
export async function generateScene({ provider, key, model, concept, duration, current, customSounds }) {
  if (!key) throw new Error(`Add your ${PROVIDERS[provider].label} API key in Settings first.`);
  const system = systemPrompt(customSounds);
  const user = current
    ? `Here is the current animation JSON:\n${JSON.stringify(current)}\n\nRevise it according to this request, keeping everything else that works: ${concept}\nReturn the complete updated JSON.`
    : `Concept: ${concept}\n${duration ? `Target duration: about ${duration} seconds.` : 'Pick a duration that fits the story.'}\nReturn the animation JSON.`;
  const call = provider === 'openai' ? callOpenAI : callClaude;
  const text = await call({ key, model, system, user });
  return extractJson(text);
}
