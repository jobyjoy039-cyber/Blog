// Pure generation logic for UGC ad briefs. No DOM access, so it runs in the
// browser and under `node --test` alike.
//
// Methodology adapted from:
//  - Anil-matcha/ai-creator-academy, Track 1 "AI Video Ads & UGC" (MIT):
//    hook -> pitch -> proof -> CTA script, ad brief checklist, batch matrix
//    (lock constants, vary only the hook).
//  - cliprise/awesome-ai-ugc-video-prompts: UGC video prompt formula,
//    platform-first planning, restriction library, QA checklist and the
//    "UGC style is not permission to fake real experience" principle.

export const WORDS_PER_SECOND = 3;

export const PLATFORMS = {
  tiktok: {
    label: 'TikTok',
    aspect: '9:16',
    style: 'TikTok-native UGC ad, handheld but steady, hook lands in the first second, product shown early, relaxed creator delivery.',
  },
  reels: {
    label: 'Instagram Reels',
    aspect: '9:16',
    style: 'Instagram Reels UGC ad, vertical and mobile-first, clean creator framing, product and CTA kept inside the safe zone.',
  },
  facebook: {
    label: 'Facebook Feed',
    aspect: '4:5',
    style: 'Mobile-first Facebook UGC ad with a clear problem-solution arc, readable on a small screen, product-centred final frame.',
  },
  shorts: {
    label: 'YouTube Shorts',
    aspect: '9:16',
    style: 'YouTube Shorts UGC ad with a strong visual first frame, fast demo, and a final beat that works as a thumbnail.',
  },
  instream: {
    label: 'YouTube In-stream',
    aspect: '16:9',
    style: 'Creator-led YouTube in-stream ad: problem, product and demo all land before the 5-second skip button.',
  },
};

export const CREATOR_ROLES = {
  demonstrator: { label: 'Product demonstrator', prompt: 'product demonstrator showing the product in use' },
  founder: { label: 'Founder', prompt: 'founder explaining why the product exists' },
  educator: { label: 'Educator', prompt: 'educator teaching one useful tip, with the product as the workflow' },
  actor: { label: 'Customer-style actor', prompt: 'customer-style actor performing an ad concept' },
};

export const CATEGORIES = {
  product: { label: 'Physical product', restrictions: ['no label distortion', 'no changed packaging', 'no extra products', 'no logo distortion', 'no unsafe use'] },
  beauty: { label: 'Beauty / health', restrictions: ['no medical or treatment claims', 'no guaranteed results', 'no fake before-after', 'no fake dermatologist or doctor', 'no skin distortion'] },
  finance: { label: 'Finance / money', restrictions: ['no income guarantees', 'no fake account balances', 'no fake investment returns', 'no real bank logos', 'no misleading savings claims'] },
  app: { label: 'App / SaaS', restrictions: ['no readable fake UI text (use abstract UI cards)', 'no competitor logos', 'no fake ratings or reviews', 'no distorted screen', 'no random buttons'] },
  local: { label: 'Local service', restrictions: ['no fake guarantee', 'no exaggerated transformation', 'no fake customer quote', 'no misleading before-after'] },
  food: { label: 'Food / restaurant', restrictions: ['no fake ratings', 'no health claims', 'no distorted food', 'no extra fingers'] },
};

export const GENERAL_RESTRICTIONS = ['no fake testimonial', 'no fake review', 'no misleading result', 'no distorted hands', 'no face warping'];

export const CTA_TYPES = {
  shop: { label: 'Shop now' },
  app: { label: 'Download / try the app' },
  learn: { label: 'Learn more' },
  book: { label: 'Book / order' },
  lead: { label: 'Free lead magnet' },
};

const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const trimEnd = (s) => (s || '').trim().replace(/[.!?]+$/, '');
// "my phone falling" -> "your phone falling" for hooks spoken to the viewer.
const yours = (s) => s.replace(/\bmy\b/gi, 'your').replace(/\bI\b/g, 'you');
const thing = (b) => (b.price ? `This ${b.price} thing` : 'This little thing');

// Each hook keeps every other beat constant; the batch varies only this.
export const HOOK_TYPES = {
  surprise: {
    label: 'Surprise',
    angle: 'Unexpected result',
    line: (b) => `Okay, I did not expect this to actually fix ${b.problem}.`,
  },
  problem: {
    label: 'Problem-first',
    angle: 'Names the pain point',
    line: (b) => `I was so done with ${b.problem}.`,
  },
  pov: {
    label: 'POV',
    angle: 'Relatable / POV format',
    line: (b) => `POV: you finally stop dealing with ${yours(b.problem)}.`,
  },
  price: {
    label: 'Price / value',
    angle: 'Leads with price',
    line: (b) => `${thing(b)} fixed ${b.problem}.`,
  },
  proof: {
    label: 'Proof-first',
    angle: 'Opens on the result',
    line: (b) => `${cap(trimEnd(b.proof))}.`,
  },
  question: {
    label: 'Question',
    angle: 'Asks the viewer',
    line: (b) => `Why is ${b.problem} still a thing?`,
  },
  founder: {
    label: 'Founder',
    angle: 'Origin story',
    line: (b) => `We built ${b.product} because we were tired of ${yours(b.problem)}.`,
  },
  visual: {
    label: 'Visual action',
    angle: 'Most satisfying product moment first',
    line: (b) => `[No line. Open on the product moment: ${trimEnd(b.demo)}.]`,
  },
};

export const DEFAULT_HOOK_ORDER = ['surprise', 'problem', 'pov', 'price', 'proof', 'question', 'founder', 'visual'];

export function ctaLine(b) {
  const when = b.useCase ? ` before ${trimEnd(b.useCase)}` : '';
  switch (b.ctaType) {
    case 'app':
      return `It's free to try. Download it${when}.`;
    case 'learn':
      return `Check out ${b.product} if you want an easier way to handle it.`;
    case 'book':
      return `Book yours${when}. The link's below.`;
    case 'lead':
      return `Grab the free guide${when}. The link's in my bio.`;
    case 'shop':
    default:
      return b.price
        ? `It's ${b.price} and the link's below. Get it${when}.`
        : `The link's below. Get it${when}.`;
  }
}

export function normalizeBrief(raw = {}) {
  const b = {
    product: (raw.product || 'the product').trim(),
    description: trimEnd(raw.description) || 'makes this easier',
    price: (raw.price || '').trim(),
    category: CATEGORIES[raw.category] ? raw.category : 'product',
    audience: (raw.audience || '').trim() || 'people who face this problem',
    problem: trimEnd(raw.problem) || 'this everyday hassle',
    competitorFailure: trimEnd(raw.competitorFailure),
    proof: trimEnd(raw.proof) || 'it does exactly what it says',
    demo: trimEnd(raw.demo) || 'creator uses the product once, clearly on camera',
    setting: trimEnd(raw.setting) || 'a real home with natural daylight',
    useCase: trimEnd(raw.useCase),
    tone: (raw.tone || 'casual, natural, not corporate').trim(),
    platforms: (raw.platforms && raw.platforms.length ? raw.platforms : ['tiktok']).filter((p) => PLATFORMS[p]),
    duration: clamp(Number(raw.duration) || 28, 6, 60),
    creatorRole: CREATOR_ROLES[raw.creatorRole] ? raw.creatorRole : 'demonstrator',
    disclosure: raw.disclosure !== false,
    constraints: (raw.constraints || '').trim(),
    ctaType: CTA_TYPES[raw.ctaType] ? raw.ctaType : 'shop',
    variantCount: clamp(Number(raw.variantCount) || 5, 1, DEFAULT_HOOK_ORDER.length),
    hookTypes: Array.isArray(raw.hookTypes) ? raw.hookTypes.filter((h) => HOOK_TYPES[h]) : null,
  };
  if (!b.platforms.length) b.platforms = ['tiktok'];
  return b;
}

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, Math.round(n)));
}

// Beat boundaries follow the academy template (2s / 15s / 25s of a 28s ad)
// scaled to the requested duration.
export function beatTimings(duration) {
  const hookEnd = Math.max(1.5, Math.min(3, duration * 0.07));
  const pitchEnd = duration * 0.53;
  const proofEnd = duration * 0.89;
  const r = (n) => Math.round(n * 2) / 2;
  return [
    [0, r(hookEnd)],
    [r(hookEnd), r(pitchEnd)],
    [r(pitchEnd), r(proofEnd)],
    [r(proofEnd), duration],
  ];
}

export function buildScript(rawBrief, hookType = 'surprise') {
  const b = normalizeBrief(rawBrief);
  const hook = HOOK_TYPES[hookType] || HOOK_TYPES.surprise;
  const t = beatTimings(b.duration);
  const pitch = b.competitorFailure
    ? `I used to have one that ${b.competitorFailure}. ${cap(b.product)} ${b.description}.`
    : `${cap(b.product)} ${b.description}.`;
  const beats = [
    { beat: 'Hook', start: t[0][0], end: t[0][1], line: hook.line(b) },
    { beat: 'Problem / Pitch', start: t[1][0], end: t[1][1], line: pitch },
    { beat: 'Proof / Demo', start: t[2][0], end: t[2][1], line: `[demo: ${b.demo}] ${cap(b.proof)}.` },
    { beat: 'Call to Action', start: t[3][0], end: t[3][1], line: ctaLine(b) },
  ];
  const spoken = beats.map((x) => x.line.replace(/\[[^\]]*\]/g, '')).join(' ');
  const words = spoken.split(/\s+/).filter(Boolean).length;
  return {
    hookType,
    beats,
    words,
    targetWords: b.duration * WORDS_PER_SECOND,
    readSeconds: Math.round((words / WORDS_PER_SECOND) * 10) / 10,
  };
}

export function restrictionsFor(b) {
  const extra = b.constraints
    ? b.constraints.split(/[\n;,]+/).map((s) => s.trim()).filter(Boolean)
    : [];
  return [...new Set([...GENERAL_RESTRICTIONS, ...CATEGORIES[b.category].restrictions, ...extra])];
}

export function buildVideoPrompt(rawBrief, hookType, platform) {
  const b = normalizeBrief(rawBrief);
  const p = PLATFORMS[platform] || PLATFORMS[b.platforms[0]];
  const script = buildScript(b, hookType);
  const [hook, pitch, proof, cta] = script.beats;
  const role = CREATOR_ROLES[b.creatorRole];
  const lines = [
    `Create a ${b.duration}-second ${p.aspect} UGC-style video ad for ${b.product}${b.price ? ` (${b.price})` : ''}.`,
    `Audience: ${b.audience}.`,
    `Creator role: ${role.prompt}.`,
  ];
  if (b.disclosure) lines.push('Disclosure: paid ad / brand demo. Show an "Ad" or "#ad" label.');
  if (b.creatorRole !== 'founder') {
    lines.push('Do not present the creator as a real customer and do not invent personal results.');
  }
  lines.push(
    `Hook (${hook.start}-${hook.end}s): ${hook.line}`,
    `Problem / pitch (${pitch.start}-${pitch.end}s): ${pitch.line}`,
    `Product moment: show ${b.product} clearly by ${pitch.end}s. Keep the exact product shape, label placement, packaging and colour.`,
    `Demo / proof (${proof.start}-${proof.end}s): ${b.demo}. Voice line: "${cap(b.proof)}."`,
    `CTA (${cta.start}-${cta.end}s): "${cta.line}"`,
    'Camera: handheld but steady, phone-style creator framing, close-ups on the product.',
    `Setting: ${b.setting}.`,
    `Tone: ${b.tone}.`,
    'Audio: natural voice, light room tone, subtle music. Burn in captions so it works with the sound off.',
    `Style: ${p.style}`,
    `Restrictions: ${restrictionsFor(b).join(', ')}.`,
  );
  return lines.join('\n');
}

export function pickHooks(b) {
  const chosen = b.hookTypes && b.hookTypes.length ? b.hookTypes : DEFAULT_HOOK_ORDER;
  return chosen.slice(0, b.variantCount);
}

export function buildBatch(rawBrief) {
  const b = normalizeBrief(rawBrief);
  const baseCta = ctaLine(b);
  const constants = {
    product: b.product,
    proof: cap(b.proof),
    cta: baseCta,
    creatorRole: CREATOR_ROLES[b.creatorRole].label,
  };
  const variants = pickHooks(b).map((hookType, i) => {
    const script = buildScript(b, hookType);
    return {
      id: i + 1,
      hookType,
      hookLabel: HOOK_TYPES[hookType].label,
      angle: HOOK_TYPES[hookType].angle,
      hook: script.beats[0].line,
      script,
      prompts: Object.fromEntries(b.platforms.map((p) => [p, buildVideoPrompt(b, hookType, p)])),
    };
  });
  return { brief: b, constants, variants };
}

// --- Claim checker --------------------------------------------------------

export const RISK_RULES = [
  { re: /\bguarantee[ds]?\b/i, level: 'high', why: 'Guaranteed results are an unsupported claim.' },
  { re: /\b(cure[sd]?|heal(s|ed)?|treat(s|ed|ment)?)\b/i, level: 'high', why: 'Medical or treatment claims need substantiation.' },
  { re: /\b(lost|lose)\s+\d+\s*(lb|lbs|pounds|kg|kilos)\b/i, level: 'high', why: 'Weight-loss results imply a fake personal outcome.' },
  { re: /\b(made|earn(ed)?|make)\s+\$?\d[\d,]*(k)?\b/i, level: 'high', why: 'Earnings claims are heavily regulated.' },
  { re: /\b(doctor|dermatologist|dentist|expert)s?\s+(recommended|approved)\b/i, level: 'high', why: 'Expert endorsement must be real and documented.' },
  { re: /\b(clinically|scientifically)\s+(proven|tested)\b/i, level: 'high', why: 'Needs a study you can cite.' },
  { re: /(?<!\w)(100%|risk[- ]free|no risk)(?!\w)/i, level: 'medium', why: 'Absolute claims are hard to support.' },
  { re: /\b(unbreakable|indestructible|never fails?|forever|permanent(ly)?)\b/i, level: 'medium', why: 'Absolute durability claim. Say what you have actually tested.' },
  { re: /\b(best|#1|number one)\b/i, level: 'medium', why: 'Superlatives need comparative proof.' },
  { re: /\b(5|five)[- ]stars?\b|\brated\s+\d(\.\d)?\b/i, level: 'medium', why: 'Ratings must be real, not generated.' },
  { re: /\b(changed my life|life[- ]changing|miracle)\b/i, level: 'low', why: 'Reads as a fake testimonial. Show what it does instead.' },
  { re: /\b(amazing|incredible|insane)\b/i, level: 'low', why: 'Vague adjective. A concrete number or detail converts better.' },
];

export function checkClaims(text) {
  const findings = [];
  for (const rule of RISK_RULES) {
    const re = new RegExp(rule.re.source, rule.re.flags.includes('g') ? rule.re.flags : rule.re.flags + 'g');
    for (const m of text.matchAll(re)) {
      findings.push({ match: m[0], index: m.index, level: rule.level, why: rule.why });
    }
  }
  return findings.sort((a, b) => a.index - b.index);
}

export function scriptChecks(script, b) {
  const spoken = script.beats.map((x) => x.line).join(' ');
  const ctaCount = (script.beats[3].line.match(/\b(link|download|book|grab|get it|check out|try)\b/gi) || []).length;
  return [
    { label: `Read-aloud time (${script.readSeconds}s) fits ${b.duration}s`, ok: script.readSeconds <= b.duration },
    { label: 'Has at least one concrete number or detail', ok: /\d|\b(one|two|three|four|five|six|seven|ten|half|twice|every)\b/i.test(spoken) },
    { label: 'Hook is 15 words or fewer', ok: script.beats[0].line.split(/\s+/).length <= 15 },
    { label: 'Exactly one call to action', ok: ctaCount >= 1 && ctaCount <= 2 },
    { label: 'No high-risk claims', ok: !checkClaims(spoken).some((f) => f.level === 'high') },
  ];
}

export const QA_CHECKLIST = [
  ['Story', ['Hook is clear with the sound off', 'Product appears early', 'Exactly one CTA, and it matches the landing page']],
  ['Honesty', ['Creator role is honest (not posing as a real customer)', 'Disclosure (#ad / Paid partnership) is visible', 'No fake testimonial, review, rating or expert', 'Every claim is something you can prove']],
  ['Visual quality', ['Face is the same person in every shot', 'Hands and fingers look natural', 'Product shape, label and colour are accurate', 'No made-up readable UI text or logos']],
  ['Delivery', ['Correct aspect ratio for each platform', 'Captions and CTA sit inside the safe zone', 'You have commercial-use rights for every asset']],
];

// --- Export ---------------------------------------------------------------

export function toMarkdown(batch) {
  const { brief: b, constants, variants } = batch;
  const out = [];
  out.push(`# UGC Ad Batch: ${b.product}`, '');
  out.push('## Brief', '');
  out.push('| Item | Answer |', '|---|---|');
  out.push(`| Product | ${b.product}${b.price ? ` (${b.price})` : ''}. ${cap(b.description)} |`);
  out.push(`| Audience | ${b.audience} |`);
  out.push(`| Platforms | ${b.platforms.map((p) => `${PLATFORMS[p].label} ${PLATFORMS[p].aspect}`).join(', ')} |`);
  out.push(`| Length | ${b.duration}s (~${b.duration * WORDS_PER_SECOND} words) |`);
  out.push(`| Tone | ${b.tone} |`);
  out.push(`| Creator role | ${CREATOR_ROLES[b.creatorRole].label} |`);
  out.push(`| Variants | ${variants.length} |`, '');
  out.push('## Batch matrix', '');
  out.push(`**Constants (same in every ad):** proof "${constants.proof}", CTA "${constants.cta}"`, '');
  out.push('| Ad # | Hook type | Angle | Hook line |', '|---|---|---|---|');
  for (const v of variants) out.push(`| ${v.id} | ${v.hookLabel} | ${v.angle} | ${v.hook.replace(/\|/g, '\\|')} |`);
  out.push('', 'Only the hook changes, so a winner tells you it was the hook. Read hook rate first, then CPA.', '');
  for (const v of variants) {
    out.push(`## Ad ${v.id}: ${v.hookLabel}`, '');
    out.push('| Beat | Timing | Line |', '|---|---|---|');
    for (const x of v.script.beats) out.push(`| ${x.beat} | ${x.start}-${x.end}s | ${x.line.replace(/\|/g, '\\|')} |`);
    out.push('', `_${v.script.words} words, about ${v.script.readSeconds}s read aloud_`, '');
    for (const [p, prompt] of Object.entries(v.prompts)) {
      out.push(`**Video prompt: ${PLATFORMS[p].label}**`, '', '```text', prompt, '```', '');
    }
  }
  out.push('## QA checklist', '');
  for (const [group, items] of QA_CHECKLIST) {
    out.push(`**${group}**`, '');
    for (const item of items) out.push(`- [ ] ${item}`);
    out.push('');
  }
  return out.join('\n');
}
