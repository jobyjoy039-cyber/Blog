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
html, body { width:540px; height:675px; background:var(--bg); }
body { position:relative; font-family:'Inter',sans-serif; color:var(--body); -webkit-font-smoothing:antialiased; }
.label { position:absolute; top:32px; left:40px; font-size:9px; font-weight:500; letter-spacing:.18em; color:var(--head); opacity:.7; }
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
.rows div { font-size:19px; line-height:1.35; margin-top:14px; }
.rows b { font-weight:500; color:var(--head); display:inline-block; width:72px; }
.flows { margin-top:24px; }
.flows .flow { margin-top:20px; }
.flows .from { font-size:19px; font-weight:500; line-height:1.35; }
.flows .to { font-size:18px; line-height:1.4; margin-top:4px; }
.flows .flow:first-child .from { color:var(--head); }
ol { list-style:none; margin-top:24px; }
ol li { display:flex; gap:16px; font-size:19px; font-weight:500; line-height:1.35; margin-top:16px; color:var(--body); }
ol li span { font-family:'Inter Tight',sans-serif; font-weight:700; font-size:22px; color:var(--head); min-width:32px; }
.foot { font-size:15px; line-height:1.45; margin-top:32px; opacity:.9; }
.accent { color:var(--accent); }
.cta { font-size:22px; font-weight:500; line-height:1.35; color:var(--head); }
.signoff { font-size:16px; margin-top:24px; }
`;

function slideHtml(s, label) {
  const parts = [];
  if (s.tag) parts.push(`<div class="tag">${s.tag}</div>`);
  if (s.h1) parts.push(`<h1>${s.h1}</h1>`);
  if (s.h2) parts.push(`<h2>${s.h2}</h2>`);
  if (s.divider) parts.push(`<div class="divider"></div>`);
  if (s.equation) parts.push(`<div class="equation">${s.equation}</div>`);
  if (s.body) parts.push(`<div class="body">${s.body.map(p => `<p>${p}</p>`).join('')}</div>`);
  if (s.rows) parts.push(`<div class="rows">${s.rows.map(([k, v]) => `<div><b>${k}</b>${v}</div>`).join('')}</div>`);
  if (s.flows) parts.push(`<div class="flows">${s.flows.map(([from, ...to]) => `<div class="flow"><div class="from">${from}</div><div class="to">→ ${to.join(' → ')}</div></div>`).join('')}</div>`);
  if (s.list) parts.push(`<ol>${s.list.map((t, i) => `<li><span>0${i + 1}</span>${t}</li>`).join('')}</ol>`);
  if (s.statement) parts.push(`<div class="statement">${s.statement}</div>`);
  if (s.cta) parts.push(`<div class="cta">${s.cta}</div>`);
  if (s.signoff) parts.push(`<div class="signoff">${s.signoff}</div>`);
  if (s.foot) parts.push(`<div class="foot">${s.foot}</div>`);
  return `<!doctype html><html><head><meta charset="utf-8">
<style>${fontCss}${css}</style></head><body>
<div class="label">${label}</div>
<div class="content pos-${s.pos || 'upper'}"><div class="inner">${parts.join('\n')}</div></div>
<div class="handle">@ritvayalife</div>
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
    await page.setContent(slideHtml(s, c.label), { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const out = path.join(dir, `${String(i + 1).padStart(2, '0')}.png`);
    await page.screenshot({ path: out });
    console.log(out);
  }
}
await browser.close();
