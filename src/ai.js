// Turns a text concept into an animated scene using Claude (Anthropic) or OpenAI.
import Anthropic from '@anthropic-ai/sdk';
import OpenAI from 'openai';
import { POSES, POSE_NAMES, SOUND_NAMES, MUSIC_MOODS, SCENERY, EFFECTS, PROPS, normalizeScene } from './scene.js';

export const DEFAULT_MODELS = { claude: 'claude-opus-5-5', openai: 'gpt-5' };

function systemPrompt(customSounds) {
  const poseTable = POSE_NAMES.map((n) => `  ${n}: ${JSON.stringify(POSES[n])}`).join('\n');
  return `You are the animation director inside a stick figure animation app. You turn a concept into a short, funny, readable 2D stick figure cartoon described as JSON. The app renders your JSON with its own skeleton, interpolates between keyframes and synthesizes the sound effects and music you list.

Reply with ONE JSON object and nothing else: no markdown fences, no commentary.

## JSON shape
{
  "title": string,
  "duration": number,                      // seconds, 4-30 (default 8-12)
  "aspect": "16:9" | "9:16",
  "background": { "sky": "#rrggbb", "ground": "#rrggbb", "groundY": 0.82, "scenery": one of ${JSON.stringify(SCENERY)} },
  "figures": [{
    "id": string, "name": string, "color": "#rrggbb", "scale": 1,
    "keyframes": [{
      "t": seconds,
      "x": 0..1,               // horizontal position of the hip, fraction of screen width
      "lift": number,          // height above the ground in figure heights (0 = standing on ground, 0.6 = high jump)
      "facing": 1 | -1,        // 1 faces right, -1 faces left
      "rot": degrees,          // whole-body rotation around the hip, positive = forward (360 = flip)
      "pose": preset name OR { "preset": name, ...joint overrides in degrees },
      "ease": "ease" | "linear" | "in" | "out" | "step",   // easing INTO this keyframe
      "say": string,           // optional speech bubble, shown until this figure's next keyframe
      "expr": "neutral" | "happy" | "sad" | "angry" | "surprised" | "hurt"
    }]
  }],
  "props": [{ "id": string, "type": one of ${JSON.stringify(PROPS)}, "color": "#rrggbb", "size": 1,
              "keyframes": [{ "t", "x", "lift", "rot", "holder": figure id or "", "hand": "l"|"r", "visible": true }] }],
  "effects": [{ "t": seconds, "type": one of ${JSON.stringify(EFFECTS)}, "x": 0..1, "lift": figure heights, "text": "POW!", "color": "#rrggbb", "dur": seconds }],
  "captions": [{ "t": seconds, "end": seconds, "text": string }],
  "sfx": [{ "t": seconds, "sound": one of ${JSON.stringify(SOUND_NAMES.concat(customSounds))}, "volume": 0..1 }],
  "music": { "mood": one of ${JSON.stringify(MUSIC_MOODS)}, "bpm": 60-180, "volume": 0..1 }
}

## Poses
Joint angles in degrees for a figure facing right. torso = spine lean (positive forward). head = head tilt. Shoulder = upper arm angle from hanging down, relative to the spine (90 = pointing forward, 180 = straight up, negative = behind). Elbow = forearm bend (positive bends forward/up). Hip = thigh angle from straight down (positive forward). Knee = shin bend backward (0 = straight). "l" is the far limb, "r" the near limb.
Presets:
${poseTable}

## Direction rules
- Animate with plenty of keyframes: roughly every 0.15-0.4 s during action. Walking alternates walk1/walk2 every ~0.3 s while x changes ~0.04 per step; running alternates run1/run2 every ~0.18 s.
- Jumps: crouch -> jump with lift 0.3-0.8 -> land with lift 0. Flips use rot 360. Falls use fall then lie.
- Keep figures inside x 0.08-0.92 unless entering or leaving. Two figures fighting stand ~0.12-0.2 apart and face each other.
- Every hit, jump, landing, footstep run or explosion gets an sfx at the exact same t, and usually an effect (impact, text like "POW!", dust on landings, shake for big hits).
- Pick music mood and bpm that fit the story. Use captions only for narration; use "say" for dialogue.
- Give the story a beginning, a clear action and a punchline or ending pose. Keep all t within duration.`;
}

function extractJson(text) {
  const t = text.trim();
  try { return JSON.parse(t); } catch { /* fall through */ }
  const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) { try { return JSON.parse(fence[1]); } catch { /* fall through */ } }
  const a = t.indexOf('{'), b = t.lastIndexOf('}');
  if (a >= 0 && b > a) return JSON.parse(t.slice(a, b + 1));
  throw new Error('The AI reply did not contain JSON.');
}

function userPrompt(concept, current, aspect) {
  if (current) {
    return `Here is the current animation JSON:\n${JSON.stringify(current)}\n\nRevise it according to this instruction and return the complete updated JSON object:\n${concept}`;
  }
  return `Concept: ${concept}\n\nUse aspect "${aspect}". Return the animation JSON.`;
}

async function askClaude({ apiKey, model, system, prompt, onProgress }) {
  const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });
  const stream = client.beta.messages.stream({
    model: model || DEFAULT_MODELS.claude,
    max_tokens: 64000,
    output_config: { effort: 'medium' },
    // Re-runs the request on a fallback model if the primary model declines it.
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    system,
    messages: [{ role: 'user', content: prompt }],
  });
  let chars = 0;
  stream.on('text', (delta) => {
    chars += delta.length;
    onProgress?.(chars);
  });
  const msg = await stream.finalMessage();
  if (msg.stop_reason === 'refusal') {
    throw new Error(`Claude declined this concept${msg.stop_details?.explanation ? `: ${msg.stop_details.explanation}` : '.'}`);
  }
  if (msg.stop_reason === 'max_tokens') throw new Error('The animation was too long for one reply. Try a shorter concept.');
  return msg.content.filter((b) => b.type === 'text').map((b) => b.text).join('');
}

async function askOpenAI({ apiKey, model, system, prompt, onProgress }) {
  const client = new OpenAI({ apiKey, dangerouslyAllowBrowser: true });
  const stream = await client.chat.completions.create({
    model: model || DEFAULT_MODELS.openai,
    response_format: { type: 'json_object' },
    stream: true,
    messages: [
      { role: 'system', content: system },
      { role: 'user', content: prompt },
    ],
  });
  let text = '';
  for await (const chunk of stream) {
    text += chunk.choices[0]?.delta?.content || '';
    onProgress?.(text.length);
  }
  return text;
}

function friendlyError(provider, e) {
  const status = e?.status;
  if (status === 401) return `${provider} rejected the API key. Check it in Settings.`;
  if (status === 403) return `${provider} key does not have access to this model.`;
  if (status === 404) return `${provider} does not know that model name. Check it in Settings.`;
  if (status === 429) return `${provider} rate limit or quota reached. Wait a moment and try again.`;
  if (status >= 500) return `${provider} is having trouble right now (${status}). Try again.`;
  return e?.message || String(e);
}

// Generates (or revises, when `current` is given) a scene from a concept.
export async function generateScene({ provider, apiKey, model, concept, current, aspect = '16:9', customSounds = [], onProgress }) {
  if (!apiKey) throw new Error(`Add your ${provider === 'openai' ? 'OpenAI' : 'Anthropic'} API key in Settings first.`);
  const args = { apiKey, model, system: systemPrompt(customSounds), prompt: userPrompt(concept, current, aspect), onProgress };
  let text;
  try {
    text = provider === 'openai' ? await askOpenAI(args) : await askClaude(args);
  } catch (e) {
    throw new Error(friendlyError(provider === 'openai' ? 'OpenAI' : 'Claude', e));
  }
  const scene = normalizeScene(extractJson(text));
  scene.concept = current ? (current.concept || concept) : concept;
  if (!scene.figures.length) throw new Error('The AI returned an animation with no figures. Try again or rephrase the concept.');
  return scene;
}

export { extractJson, systemPrompt };
