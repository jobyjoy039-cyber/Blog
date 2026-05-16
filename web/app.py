#!/usr/bin/env python3
"""
Claude Blog — Local Browser Runner
Uses the `claude` CLI (your Claude subscription) — no API key needed.

Setup:
    pip install -r web/requirements.txt
    python3 web/app.py

Then open: http://localhost:5000
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import markdown
from flask import (Flask, Response, jsonify, redirect,
                   render_template_string, request, send_file,
                   stream_with_context, url_for)

ROOT         = Path(__file__).parent.parent
KEYWORD_DIR  = ROOT / "keyword-research"
PERF_DIR     = ROOT / "performance"
PERSONAS_DIR = ROOT / "personas"
REPURP_DIR   = ROOT / "repurposed"
CLUSTER_MAP  = ROOT / "skills" / "blog-cluster" / "templates" / "cluster-map.html"
SKILLS_DIR   = ROOT / "skills"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Skill catalogue
# ---------------------------------------------------------------------------

SKILLS = {
    "keyword-research": {
        "label": "Keyword Research",
        "icon": "🔍",
        "skill_dir": "blog-keyword-research",
        "description": "65+ prioritized keywords with SERP analysis, PAA mining, and cluster assignments.",
        "fields": [
            {"name": "topic",  "label": "Topic or Niche", "type": "text",
             "placeholder": "e.g. AI blog writing tools, content marketing for SaaS"},
            {"name": "depth",  "label": "Depth", "type": "select",
             "options": [("standard","Standard — 65+ keywords, SERP analysis"),
                         ("quick","Quick — 10 keywords, fast"),
                         ("deep","Deep — 100+ keywords, full competitive")]},
            {"name": "locale", "label": "Locale", "type": "text",
             "placeholder": "en-US", "default": "en-US"},
        ],
        "prompt": "Run keyword research for: {topic}\nDepth: {depth}\nLocale: {locale}",
        "save_dir": "keyword-research", "save_prefix": "kw",
        "web_tools": True,
    },
    "write": {
        "label": "Write Post",
        "icon": "✍️",
        "skill_dir": "blog-write",
        "description": "Full SEO-optimized blog post from a keyword or topic.",
        "fields": [
            {"name": "keyword",    "label": "Target Keyword / Topic", "type": "text",
             "placeholder": "e.g. how to write blog posts that rank"},
            {"name": "word_count", "label": "Word Count", "type": "select",
             "options": [("1500","1,500 words"),("2500","2,500 words"),
                         ("3500","3,500 words"),("5000","5,000+ (pillar)")]},
            {"name": "tone", "label": "Tone", "type": "select",
             "options": [("conversational","Conversational"),("professional","Professional"),
                         ("authoritative","Authoritative"),("beginner-friendly","Beginner-friendly")]},
            {"name": "notes", "label": "Extra Instructions (optional)", "type": "textarea",
             "placeholder": "Include a comparison table, target beginners, add FAQ…",
             "required": False, "rows": 3},
        ],
        "prompt": "Write a blog post for: \"{keyword}\"\nWord count: {word_count}\nTone: {tone}\nNotes: {notes}",
        "save_dir": "posts", "save_prefix": "post",
        "web_tools": False,
    },
    "rewrite": {
        "label": "Rewrite / Optimize",
        "icon": "🔄",
        "skill_dir": "blog-rewrite",
        "description": "Optimize an existing post: sourced stats, E-E-A-T, SEO, AI citations.",
        "fields": [
            {"name": "content",        "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to optimize…", "rows": 10},
            {"name": "target_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. content marketing strategy"},
            {"name": "focus", "label": "Focus", "type": "select",
             "options": [("all","All — SEO + E-E-A-T + AI citations"),
                         ("seo","SEO & keywords"),("eeat","E-E-A-T & authority"),
                         ("aeo","AI citation readiness (GEO/AEO)")]},
        ],
        "prompt": "Optimize this post targeting \"{target_keyword}\".\nFocus: {focus}\n\n---\n{content}",
        "save_dir": "posts", "save_prefix": "rewrite",
        "web_tools": False,
    },
    "brief": {
        "label": "Content Brief",
        "icon": "📋",
        "skill_dir": "blog-brief",
        "description": "Detailed brief with competitive analysis, outline, and writing guidelines.",
        "fields": [
            {"name": "keyword",  "label": "Target Keyword", "type": "text",
             "placeholder": "e.g. best content marketing tools 2026"},
            {"name": "audience", "label": "Target Audience", "type": "text",
             "placeholder": "e.g. solo bloggers, B2B marketers"},
            {"name": "goal",     "label": "Goal", "type": "select",
             "options": [("rank","Rank on Google (SEO)"),("ai","Get cited by AI search (AEO/GEO)"),
                         ("convert","Drive conversions"),("authority","Build topical authority")]},
        ],
        "prompt": "Create a content brief for: \"{keyword}\"\nAudience: {audience}\nGoal: {goal}",
        "save_dir": "briefs", "save_prefix": "brief",
        "web_tools": True,
    },
    "outline": {
        "label": "Outline",
        "icon": "📐",
        "skill_dir": "blog-outline",
        "description": "SERP-informed heading hierarchy with word counts and PAA integration.",
        "fields": [
            {"name": "keyword",    "label": "Target Keyword", "type": "text",
             "placeholder": "e.g. how to do keyword research"},
            {"name": "word_count", "label": "Word Count", "type": "select",
             "options": [("1500","1,500"),("2500","2,500"),("3500","3,500"),("5000","5,000+")]},
        ],
        "prompt": "Create a detailed blog outline for: \"{keyword}\"\nTarget: {word_count} words",
        "save_dir": "outlines", "save_prefix": "outline",
        "web_tools": True,
    },
    "seo-check": {
        "label": "SEO Check",
        "icon": "✅",
        "skill_dir": "blog-seo-check",
        "description": "Validate title, meta, headings, keyword density, schema, internal links.",
        "fields": [
            {"name": "content",        "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to validate…", "rows": 10},
            {"name": "target_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. SEO blog writing"},
        ],
        "prompt": "SEO-check this post targeting \"{target_keyword}\":\n\n---\n{content}",
        "save_dir": None, "save_prefix": None,
        "web_tools": False,
    },
    "repurpose": {
        "label": "Repurpose",
        "icon": "♻️",
        "skill_dir": "blog-repurpose",
        "description": "Transform a post into Twitter thread, LinkedIn, YouTube script, Reddit, email.",
        "fields": [
            {"name": "content",   "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to repurpose…", "rows": 10},
            {"name": "platforms", "label": "Platforms", "type": "select",
             "options": [("all","All platforms"),("twitter","Twitter/X thread"),
                         ("linkedin","LinkedIn post"),("email","Email newsletter"),
                         ("youtube","YouTube script"),("reddit","Reddit post")]},
        ],
        "prompt": "Repurpose this post for: {platforms}\n\n---\n{content}",
        "save_dir": "repurposed", "save_prefix": "repurposed",
        "web_tools": False,
    },
    "geo": {
        "label": "GEO / AI Citations",
        "icon": "🤖",
        "skill_dir": "blog-geo",
        "description": "Audit for AI citation readiness: ChatGPT, Claude, Perplexity, Google AI Overviews.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to audit…", "rows": 10},
        ],
        "prompt": "Run a GEO/AEO audit and provide specific optimization recommendations:\n\n---\n{content}",
        "save_dir": None, "save_prefix": None,
        "web_tools": False,
    },
    "schema": {
        "label": "Schema Markup",
        "icon": "🏷️",
        "skill_dir": "blog-schema",
        "description": "Generate JSON-LD: Article, FAQPage, HowTo, BreadcrumbList, and more.",
        "fields": [
            {"name": "content",      "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post…", "rows": 8},
            {"name": "schema_types", "label": "Schema Types", "type": "select",
             "options": [("auto","Auto-detect (recommended)"),("article","Article"),
                         ("faq","FAQPage"),("howto","HowTo"),("all","All applicable")]},
        ],
        "prompt": "Generate JSON-LD schema ({schema_types}) for this post:\n\n---\n{content}",
        "save_dir": None, "save_prefix": None,
        "web_tools": False,
    },
    "factcheck": {
        "label": "Fact Check",
        "icon": "🔬",
        "skill_dir": "blog-factcheck",
        "description": "Verify statistics, claims, and sources. Flag anything unverifiable.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to fact-check…", "rows": 10},
        ],
        "prompt": "Fact-check all statistics and claims. Flag unverifiable ones and suggest replacements:\n\n---\n{content}",
        "save_dir": None, "save_prefix": None,
        "web_tools": True,
    },
    "calendar": {
        "label": "Editorial Calendar",
        "icon": "📅",
        "skill_dir": "blog-calendar",
        "description": "90-day editorial calendar with topic clusters and publishing schedule.",
        "fields": [
            {"name": "niche",     "label": "Blog Niche", "type": "text",
             "placeholder": "e.g. SaaS content marketing, personal finance, AI tools"},
            {"name": "frequency", "label": "Frequency", "type": "select",
             "options": [("weekly","Weekly (4/month)"),("biweekly","Bi-weekly (2/month)"),
                         ("daily","Daily (Mon–Fri)")]},
            {"name": "goal",      "label": "Goal", "type": "select",
             "options": [("traffic","Organic traffic"),("authority","Topical authority"),
                         ("leads","Lead generation"),("brand","Brand awareness")]},
        ],
        "prompt": "Create a 90-day editorial calendar for: {niche}\nFrequency: {frequency}\nGoal: {goal}",
        "save_dir": "keyword-research", "save_prefix": "calendar",
        "web_tools": False,
    },
    "decay": {
        "label": "Decay Detector",
        "icon": "📉",
        "skill_dir": "blog-decay",
        "description": "Detect stale stats, outdated references, and content decay risk.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to check for decay…", "rows": 10},
        ],
        "prompt": "Analyze this post for content decay — stale stats, outdated references, decay risk. Score each section:\n\n---\n{content}",
        "save_dir": None, "save_prefix": None,
        "web_tools": False,
    },
    "ab": {
        "label": "A/B Headlines",
        "icon": "🧪",
        "skill_dir": "blog-ab",
        "description": "Generate 5 headline variants across angles (Number, Curiosity, How-To, Question, Contrarian) with CTR scores.",
        "fields": [
            {"name": "topic",   "label": "Post Topic or Existing Title", "type": "text",
             "placeholder": "e.g. how to write blog posts that rank"},
            {"name": "keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. blog writing tips"},
        ],
        "prompt": "Generate A/B headline variants for a post about \"{topic}\" targeting \"{keyword}\".",
        "save_dir": None, "save_prefix": None,
        "web_tools": False,
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def claude_available() -> bool:
    return subprocess.run(["which", "claude"], capture_output=True).returncode == 0


def get_model() -> str:
    return os.environ.get("CLAUDE_MODEL", "")


def load_skill_prompt(skill_dir: str) -> str:
    path = SKILLS_DIR / skill_dir / "SKILL.md"
    if not path.exists():
        return f"You are a blog content specialist."
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        try:
            end = content.index("---", 3)
            return content[end + 3:].strip()
        except ValueError:
            pass
    return content.strip()


def list_saved(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    return sorted(
        [{"name": f.stem, "filename": f.name,
          "size_kb": round(f.stat().st_size / 1024, 1), "path": str(f)}
         for f in directory.glob("*.md")],
        key=lambda x: x["filename"], reverse=True
    )


def render_md_file(path: Path) -> str:
    return markdown.markdown(
        path.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "nl2br"],
        output_format="html"
    )


def save_result(content: str, directory: str, prefix: str) -> Path:
    p = ROOT / directory
    p.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    fp = p / f"{prefix}-{ts}.md"
    fp.write_text(content, encoding="utf-8")
    return fp


def score_color(score) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "#8b949e"
    if s >= 80: return "#3fb950"
    if s >= 60: return "#58a6ff"
    if s >= 40: return "#d29922"
    return "#f85149"

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#0d1117;--surface:#161b22;--surface2:#21262d;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--yellow:#d29922;--red:#f85149;--purple:#bc8cff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:14px;line-height:1.6;min-height:100vh}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:rgba(110,118,129,.15);padding:2px 5px;border-radius:4px;font-family:monospace;font-size:12px}

nav{background:var(--surface);border-bottom:1px solid var(--border);padding:0 20px;display:flex;align-items:center;height:50px;position:sticky;top:0;z-index:200;overflow-x:auto;gap:0}
.nav-brand{font-weight:700;font-size:15px;color:var(--text);margin-right:24px;white-space:nowrap;flex-shrink:0}
.nav-brand em{color:var(--accent);font-style:normal}
nav a.nav-link{color:var(--muted);padding:0 12px;height:50px;display:flex;align-items:center;font-size:13px;border-bottom:2px solid transparent;white-space:nowrap;transition:color .15s,border-color .15s}
nav a.nav-link:hover{color:var(--text);text-decoration:none}
nav a.nav-link.active{color:var(--text);border-bottom-color:var(--accent)}
.nav-spacer{flex:1}
.status-pill{background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:3px 11px;font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px;flex-shrink:0;cursor:default}
.status-pill.ok{border-color:rgba(63,185,80,.4);color:var(--green)}
.status-pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex-shrink:0}

.page{max-width:1080px;margin:0 auto;padding:28px 20px}
h1{font-size:21px;font-weight:700;margin-bottom:4px}
h2{font-size:15px;font-weight:600;margin-bottom:12px}
h3{font-size:13px;font-weight:600}
.sub{color:var(--muted);font-size:13px;margin-bottom:22px}
.sec-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}

.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:18px}
.grid{display:grid;gap:14px;margin-bottom:22px}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:760px){.g2,.g3,.g4{grid-template-columns:1fr}}
@media(min-width:761px) and (max-width:980px){.g4{grid-template-columns:repeat(2,1fr)}}

.stat-num{font-size:30px;font-weight:700;color:var(--accent);display:block;line-height:1.1}
.stat-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}

.skill-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:6px;transition:border-color .15s,transform .1s;cursor:pointer;text-decoration:none;color:var(--text)}
.skill-card:hover{border-color:var(--accent);transform:translateY(-1px);text-decoration:none;color:var(--text)}
.skill-icon{font-size:20px}
.skill-name{font-weight:600;font-size:13px}
.skill-desc{font-size:12px;color:var(--muted);line-height:1.4}

.form-group{margin-bottom:13px}
label.field-label{display:block;font-size:11px;font-weight:600;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
input[type=text],select,textarea{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px 11px;font-size:13px;font-family:inherit;outline:none;transition:border-color .15s}
input[type=text]:focus,select:focus,textarea:focus{border-color:var(--accent)}
select option{background:var(--surface)}
textarea{resize:vertical;min-height:100px;font-family:monospace;font-size:12px}

.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer;border:1px solid transparent;transition:all .15s;text-decoration:none;white-space:nowrap;line-height:1}
.btn:hover{text-decoration:none}
.btn-primary{background:var(--accent);color:#0d1117;border-color:var(--accent)}
.btn-primary:hover{background:#79c0ff;color:#0d1117}
.btn-secondary{background:transparent;color:var(--text);border-color:var(--border)}
.btn-secondary:hover{background:var(--border)}
.btn-ghost{background:transparent;color:var(--muted);border-color:transparent}
.btn-ghost:hover{color:var(--text);background:var(--surface2)}
.btn-sm{padding:5px 11px;font-size:12px}
.btn[disabled]{opacity:.5;cursor:not-allowed;pointer-events:none}

.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
.badge-blue{background:rgba(88,166,255,.15);color:var(--accent)}
.badge-green{background:rgba(63,185,80,.15);color:var(--green)}
.badge-yellow{background:rgba(210,153,34,.15);color:var(--yellow)}
.badge-red{background:rgba(248,81,73,.15);color:var(--red)}

.alert{border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px}
.alert-warn{background:rgba(210,153,34,.1);border:1px solid rgba(210,153,34,.3);color:var(--yellow)}
.alert-info{background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.3);color:var(--accent)}
.alert-success{background:rgba(63,185,80,.1);border:1px solid rgba(63,185,80,.3);color:var(--green)}
.alert-error{background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.3);color:var(--red)}

.output-wrap{display:flex;flex-direction:column;height:100%}
.output-toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-bottom:none;border-radius:8px 8px 0 0}
.output-toolbar .title{font-size:12px;color:var(--muted);flex:1}
.output-box{background:var(--bg);border:1px solid var(--border);border-radius:0 0 8px 8px;padding:18px;min-height:240px;max-height:72vh;overflow-y:auto;font-size:13px;line-height:1.7;flex:1}
.output-box.empty{display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:13px;flex-direction:column;gap:8px}
.cursor{display:inline-block;width:7px;height:13px;background:var(--accent);margin-left:2px;animation:blink .8s step-end infinite;vertical-align:text-bottom}
@keyframes blink{50%{opacity:0}}

.md h1{font-size:18px;margin:18px 0 8px;border-bottom:1px solid var(--border);padding-bottom:6px}
.md h2{font-size:15px;margin:16px 0 7px}
.md h3{font-size:13px;margin:13px 0 5px}
.md h4{font-size:12px;margin:10px 0 4px;color:var(--muted)}
.md p{margin-bottom:9px}
.md ul,.md ol{margin:6px 0 10px 20px}
.md li{margin-bottom:3px}
.md code{background:rgba(110,118,129,.15);padding:2px 5px;border-radius:4px;font-size:12px}
.md pre{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px;overflow-x:auto;margin:10px 0}
.md pre code{background:none;padding:0;font-size:12px}
.md table{border-collapse:collapse;width:100%;margin:10px 0;font-size:12px}
.md th{background:var(--surface2);border:1px solid var(--border);padding:6px 10px;text-align:left;font-weight:600}
.md td{border:1px solid var(--border);padding:6px 10px}
.md tr:nth-child(even) td{background:rgba(22,27,34,.4)}
.md blockquote{border-left:3px solid var(--border);padding-left:14px;color:var(--muted);margin:10px 0}
.md hr{border:none;border-top:1px solid var(--border);margin:18px 0}
.md strong{font-weight:600}
.md a{color:var(--accent)}

.report-list{list-style:none}
.report-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);color:var(--text);transition:color .1s}
.report-item:hover{color:var(--accent);text-decoration:none}
.report-item:last-child{border-bottom:none}
.report-item .meta{color:var(--muted);font-size:11px;margin-left:auto;white-space:nowrap}

.spinner{width:13px;height:13px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .5s linear infinite;display:inline-block;flex-shrink:0}
@keyframes spin{to{transform:rotate(360deg)}}

.score-big{font-size:50px;font-weight:700;line-height:1}
.score-bar-wrap{background:var(--border);border-radius:4px;height:5px;margin:5px 0 2px}
.score-bar{height:5px;border-radius:4px;transition:width .5s}
.score-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}
.score-item{background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:11px 13px}
.score-item .sname{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.score-item .sval{font-size:20px;font-weight:700;margin:2px 0 1px}

/* two-col skill layout */
.skill-layout{display:grid;grid-template-columns:360px 1fr;gap:20px;align-items:start}
@media(max-width:800px){.skill-layout{grid-template-columns:1fr}}
"""

# ---------------------------------------------------------------------------
# JavaScript (streaming + markdown renderer)
# ---------------------------------------------------------------------------

JS = r"""
/* ---- Skill streaming ---- */
async function runSkill(skillId) {
  const form     = document.getElementById('skill-form');
  const output   = document.getElementById('output');
  const statusEl = document.getElementById('run-status');
  const runBtn   = document.getElementById('run-btn');
  const saveBtn  = document.getElementById('save-btn');
  const copyBtn  = document.getElementById('copy-btn');

  const fields = {};
  new FormData(form).forEach((v, k) => fields[k] = v);

  output.innerHTML = '';
  output.classList.remove('empty');
  runBtn.disabled = true;
  if (saveBtn) saveBtn.style.display = 'none';
  statusEl.innerHTML = '<div class="spinner"></div> <span>Waiting for Claude…</span>';

  let fullText = '';
  const cursor = document.createElement('span');
  cursor.className = 'cursor';

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({skill: skillId, fields})
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({error: resp.statusText}));
      statusEl.textContent = '✗ ' + (err.error || 'Error');
      output.classList.add('empty');
      output.innerHTML = '<span style="color:var(--red)">' + (err.error || 'Request failed') + '</span>';
      runBtn.disabled = false;
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    output.appendChild(cursor);

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      const raw = decoder.decode(value, {stream: true});
      raw.split('\n').forEach(line => {
        if (!line.startsWith('data: ')) return;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') return;
        try {
          const d = JSON.parse(payload);
          if (d.text) {
            fullText += d.text;
            cursor.remove();
            output.innerHTML = renderMd(fullText);
            output.appendChild(cursor);
            output.scrollTop = output.scrollHeight;
            statusEl.innerHTML = '<div class="spinner"></div> <span>Streaming…</span>';
          }
          if (d.error) {
            statusEl.textContent = '✗ ' + d.error;
            output.classList.add('empty');
            output.innerHTML = '<span style="color:var(--red)">' + d.error + '</span>';
          }
        } catch(e) {}
      });
    }

    cursor.remove();
    const words = fullText.trim().split(/\s+/).length;
    statusEl.textContent = '✓ Done · ' + words + ' words';
    runBtn.disabled = false;
    window._lastOutput = fullText;

    if (copyBtn) copyBtn.style.display = 'flex';
    if (saveBtn && fullText.trim()) {
      saveBtn.style.display = 'flex';
      saveBtn.onclick = () => saveOutput(skillId, fullText, saveBtn);
    }

  } catch(e) {
    cursor.remove();
    statusEl.textContent = '✗ ' + e.message;
    runBtn.disabled = false;
  }
}

async function saveOutput(skillId, content, btn) {
  btn.disabled = true;
  btn.textContent = 'Saving…';
  const r = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({skill: skillId, content})
  });
  const d = await r.json();
  if (d.path) {
    btn.textContent = '✓ Saved: ' + d.filename;
  } else {
    btn.textContent = '✗ ' + (d.error || 'Save failed');
    btn.disabled = false;
  }
}

function copyOutput() {
  if (!window._lastOutput) return;
  navigator.clipboard.writeText(window._lastOutput).then(() => {
    const btn = document.getElementById('copy-btn');
    if (btn) { const t = btn.textContent; btn.textContent = '✓ Copied'; setTimeout(() => btn.textContent = t, 1600); }
  });
}

/* ---- Minimal markdown renderer ---- */
function renderMd(text) {
  let s = text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^#### (.+)$/gm,'<h4>$1</h4>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/^# (.+)$/gm,'<h1>$1</h1>')
    .replace(/^---+$/gm,'<hr>')
    .replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');

  // Tables
  s = s.replace(/((\|.+\|\n?)+)/gm, block => {
    const rows = block.trim().split('\n').filter(r => r.trim());
    if (rows.length < 2) return block;
    const isSep = r => /^\|[\s\-:|]+\|/.test(r);
    let thead='', tbody='', inHead=true;
    rows.forEach(row => {
      if (isSep(row)) { inHead=false; return; }
      const cells = row.split('|').filter((_,i,a)=>i>0&&i<a.length-1);
      const tag = inHead?'th':'td';
      const tr = cells.map(c=>`<${tag}>${c.trim()}</${tag}>`).join('');
      if (inHead) thead+=`<tr>${tr}</tr>`; else tbody+=`<tr>${tr}</tr>`;
    });
    return `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
  });

  // Code blocks
  s = s.replace(/```[\w]*\n([\s\S]+?)```/gm, (_,c) => `<pre><code>${c.trim()}</code></pre>`);

  // Lists
  s = s.replace(/(^[-*] .+\n?)+/gm, b => '<ul>'+b.trim().split('\n').map(l=>`<li>${l.replace(/^[-*] /,'')}</li>`).join('')+'</ul>');
  s = s.replace(/(^\d+\. .+\n?)+/gm, b => '<ol>'+b.trim().split('\n').map(l=>`<li>${l.replace(/^\d+\. /,'')}</li>`).join('')+'</ol>');

  // Paragraphs
  s = s.replace(/^(?!<[a-z]).+$/gm, l => l.trim() ? `<p>${l}</p>` : '');

  return '<div class="md">' + s + '</div>';
}
"""

# ---------------------------------------------------------------------------
# Base template renderer
# ---------------------------------------------------------------------------

def render(body: str, title: str = "Claude Blog", active: str = "") -> str:
    ok = claude_available()
    pill_cls = "ok" if ok else ""
    pill_label = "Claude connected" if ok else "claude CLI not found"
    model_label = (f" · {get_model()}" if get_model() else "")

    return render_template_string(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Claude Blog</title>
<style>{CSS}</style>
</head>
<body>
<nav>
  <div class="nav-brand">✍ Claude<em>Blog</em></div>
  <a href="/" class="nav-link {'active' if active=='home' else ''}">Home</a>
  <a href="/run/keyword-research" class="nav-link {'active' if active=='keyword-research' else ''}">Keywords</a>
  <a href="/run/write" class="nav-link {'active' if active=='write' else ''}">Write</a>
  <a href="/run/rewrite" class="nav-link {'active' if active=='rewrite' else ''}">Rewrite</a>
  <a href="/run/brief" class="nav-link {'active' if active=='brief' else ''}">Brief</a>
  <a href="/saved" class="nav-link {'active' if active=='saved' else ''}">Saved</a>
  <a href="/analyze" class="nav-link {'active' if active=='analyze' else ''}">Analyzer</a>
  <a href="/cluster-map" class="nav-link {'active' if active=='cluster' else ''}">Clusters</a>
  <a href="/settings" class="nav-link {'active' if active=='settings' else ''}">Settings</a>
  <div class="nav-spacer"></div>
  <div class="status-pill {pill_cls}" title="Using your Claude subscription — no API key needed">
    <span class="dot"></span>{pill_label}{model_label}
  </div>
</nav>
<div class="page">
{body}
</div>
<script>{JS}</script>
</body>
</html>""")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    kw_count   = len(list_saved(KEYWORD_DIR))
    perf_count = len(list_saved(PERF_DIR))
    ok = claude_available()

    warn = "" if ok else """<div class="alert alert-error">
      <strong>claude CLI not found.</strong>
      Install Claude Code from <a href="https://claude.ai/code" target="_blank">claude.ai/code</a>,
      then restart this app. It uses your Claude subscription — no API key needed.
    </div>"""

    skill_cards = "".join(
        f'<a class="skill-card" href="/run/{sid}">'
        f'<div class="skill-icon">{s["icon"]}</div>'
        f'<div class="skill-name">{s["label"]}</div>'
        f'<div class="skill-desc">{s["description"]}</div>'
        f'</a>'
        for sid, s in SKILLS.items()
    )

    body = f"""
<h1>Claude Blog</h1>
<p class="sub">Local AI blog suite · v1.9.0 · {len(SKILLS)} skills · powered by your Claude subscription</p>

{warn}

<div class="grid g4" style="margin-bottom:22px">
  <div class="card"><span class="stat-num">{len(SKILLS)}</span><div class="stat-label">Skills</div></div>
  <div class="card"><span class="stat-num">15</span><div class="stat-label">Agents</div></div>
  <div class="card"><span class="stat-num">{kw_count}</span><div class="stat-label">Keyword reports</div></div>
  <div class="card"><span class="stat-num">{perf_count}</span><div class="stat-label">Performance reports</div></div>
</div>

<div class="sec-header"><h2>Skills</h2></div>
<div class="grid g4" style="margin-bottom:26px">{skill_cards}</div>

<div class="grid g2">
  <div class="card">
    <h2>How it works</h2>
    <ol style="margin-left:18px;font-size:13px;line-height:2.1">
      <li>Pick a skill above (e.g. <a href="/run/keyword-research">Keyword Research</a>)</li>
      <li>Fill the form and click <strong>Run</strong></li>
      <li>Output streams live — same model as your Claude subscription</li>
      <li>Click <strong>Save</strong> to store the result locally</li>
    </ol>
  </div>
  <div class="card">
    <h2>Local tools (no Claude needed)</h2>
    <div style="display:flex;flex-direction:column;gap:8px">
      <a href="/analyze" class="btn btn-secondary">📊 Blog Post Analyzer — 100-point scoring</a>
      <a href="/cluster-map" class="btn btn-secondary">🌐 Cluster Map Visualizer</a>
      <a href="/saved" class="btn btn-secondary">📁 Browse Saved Files</a>
    </div>
  </div>
</div>
"""
    return render(body, title="Dashboard", active="home")


# ---------------------------------------------------------------------------
# Skill runner page
# ---------------------------------------------------------------------------

@app.route("/run/<skill_id>")
def run_skill(skill_id: str):
    if skill_id not in SKILLS:
        return redirect(url_for("home"))

    s   = SKILLS[skill_id]
    ok  = claude_available()

    fields_html = ""
    for f in s["fields"]:
        req  = f.get("required", True)
        name = f["name"]
        lbl  = f["label"]
        if f["type"] == "text":
            default = f.get("default", "")
            ph      = f.get("placeholder", "")
            fields_html += f'<div class="form-group"><label class="field-label">{lbl}</label><input type="text" name="{name}" placeholder="{ph}" value="{default}" {"required" if req else ""}></div>'
        elif f["type"] == "select":
            opts = "".join(f'<option value="{v}">{l}</option>' for v, l in f["options"])
            fields_html += f'<div class="form-group"><label class="field-label">{lbl}</label><select name="{name}">{opts}</select></div>'
        elif f["type"] == "textarea":
            rows = f.get("rows", 8)
            ph   = f.get("placeholder", "")
            fields_html += f'<div class="form-group"><label class="field-label">{lbl}</label><textarea name="{name}" rows="{rows}" placeholder="{ph}" {"required" if req else ""}></textarea></div>'

    other = "".join(
        f'<a href="/run/{sid}" class="btn btn-ghost btn-sm">{sv["icon"]} {sv["label"]}</a>'
        for sid, sv in SKILLS.items() if sid != skill_id
    )

    warn = "" if ok else '<div class="alert alert-warn">Claude CLI not found — <a href="/settings">see setup</a></div>'

    body = f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
  <a href="/" class="btn btn-ghost btn-sm">← Home</a>
  <h1>{s["icon"]} {s["label"]}</h1>
</div>
<p class="sub">{s["description"]}</p>
{warn}

<div class="skill-layout">
<div>
  <div class="card">
    <form id="skill-form" onsubmit="event.preventDefault();runSkill('{skill_id}')">
      {fields_html}
      <div style="display:flex;align-items:center;gap:10px;margin-top:4px;flex-wrap:wrap">
        <button type="submit" class="btn btn-primary" id="run-btn" {"disabled" if not ok else ""}>
          ⚡ Run
        </button>
        <span id="run-status" style="font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px"></span>
      </div>
    </form>
  </div>
  <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:6px">{other}</div>
</div>

<div class="output-wrap" style="min-height:360px">
  <div class="output-toolbar">
    <span class="title">Output</span>
    <button class="btn btn-ghost btn-sm" id="copy-btn" onclick="copyOutput()" style="display:none">⎘ Copy</button>
    <button class="btn btn-secondary btn-sm" id="save-btn" style="display:none">💾 Save</button>
  </div>
  <div class="output-box empty" id="output">
    <span>Fill the form and click Run</span>
    <span style="font-size:11px">Output streams token-by-token</span>
  </div>
</div>
</div>
"""
    return render(body, title=s["label"], active=skill_id)


# ---------------------------------------------------------------------------
# Streaming API — uses `claude -p` subprocess
# ---------------------------------------------------------------------------

@app.route("/api/run", methods=["POST"])
def api_run():
    if not claude_available():
        return jsonify({"error": "claude CLI not found. Install Claude Code from claude.ai/code"}), 503

    data     = request.get_json()
    skill_id = data.get("skill", "")
    fields   = data.get("fields", {})

    if skill_id not in SKILLS:
        return jsonify({"error": f"Unknown skill: {skill_id}"}), 400

    s             = SKILLS[skill_id]
    system_prompt = load_skill_prompt(s["skill_dir"])
    use_web       = s.get("web_tools", False)

    try:
        user_msg = s["prompt"].format(**{k: v or "" for k, v in fields.items()})
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    def generate():
        # Write system prompt to temp file to avoid shell-length limits
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                         delete=False, encoding="utf-8") as tf:
            tf.write(system_prompt)
            sys_file = tf.name

        try:
            allowed = "WebSearch,WebFetch" if use_web else ""
            cmd = [
                "claude", "-p", user_msg,
                "--system-prompt", f"@{sys_file}",
                "--output-format", "stream-json",
                "--include-partial-messages",
                "--verbose",
                "--no-session-persistence",
            ]
            if allowed:
                cmd += ["--allowedTools", allowed]
            else:
                cmd += ["--tools", ""]

            model = get_model()
            if model:
                cmd += ["--model", model]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(ROOT),
            )

            for raw_line in proc.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    # Real-time text delta: stream_event → content_block_delta → text_delta
                    if ev.get("type") == "stream_event":
                        inner = ev.get("event", {})
                        if inner.get("type") == "content_block_delta":
                            delta = inner.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield f"data: {json.dumps({'text': text})}\n\n"
                    # Error events
                    elif ev.get("type") == "result" and ev.get("is_error"):
                        msg = ev.get("result", "Unknown error")
                        yield f"data: {json.dumps({'error': msg})}\n\n"
                except json.JSONDecodeError:
                    pass

            proc.wait()
            if proc.returncode not in (0, None):
                err = proc.stderr.read() if proc.stderr else ""
                if err:
                    yield f"data: {json.dumps({'error': err[:300]})}\n\n"

        finally:
            os.unlink(sys_file)

        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Save endpoint
# ---------------------------------------------------------------------------

@app.route("/api/save", methods=["POST"])
def api_save():
    data     = request.get_json()
    skill_id = data.get("skill", "")
    content  = data.get("content", "")
    if skill_id not in SKILLS:
        return jsonify({"error": "Unknown skill"}), 400
    s = SKILLS[skill_id]
    if not s.get("save_dir"):
        return jsonify({"error": "This skill has no save directory configured"}), 400
    fp = save_result(content, s["save_dir"], s["save_prefix"])
    return jsonify({"path": str(fp), "filename": fp.name})


# ---------------------------------------------------------------------------
# Blog Analyzer (pure Python — no Claude needed)
# ---------------------------------------------------------------------------

@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    score_data   = None
    error        = ""
    post_content = ""

    if request.method == "POST":
        post_content = request.form.get("content", "").strip()
        filepath     = request.form.get("filepath", "").strip()
        script       = ROOT / "scripts" / "analyze_blog.py"

        if not script.exists():
            error = "scripts/analyze_blog.py not found in the project."
        elif not post_content and not filepath:
            error = "Paste content or enter a file path."
        else:
            tmp_path = None
            try:
                if post_content:
                    with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                                     delete=False, encoding="utf-8") as tf:
                        tf.write(post_content)
                        tmp_path = tf.name
                    target = tmp_path
                else:
                    target = filepath

                result = subprocess.run(
                    [sys.executable, str(script), target, "--format", "json"],
                    capture_output=True, text=True, timeout=30, cwd=ROOT
                )
                if tmp_path:
                    os.unlink(tmp_path)

                if result.returncode != 0:
                    error = (result.stderr or "Analyzer error.").strip()
                else:
                    out   = result.stdout.strip()
                    start = out.find("{")
                    if start != -1:
                        score_data = json.loads(out[start:])
                    else:
                        error = "Could not parse analyzer output."
            except Exception as ex:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                error = str(ex)

    score_html = ""
    if score_data:
        score  = score_data.get("score", score_data.get("total", 0))
        band   = score_data.get("band", "")
        color  = score_color(score)
        cats   = score_data.get("categories", score_data.get("breakdown", {}))
        cathtml = "".join(
            f'<div class="score-item"><div class="sname">{k.replace("_"," ")}</div>'
            f'<div class="sval" style="color:{score_color(v)}">{v}</div>'
            f'<div class="score-bar-wrap"><div class="score-bar" style="width:{min(float(v),100):.0f}%;background:{score_color(v)}"></div></div></div>'
            for k, v in cats.items()
        )
        issues    = score_data.get("issues", score_data.get("recommendations", []))
        issue_html = "".join(
            f'<li style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px;color:var(--muted)">▸ {i}</li>'
            for i in issues[:10]
        ) if issues else ""

        score_html = f"""
<div class="card" style="margin-bottom:12px">
  <div style="display:flex;align-items:flex-end;gap:16px;margin-bottom:12px">
    <div>
      <div class="score-big" style="color:{color}">{score}</div>
      <div style="color:var(--muted);font-size:11px">/100</div>
    </div>
    <div style="flex:1">
      <div style="font-size:14px;font-weight:600">{band}</div>
      <div class="score-bar-wrap">
        <div class="score-bar" style="width:{min(float(score),100):.0f}%;background:{color}"></div>
      </div>
    </div>
  </div>
  <div class="score-grid">{cathtml}</div>
</div>
{'<div class="card"><h3 style="margin-bottom:9px">Recommendations</h3><ul style="list-style:none">'+issue_html+'</ul></div>' if issue_html else ''}
"""

    body = f"""
<h1>📊 Blog Post Analyzer</h1>
<p class="sub">5-category, 100-point scoring — runs locally, no Claude needed</p>

<div style="display:grid;grid-template-columns:400px 1fr;gap:20px;align-items:start">
<div class="card">
  {'<div class="alert alert-error">'+error+'</div>' if error else ''}
  <form method="POST">
    <div class="form-group">
      <label class="field-label">Paste Blog Post (Markdown)</label>
      <textarea name="content" rows="12" placeholder="# Post Title&#10;&#10;Content…">{post_content}</textarea>
    </div>
    <div class="form-group">
      <label class="field-label">— or — File Path</label>
      <input type="text" name="filepath" placeholder="posts/my-post.md">
    </div>
    <button type="submit" class="btn btn-primary">📊 Analyze</button>
  </form>
</div>
<div>
  {score_html if score_html else '<div class="card" style="text-align:center;padding:40px;color:var(--muted)"><div style="font-size:36px;margin-bottom:10px">📊</div><div>Paste a post and click Analyze</div></div>'}
</div>
</div>
"""
    return render(body, title="Analyzer", active="analyze")


# ---------------------------------------------------------------------------
# Saved files browser
# ---------------------------------------------------------------------------

@app.route("/saved")
def saved():
    dirs = {"Keyword Research": KEYWORD_DIR, "Performance Reports": PERF_DIR,
            "Repurposed Content": REPURP_DIR, "Personas": PERSONAS_DIR}
    for sid, s in SKILLS.items():
        sd = s.get("save_dir")
        if sd and sd not in ("keyword-research","performance","repurposed","personas"):
            dirs[s["label"] + " Output"] = ROOT / sd

    sections = ""
    for label, path in dirs.items():
        files = list_saved(path)
        if not files:
            continue
        items = "".join(
            f'<li><a class="report-item" href="/saved/view?path={f["path"]}">'
            f'<span>📄</span>'
            f'<div><div>{f["name"]}</div><div style="font-size:11px;color:var(--muted)">{f["filename"]}</div></div>'
            f'<span class="meta">{f["size_kb"]} KB</span></a></li>'
            for f in files
        )
        sections += f'<div class="card" style="margin-bottom:12px"><div class="sec-header"><h2>{label}</h2><span class="badge badge-blue">{len(files)}</span></div><ul class="report-list">{items}</ul></div>'

    if not sections:
        sections = '<div class="alert alert-info">No saved files yet. Run a skill and click Save.</div>'

    body = f"<h1>📁 Saved Files</h1><p class='sub'>All files generated by Claude Blog skills</p>{sections}"
    return render(body, title="Saved Files", active="saved")


@app.route("/saved/view")
def saved_view():
    path = Path(request.args.get("path", ""))
    if not path.exists() or path.suffix != ".md":
        return redirect(url_for("saved"))
    html = render_md_file(path)
    body = f'<a href="/saved" class="btn btn-ghost btn-sm">← Saved Files</a><h1 style="margin-top:10px">{path.stem}</h1><p class="sub">{path}</p><div class="card md" style="margin-top:12px">{html}</div>'
    return render(body, title=path.stem, active="saved")


# ---------------------------------------------------------------------------
# Cluster Map
# ---------------------------------------------------------------------------

@app.route("/cluster-map")
def cluster_map():
    body = """
<div class="sec-header">
  <div><h1>🌐 Cluster Map</h1><p class="sub">Interactive force-directed topic cluster visualization</p></div>
  <a href="/cluster-map/full" target="_blank" class="btn btn-secondary btn-sm">⛶ Fullscreen</a>
</div>
<div style="border-radius:8px;overflow:hidden;border:1px solid var(--border);height:580px">
  <iframe src="/cluster-map/full" style="width:100%;height:100%;border:none"></iframe>
</div>
<div class="alert alert-info" style="margin-top:12px">
  Populate with real data: run the <strong>Keyword Research</strong> skill then
  <code>/blog cluster [topic]</code> in Claude Code to generate cluster data.
</div>
"""
    return render(body, title="Cluster Map", active="cluster")


@app.route("/cluster-map/full")
def cluster_map_full():
    if not CLUSTER_MAP.exists():
        return "cluster-map.html not found", 404
    return send_file(CLUSTER_MAP, mimetype="text/html")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved_msg = ""
    if request.method == "POST":
        model = request.form.get("model", "").strip()
        env_path = ROOT / ".env"
        try:
            lines = env_path.read_text().splitlines() if env_path.exists() else []
            new_lines, found = [], False
            for line in lines:
                if line.startswith("CLAUDE_MODEL="):
                    new_lines.append(f"CLAUDE_MODEL={model}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"CLAUDE_MODEL={model}")
            env_path.write_text("\n".join(new_lines) + "\n")
            if model:
                os.environ["CLAUDE_MODEL"] = model
            else:
                os.environ.pop("CLAUDE_MODEL", None)
            saved_msg = f"Saved. Model set to: {model or 'default'}."
        except Exception as ex:
            saved_msg = f"Error: {ex}"

    current_model = get_model()
    ok = claude_available()

    # Detect claude version
    ver_result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
    claude_ver = ver_result.stdout.strip() if ver_result.returncode == 0 else "not found"

    models = [
        ("", "Default (subscription model)"),
        ("claude-haiku-4-5-20251001", "Haiku 4.5 — fastest"),
        ("claude-sonnet-4-6", "Sonnet 4.6 — balanced"),
        ("claude-opus-4-7", "Opus 4.7 — most capable"),
    ]
    model_opts = "".join(
        f'<option value="{v}" {"selected" if v==current_model else ""}>{l}</option>'
        for v, l in models
    )

    body = f"""
<h1>⚙️ Settings</h1>
<p class="sub">Claude Blog runs through the <code>claude</code> CLI — your subscription handles authentication</p>

{'<div class="alert alert-success">'+saved_msg+'</div>' if saved_msg else ''}

<div class="grid g2" style="max-width:800px">

<div class="card">
  <h2>Claude CLI Status</h2>
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
    <div class="status-pill {'ok' if ok else ''}" style="font-size:13px;padding:6px 14px">
      <span class="dot"></span>{'Connected' if ok else 'Not found'}
    </div>
    <span style="font-size:12px;color:var(--muted)">{claude_ver}</span>
  </div>
  {'<p style="font-size:13px;color:var(--muted)">Your Claude subscription is active. All skills run through the CLI.</p>' if ok else
   '<div class="alert alert-warn">Install Claude Code from <a href="https://claude.ai/code" target="_blank">claude.ai/code</a>, then restart this app.</div>'}
</div>

<div class="card">
  <h2>Model Override (optional)</h2>
  <form method="POST">
    <div class="form-group">
      <label class="field-label">Model</label>
      <select name="model">{model_opts}</select>
      <div style="font-size:11px;color:var(--muted);margin-top:5px">
        Leave as Default to use whichever model your subscription provides.
      </div>
    </div>
    <button type="submit" class="btn btn-primary btn-sm">Save</button>
  </form>
</div>

</div>

<div class="card" style="max-width:800px;margin-top:0">
  <h2>Environment</h2>
  <table style="width:100%;font-size:13px;border-collapse:collapse">
    <tr><td style="padding:7px 0;border-bottom:1px solid var(--border);color:var(--muted);width:160px">Project root</td>
        <td style="padding:7px 0;border-bottom:1px solid var(--border)"><code>{ROOT}</code></td></tr>
    <tr><td style="padding:7px 0;border-bottom:1px solid var(--border);color:var(--muted)">Python</td>
        <td style="padding:7px 0;border-bottom:1px solid var(--border)"><code>{sys.version.split()[0]}</code></td></tr>
    <tr><td style="padding:7px 0;border-bottom:1px solid var(--border);color:var(--muted)">Skills loaded</td>
        <td style="padding:7px 0;border-bottom:1px solid var(--border)">{len(SKILLS)}</td></tr>
    <tr><td style="padding:7px 0;color:var(--muted)">.env file</td>
        <td style="padding:7px 0">{'<span style="color:var(--green)">exists</span>' if (ROOT/'.env').exists() else '<span style="color:var(--muted)">not found (optional)</span>'}</td></tr>
  </table>
</div>
"""
    return render(body, title="Settings", active="settings")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    ok   = claude_available()
    print(f"\n  Claude Blog Local Runner")
    print(f"  → http://localhost:{port}")
    print(f"  → Claude CLI: {'✓ found' if ok else '✗ not found — install from claude.ai/code'}")
    if get_model():
        print(f"  → Model override: {get_model()}")
    print()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
