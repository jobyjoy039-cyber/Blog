// Renders Ritvayalife carousels (carousels/*.json) to 1080×1350 PNGs.
// Layout is authored at half scale (540×675) and captured at 2× so the
// profile's type sizes stay readable on a phone.
//
// Usage: node render.mjs [slug ...]   (no args = render every carousel)
import { chromium } from 'playwright';
import { readFile, readdir, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(here, 'carousels');
const outDir = path.join(here, 'output');
const fontDir = path.join(here, 'fonts');

// Inline the brand fonts (Inter, Inter Tight — SIL OFL) so rendering needs no network.
let fontCss = await readFile(path.join(fontDir, 'fonts.css'), 'utf8');
for (const [, file] of fontCss.matchAll(/url\(([^)]+\.woff2)\)/g)) {
  const b64 = (await readFile(path.join(fontDir, file))).toString('base64');
  fontCss = fontCss.replace(`url(${file})`, `url(data:font/woff2;base64,${b64})`);
}

const css = `
:root { --bg:#F5F1E8; --head:#2E5E4E; --body:#6B6B6B; --accent:#C2A87D; }
* { margin:0; padding:0; box-sizing:border-box; }
html, body { width:540px; height:675px; background:var(--bg); overflow:hidden; }
.bg { position:absolute; inset:0; }
.frame { position:absolute; inset:16px; border:1px solid rgba(46,94,78,.14); border-radius:6px; pointer-events:none; }
.dots { position:absolute; bottom:34px; right:40px; display:flex; gap:6px; }
.dots i { width:5px; height:5px; border-radius:50%; background:rgba(46,94,78,.22); }
.dots i.on { width:16px; border-radius:3px; background:var(--head); }
.handle svg { vertical-align:-2px; margin-right:5px; }
.card { background:rgba(255,255,255,.55); border:1px solid rgba(46,94,78,.10); border-radius:10px; box-shadow:0 1px 2px rgba(46,94,78,.05); }
body { position:relative; font-family:'Inter',sans-serif; color:var(--body); -webkit-font-smoothing:antialiased; }
.label { position:absolute; top:34px; left:40px; font-size:9px; font-weight:500; letter-spacing:.18em; color:var(--head); opacity:.7; }
.handle { position:absolute; bottom:32px; left:40px; font-size:10px; font-weight:500; color:var(--body); opacity:.8; }
.content { position:absolute; left:40px; top:80px; bottom:90px; width:380px; display:flex; flex-direction:column; justify-content:center; }
.content > .inner { transform:translateY(var(--shift)); }
.pos-upper { --shift:-36px; } .pos-mid { --shift:0px; } .pos-low { --shift:40px; }
h1, h2, .statement { font-family:'Inter Tight',sans-serif; font-weight:700; color:var(--head); letter-spacing:-.01em; }
h1 { font-size:44px; line-height:1.08; }
h2 { font-size:28px; line-height:1.15; }
.statement { font-size:32px; line-height:1.18; }
.tag { font-size:9px; font-weight:500; letter-spacing:.16em; color:var(--body); margin-bottom:12px; }
.divider { height:1px; width:48px; background:var(--head); opacity:.25; margin-top:16px; }
.equation { font-family:'Inter Tight',sans-serif; font-weight:700; font-size:24px; color:var(--head); margin-top:24px; }
.body p { font-size:19px; line-height:1.4; margin-top:16px; }
.body p:first-child { margin-top:24px; }
.rows { margin-top:24px; }
.rows div { font-size:18px; line-height:1.35; margin-top:10px; padding:12px 16px; }
.rows b { font-weight:500; color:var(--head); display:inline-block; width:72px; }
.flows { margin-top:24px; }
.flows .flow { margin-top:12px; padding:14px 16px; }
.flows .flow:first-child { border-left:3px solid var(--head); }
.flows .from { font-size:19px; font-weight:500; line-height:1.35; }
.flows .to { font-size:18px; line-height:1.4; margin-top:4px; }
.flows .flow:first-child .from { color:var(--head); }
ol { list-style:none; margin-top:24px; }
ol li { display:flex; align-items:center; gap:14px; font-size:18px; font-weight:500; line-height:1.35; margin-top:10px; padding:12px 16px; color:var(--body); }
ol li span { font-family:'Inter Tight',sans-serif; font-weight:700; font-size:22px; color:var(--head); min-width:32px; }
.foot { font-size:15px; line-height:1.45; margin-top:24px; opacity:.9; padding-left:12px; border-left:2px solid rgba(46,94,78,.25); }
.statement::before { content:'“'; display:block; font-size:96px; line-height:.6; height:40px; color:rgba(46,94,78,.18); }
.cta-box { padding:24px 24px 22px; border-radius:14px; background:rgba(255,255,255,.55); border:1px solid rgba(46,94,78,.12); }
.accent { color:var(--accent); }
.cta { font-size:22px; font-weight:500; line-height:1.35; color:var(--head); }
.signoff { font-size:16px; margin-top:24px; }
.engage { margin-top:24px; }
.engage div { display:flex; align-items:center; gap:14px; padding:13px 16px; margin-top:10px; font-size:17px; line-height:1.35; }
.engage b { display:block; font-weight:500; color:var(--head); font-size:18px; }
.engage svg { flex:none; }
.follow { display:inline-block; margin-top:24px; padding:12px 22px; border-radius:999px; background:var(--accent); color:#fff; font-size:18px; font-weight:500; }
`;

const W = 540, H = 675;

// One leaf, tip pointing along +x, drawn at the origin.
const leaf = (x, y, rot, len, op) =>
  `<g transform="translate(${x} ${y}) rotate(${rot})" opacity="${op}">
    <path d="M0 0 C ${len * .3} ${-len * .28} ${len * .72} ${-len * .28} ${len} 0 C ${len * .72} ${len * .28} ${len * .3} ${len * .28} 0 0 Z" fill="rgba(46,94,78,.10)" stroke="#2E5E4E" stroke-width="1"/>
    <path d="M${len * .08} 0 L ${len * .9} 0" stroke="#2E5E4E" stroke-width=".7"/></g>`;

// A curved stem with alternating leaves.
function sprig(x, y, rot, scale, op = .35) {
  const leaves = [[18, -40, 34], [34, 40, 38], [52, -44, 40], [70, 42, 36], [86, -38, 30]]
    .map(([t, a, l]) => leaf(t * 1.4, -Math.sin(t / 30) * 10, a, l, 1)).join('');
  return `<g transform="translate(${x} ${y}) rotate(${rot}) scale(${scale})" opacity="${op}">
    <path d="M0 0 Q 70 -22 136 -6" fill="none" stroke="#2E5E4E" stroke-width="1.1"/>${leaves}
    ${leaf(136, -6, -8, 30, 1)}</g>`;
}

// Panorama spanning every slide: each slide shows its own 540px window, so the
// rhythm line and rings flow across the swipe.
function panorama(n) {
  const total = W * n, pts = [];
  for (let x = -20; x <= total + 20; x += 10) pts.push(`${x},${(560 + Math.sin(x / 150) * 26 + Math.sin(x / 61) * 6).toFixed(1)}`);
  const pts2 = pts.map(p => { const [x, y] = p.split(','); return `${x},${(+y + 16 + Math.sin(x / 90) * 5).toFixed(1)}`; });
  const rings = [];
  for (let i = 1; i < n; i += 2) {
    const cx = W * i, cy = i % 4 === 1 ? 118 : 600;
    for (const r of [46, 78, 112, 150]) rings.push(`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#2E5E4E" stroke-opacity="${(.16 - r / 1500).toFixed(3)}" stroke-width="1"/>`);
    rings.push(`<circle cx="${cx}" cy="${cy}" r="30" fill="#C2A87D" fill-opacity=".10"/>`);
  }
  return `<polyline points="${pts.join(' ')}" fill="none" stroke="#2E5E4E" stroke-opacity=".22" stroke-width="1.4"/>
    <polyline points="${pts2.join(' ')}" fill="none" stroke="#C2A87D" stroke-opacity=".35" stroke-width="1"/>
    ${rings.join('')}`;
}

function background(i, n) {
  const first = i === 0, last = i === n - 1;
  return `<svg class="bg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
    <defs>
      <radialGradient id="glow" cx="85%" cy="12%" r="75%"><stop offset="0" stop-color="#E8E2D6"/><stop offset="1" stop-color="#F5F1E8" stop-opacity="0"/></radialGradient>
      <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .18  0 0 0 0 .37  0 0 0 0 .31  0 0 0 .05 0"/></filter>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#glow)"/>
    <rect width="${W}" height="${H}" filter="url(#grain)"/>
    <g transform="translate(${-W * i} 0)">${panorama(n)}</g>
    ${first ? sprig(575, 610, -148, 1.6, .42) + sprig(560, 330, 175, .9, .22) : ''}
    ${last ? sprig(585, 585, -150, 1.4, .38) : ''}
    ${!first && !last ? sprig(548, 90, 150, .8, .22) : ''}
  </svg>`;
}

const icon = {
  save: '<path d="M7 4h10v16l-5-4-5 4z"/>',
  share: '<path d="M21 3 3 10l7 3 3 7z M10 13l11-10"/>',
  follow: '<circle cx="9" cy="8" r="4"/><path d="M2 20c0-4 3-6 7-6s7 2 7 6 M19 8v6 M16 11h6"/>',
};
const iconSvg = k => `<svg width="30" height="30" viewBox="0 0 24 24"><circle cx="12" cy="12" r="12" fill="rgba(46,94,78,.08)"/><g transform="translate(5 5) scale(.58)" fill="none" stroke="#2E5E4E" stroke-width="2" stroke-linejoin="round" stroke-linecap="round">${icon[k]}</g></svg>`;

const mark = `<svg width="11" height="11" viewBox="0 0 20 20"><path d="M3 17 C 3 8 9 3 17 3 C 17 11 12 17 3 17 Z M3 17 L 12 8" fill="none" stroke="#2E5E4E" stroke-width="1.6"/></svg>`;

function slideHtml(s, label, i, n) {
  const parts = [];
  if (s.tag) parts.push(`<div class="tag">${s.tag}</div>`);
  if (s.h1) parts.push(`<h1>${s.h1}</h1>`);
  if (s.h2) parts.push(`<h2>${s.h2}</h2>`);
  if (s.divider) parts.push(`<div class="divider"></div>`);
  if (s.equation) parts.push(`<div class="equation">${s.equation}</div>`);
  if (s.body) parts.push(`<div class="body">${s.body.map(p => `<p>${p}</p>`).join('')}</div>`);
  if (s.rows) parts.push(`<div class="rows">${s.rows.map(([k, v]) => `<div class="card"><b>${k}</b>${v}</div>`).join('')}</div>`);
  if (s.flows) parts.push(`<div class="flows">${s.flows.map(([from, ...to]) => `<div class="flow card"><div class="from">${from}</div><div class="to">→ ${to.join(' → ')}</div></div>`).join('')}</div>`);
  if (s.list) parts.push(`<ol>${s.list.map((t, i) => `<li class="card"><span>0${i + 1}</span>${t}</li>`).join('')}</ol>`);
  if (s.statement) parts.push(`<div class="statement">${s.statement}</div>`);
  if (s.cta) parts.push(`<div class="cta-box"><div class="cta">${s.cta}</div>${s.signoff ? `<div class="signoff">${s.signoff}</div>` : ''}</div>`);
  if (s.engage) parts.push(`<div class="engage">${s.engage.map(([k, t, d]) => `<div class="card">${iconSvg(k)}<span><b>${t}</b>${d}</span></div>`).join('')}</div>`);
  if (s.follow) parts.push(`<div class="follow">${s.follow}</div>`);
  if (s.foot) parts.push(`<div class="foot">${s.foot}</div>`);
  return `<!doctype html><html><head><meta charset="utf-8">
<style>${fontCss}${css}</style></head><body>
${background(i, n)}<div class="frame"></div>
<div class="label">${label}</div>
<div class="content pos-${s.pos || 'upper'}"><div class="inner">${parts.join('\n')}</div></div>
<div class="handle">${mark}@ritvayalife</div>
<div class="dots">${Array.from({ length: n }, (_, k) => `<i class="${k === i ? 'on' : ''}"></i>`).join('')}</div>
</body></html>`;
}

const wanted = process.argv.slice(2);
const files = (await readdir(dataDir)).filter(f => f.endsWith('.json'))
  .filter(f => !wanted.length || wanted.includes(f.replace(/\.json$/, '')));

const executablePath = existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined;
const browser = await chromium.launch(executablePath ? { executablePath } : {}).catch(() => chromium.launch());
const page = await browser.newPage({ viewport: { width: 540, height: 675 }, deviceScaleFactor: 2 });

for (const file of files) {
  const c = JSON.parse(await readFile(path.join(dataDir, file), 'utf8'));
  const dir = path.join(outDir, c.slug);
  await mkdir(dir, { recursive: true });
  for (const [i, s] of c.slides.entries()) {
    await page.setContent(slideHtml(s, c.label, i, c.slides.length), { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const out = path.join(dir, `${String(i + 1).padStart(2, '0')}.png`);
    await page.screenshot({ path: out });
    console.log(out);
  }
}
await browser.close();
