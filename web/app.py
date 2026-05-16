#!/usr/bin/env python3
"""
Claude Blog — Local Browser Runner
Runs all /blog skills directly via the Anthropic API.
No Claude Code CLI required.

Setup:
    cp .env.example .env          # add your ANTHROPIC_API_KEY
    pip install -r web/requirements.txt
    python3 web/app.py

Then open: http://localhost:5000
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import markdown
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template_string, request, send_file, stream_with_context, url_for

# Load .env from project root
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

KEYWORD_DIR   = ROOT / "keyword-research"
PERFORMANCE_DIR = ROOT / "performance"
PERSONAS_DIR  = ROOT / "personas"
REPURPOSED_DIR = ROOT / "repurposed"
CLUSTER_MAP   = ROOT / "skills" / "blog-cluster" / "templates" / "cluster-map.html"
SKILLS_DIR    = ROOT / "skills"
AGENTS_DIR    = ROOT / "agents"

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Skill catalogue — every entry becomes a runnable page
# ---------------------------------------------------------------------------

SKILLS = {
    "keyword-research": {
        "label": "Keyword Research",
        "icon": "🔍",
        "skill_dir": "blog-keyword-research",
        "description": "Generate 65+ prioritized keywords with SERP analysis, PAA mining, and cluster assignments.",
        "fields": [
            {"name": "topic", "label": "Topic or Niche", "type": "text",
             "placeholder": "e.g. AI blog writing tools, content marketing for SaaS"},
            {"name": "depth", "label": "Research Depth", "type": "select",
             "options": [("standard","Standard — 65+ keywords, SERP analysis"),
                         ("quick","Quick — 10 keywords, fast"),
                         ("deep","Deep — 100+ keywords, full competitive")]},
            {"name": "locale", "label": "Target Locale", "type": "text",
             "placeholder": "en-US", "default": "en-US"},
        ],
        "prompt_template": "Run keyword research for the topic: {topic}\nDepth: {depth}\nLocale: {locale}",
        "save_dir": "keyword-research",
        "save_prefix": "kw",
    },
    "write": {
        "label": "Write Post",
        "icon": "✍️",
        "skill_dir": "blog-write",
        "description": "Write a full SEO-optimized blog post from a keyword or topic.",
        "fields": [
            {"name": "keyword", "label": "Target Keyword / Topic", "type": "text",
             "placeholder": "e.g. how to write blog posts that rank"},
            {"name": "word_count", "label": "Target Word Count", "type": "select",
             "options": [("1500","1,500 words"),("2500","2,500 words"),
                         ("3500","3,500 words"),("5000","5,000+ words (pillar)")]},
            {"name": "tone", "label": "Tone", "type": "select",
             "options": [("conversational","Conversational"),("professional","Professional"),
                         ("authoritative","Authoritative"),("beginner-friendly","Beginner-friendly")]},
            {"name": "notes", "label": "Additional Instructions (optional)", "type": "textarea",
             "placeholder": "Include a comparison table, target beginners, add FAQ section…", "required": False},
        ],
        "prompt_template": "Write a blog post for: \"{keyword}\"\nTarget word count: {word_count} words\nTone: {tone}\nNotes: {notes}",
        "save_dir": "posts",
        "save_prefix": "post",
    },
    "rewrite": {
        "label": "Rewrite / Optimize",
        "icon": "🔄",
        "skill_dir": "blog-rewrite",
        "description": "Optimize an existing blog post: sourced stats, E-E-A-T signals, SEO, and AI citation readiness.",
        "fields": [
            {"name": "content", "label": "Existing Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post to optimize…", "rows": 12},
            {"name": "target_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. content marketing strategy"},
            {"name": "focus", "label": "Optimization Focus", "type": "select",
             "options": [("all","All — SEO + E-E-A-T + AI citations"),
                         ("seo","SEO & keyword optimization"),
                         ("eeat","E-E-A-T & authority signals"),
                         ("aeo","AI citation readiness (GEO/AEO)")]},
        ],
        "prompt_template": "Optimize the following blog post for the keyword \"{target_keyword}\".\nFocus: {focus}\n\n---\n{content}",
        "save_dir": "posts",
        "save_prefix": "rewrite",
    },
    "brief": {
        "label": "Content Brief",
        "icon": "📋",
        "skill_dir": "blog-brief",
        "description": "Generate a detailed content brief with competitive analysis, outline, and writing guidelines.",
        "fields": [
            {"name": "keyword", "label": "Target Keyword", "type": "text",
             "placeholder": "e.g. best content marketing tools 2026"},
            {"name": "audience", "label": "Target Audience", "type": "text",
             "placeholder": "e.g. solo bloggers, B2B marketers, SaaS founders"},
            {"name": "goal", "label": "Content Goal", "type": "select",
             "options": [("rank","Rank on Google (SEO)"),("ai","Get cited by AI search (AEO/GEO)"),
                         ("convert","Drive conversions"),("authority","Build topical authority")]},
        ],
        "prompt_template": "Create a content brief for: \"{keyword}\"\nTarget audience: {audience}\nPrimary goal: {goal}",
        "save_dir": "briefs",
        "save_prefix": "brief",
    },
    "outline": {
        "label": "Outline",
        "icon": "📐",
        "skill_dir": "blog-outline",
        "description": "SERP-informed heading hierarchy with H2/H3 structure, word counts, and PAA integration.",
        "fields": [
            {"name": "keyword", "label": "Target Keyword", "type": "text",
             "placeholder": "e.g. how to do keyword research"},
            {"name": "word_count", "label": "Target Word Count", "type": "select",
             "options": [("1500","1,500"),("2500","2,500"),("3500","3,500"),("5000","5,000+")]},
        ],
        "prompt_template": "Create a detailed blog post outline for: \"{keyword}\"\nTarget word count: {word_count} words",
        "save_dir": "outlines",
        "save_prefix": "outline",
    },
    "seo-check": {
        "label": "SEO Check",
        "icon": "✅",
        "skill_dir": "blog-seo-check",
        "description": "Post-writing SEO validation: title, meta, headings, keyword usage, schema, internal linking.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post to validate…", "rows": 10},
            {"name": "target_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. SEO blog writing"},
        ],
        "prompt_template": "Run an SEO check on this blog post targeting \"{target_keyword}\":\n\n---\n{content}",
        "save_dir": None,
        "save_prefix": None,
    },
    "repurpose": {
        "label": "Repurpose",
        "icon": "♻️",
        "skill_dir": "blog-repurpose",
        "description": "Transform a blog post into Twitter thread, LinkedIn post, YouTube script, Reddit post, and email newsletter.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post to repurpose…", "rows": 10},
            {"name": "platforms", "label": "Target Platforms", "type": "select",
             "options": [("all","All platforms"),("twitter","Twitter/X thread"),
                         ("linkedin","LinkedIn post"),("email","Email newsletter"),
                         ("youtube","YouTube script"),("reddit","Reddit post")]},
        ],
        "prompt_template": "Repurpose this blog post for: {platforms}\n\n---\n{content}",
        "save_dir": "repurposed",
        "save_prefix": "repurposed",
    },
    "geo": {
        "label": "GEO / AI Citations",
        "icon": "🤖",
        "skill_dir": "blog-geo",
        "description": "Audit and optimize a post for AI citation readiness (ChatGPT, Claude, Perplexity, Google AI Overviews).",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post to audit…", "rows": 10},
        ],
        "prompt_template": "Run a GEO/AEO audit on this blog post and provide specific optimization recommendations:\n\n---\n{content}",
        "save_dir": None,
        "save_prefix": None,
    },
    "schema": {
        "label": "Schema Markup",
        "icon": "🏷️",
        "skill_dir": "blog-schema",
        "description": "Generate JSON-LD schema markup: Article, FAQPage, HowTo, BreadcrumbList, and more.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post…", "rows": 8},
            {"name": "schema_types", "label": "Schema Types", "type": "select",
             "options": [("auto","Auto-detect (recommended)"),("article","Article"),
                         ("faq","FAQPage"),("howto","HowTo"),("all","All applicable")]},
        ],
        "prompt_template": "Generate JSON-LD schema markup ({schema_types}) for this blog post:\n\n---\n{content}",
        "save_dir": None,
        "save_prefix": None,
    },
    "factcheck": {
        "label": "Fact Check",
        "icon": "🔬",
        "skill_dir": "blog-factcheck",
        "description": "Identify and verify statistics, claims, and sourced data in a blog post.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post to fact-check…", "rows": 10},
        ],
        "prompt_template": "Fact-check all statistics, claims, and sourced data in this blog post. Flag anything unverifiable and suggest replacements:\n\n---\n{content}",
        "save_dir": None,
        "save_prefix": None,
    },
    "calendar": {
        "label": "Editorial Calendar",
        "icon": "📅",
        "skill_dir": "blog-calendar",
        "description": "Generate a 90-day editorial calendar with topic clusters, keywords, and publishing schedule.",
        "fields": [
            {"name": "niche", "label": "Blog Niche / Topic", "type": "text",
             "placeholder": "e.g. SaaS content marketing, personal finance, AI tools"},
            {"name": "frequency", "label": "Publishing Frequency", "type": "select",
             "options": [("weekly","Weekly (4 posts/month)"),("biweekly","Bi-weekly (2/month)"),
                         ("daily","Daily (Mon-Fri)")]},
            {"name": "goal", "label": "Primary Goal", "type": "select",
             "options": [("traffic","Organic traffic growth"),("authority","Topical authority"),
                         ("leads","Lead generation"),("brand","Brand awareness")]},
        ],
        "prompt_template": "Create a 90-day editorial calendar for a {niche} blog.\nPublishing frequency: {frequency}\nPrimary goal: {goal}",
        "save_dir": "keyword-research",
        "save_prefix": "calendar",
    },
    "decay": {
        "label": "Decay Detector",
        "icon": "📉",
        "skill_dir": "blog-decay",
        "description": "Identify stale statistics, outdated references, and content decay signals in a blog post.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the blog post to check for content decay…", "rows": 10},
        ],
        "prompt_template": "Analyze this blog post for content decay — stale statistics, outdated references, and decay risk. Score each section and recommend refreshes:\n\n---\n{content}",
        "save_dir": None,
        "save_prefix": None,
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")

def get_model() -> str:
    return os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

def load_skill_prompt(skill_dir: str) -> str:
    """Read SKILL.md, strip YAML frontmatter, return body as system prompt."""
    path = SKILLS_DIR / skill_dir / "SKILL.md"
    if not path.exists():
        return f"You are a blog content specialist helping with {skill_dir}."
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
    files = []
    for f in sorted(directory.glob("*.md"), reverse=True):
        files.append({
            "name": f.stem,
            "filename": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "path": str(f),
        })
    return files

def render_md_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"], output_format="html")

def save_result(content: str, directory: str, prefix: str) -> Path:
    save_path = ROOT / directory
    save_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filepath = save_path / f"{prefix}-{ts}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath

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
# Design system (CSS + JS)
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#0d1117;--surface:#161b22;--surface2:#21262d;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--yellow:#d29922;--red:#f85149;--purple:#bc8cff;--orange:#ffa657}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:14px;line-height:1.6;min-height:100vh}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:rgba(110,118,129,.15);padding:2px 5px;border-radius:4px;font-family:monospace;font-size:12px}

/* NAV */
nav{background:var(--surface);border-bottom:1px solid var(--border);padding:0 20px;display:flex;align-items:center;gap:0;height:50px;position:sticky;top:0;z-index:200;overflow-x:auto}
.nav-brand{font-weight:700;font-size:15px;color:var(--text);margin-right:24px;white-space:nowrap;display:flex;align-items:center;gap:6px;flex-shrink:0}
.nav-brand em{color:var(--accent);font-style:normal}
nav a{color:var(--muted);padding:0 12px;height:50px;display:flex;align-items:center;font-size:13px;border-bottom:2px solid transparent;white-space:nowrap;transition:color .15s,border-color .15s}
nav a:hover{color:var(--text);text-decoration:none}
nav a.active{color:var(--text);border-bottom-color:var(--accent)}
.nav-spacer{flex:1}
.api-pill{background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:4px 12px;font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px;flex-shrink:0}
.api-pill.ok{border-color:rgba(63,185,80,.4);color:var(--green)}
.api-pill.missing{border-color:rgba(248,81,73,.4);color:var(--red)}

/* LAYOUT */
.page{max-width:1080px;margin:0 auto;padding:28px 20px}
.page-wide{max-width:1280px;margin:0 auto;padding:28px 20px}

/* TYPOGRAPHY */
h1{font-size:21px;font-weight:700;margin-bottom:4px}
h2{font-size:15px;font-weight:600;margin-bottom:14px}
h3{font-size:13px;font-weight:600}
.subtitle{color:var(--muted);font-size:13px;margin-bottom:24px}
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}

/* CARDS */
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:18px}
.grid{display:grid;gap:14px;margin-bottom:24px}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:800px){.g2,.g3,.g4{grid-template-columns:1fr}}
@media(min-width:801px) and (max-width:1000px){.g4{grid-template-columns:repeat(2,1fr)}}

/* STAT CARDS */
.stat-num{font-size:30px;font-weight:700;color:var(--accent);display:block;line-height:1.1}
.stat-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}

/* SKILL GRID */
.skill-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:8px;transition:border-color .15s,transform .1s;cursor:pointer;text-decoration:none;color:var(--text)}
.skill-card:hover{border-color:var(--accent);transform:translateY(-1px);text-decoration:none;color:var(--text)}
.skill-icon{font-size:22px}
.skill-name{font-weight:600;font-size:13px}
.skill-desc{font-size:12px;color:var(--muted);line-height:1.4}

/* FORMS */
.form-group{margin-bottom:14px}
label{display:block;font-size:11px;font-weight:600;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px}
input[type=text],select,textarea{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px 11px;font-size:13px;font-family:inherit;outline:none;transition:border-color .15s}
input[type=text]:focus,select:focus,textarea:focus{border-color:var(--accent)}
select option{background:var(--surface)}
textarea{resize:vertical;min-height:120px;font-family:monospace;font-size:12px}

/* BUTTONS */
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer;border:1px solid transparent;transition:all .15s;text-decoration:none;white-space:nowrap}
.btn:hover{text-decoration:none}
.btn-primary{background:var(--accent);color:#0d1117;border-color:var(--accent)}
.btn-primary:hover{background:#79c0ff;color:#0d1117}
.btn-secondary{background:transparent;color:var(--text);border-color:var(--border)}
.btn-secondary:hover{background:var(--border)}
.btn-ghost{background:transparent;color:var(--muted);border-color:transparent}
.btn-ghost:hover{color:var(--text);background:var(--surface2)}
.btn-sm{padding:5px 12px;font-size:12px}
.btn-danger{background:transparent;color:var(--red);border-color:rgba(248,81,73,.4)}
.btn-danger:hover{background:rgba(248,81,73,.1)}
.btn[disabled]{opacity:.5;cursor:not-allowed}

/* BADGES */
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
.badge-blue{background:rgba(88,166,255,.15);color:var(--accent)}
.badge-green{background:rgba(63,185,80,.15);color:var(--green)}
.badge-yellow{background:rgba(210,153,34,.15);color:var(--yellow)}
.badge-red{background:rgba(248,81,73,.15);color:var(--red)}
.badge-purple{background:rgba(188,140,255,.15);color:var(--purple)}

/* ALERTS */
.alert{border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px}
.alert-warn{background:rgba(210,153,34,.1);border:1px solid rgba(210,153,34,.3);color:var(--yellow)}
.alert-info{background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.3);color:var(--accent)}
.alert-success{background:rgba(63,185,80,.1);border:1px solid rgba(63,185,80,.3);color:var(--green)}
.alert-error{background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.3);color:var(--red)}

/* OUTPUT AREA */
.output-wrap{position:relative}
.output-toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-bottom:none;border-radius:8px 8px 0 0}
.output-toolbar .title{font-size:12px;color:var(--muted);flex:1}
.output-box{background:var(--bg);border:1px solid var(--border);border-radius:0 0 8px 8px;padding:20px;min-height:200px;max-height:70vh;overflow-y:auto;font-size:13px;line-height:1.7}
.output-box.empty{display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:13px;min-height:260px}
.output-box pre{white-space:pre-wrap;word-break:break-word}

/* STREAMING CURSOR */
.cursor{display:inline-block;width:8px;height:14px;background:var(--accent);margin-left:2px;animation:blink .8s step-end infinite;vertical-align:text-bottom}
@keyframes blink{50%{opacity:0}}

/* MARKDOWN RENDER */
.md h1{font-size:19px;margin:20px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px}
.md h2{font-size:16px;margin:18px 0 8px}
.md h3{font-size:14px;margin:14px 0 6px}
.md h4{font-size:13px;margin:12px 0 4px;color:var(--muted)}
.md p{margin-bottom:10px}
.md ul,.md ol{margin:6px 0 10px 22px}
.md li{margin-bottom:3px}
.md code{background:rgba(110,118,129,.15);padding:2px 5px;border-radius:4px;font-size:12px}
.md pre{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px;overflow-x:auto;margin:10px 0}
.md pre code{background:none;padding:0;font-size:12px}
.md table{border-collapse:collapse;width:100%;margin:10px 0;font-size:12px}
.md th{background:var(--surface2);border:1px solid var(--border);padding:7px 11px;text-align:left;font-weight:600}
.md td{border:1px solid var(--border);padding:7px 11px}
.md tr:nth-child(even) td{background:rgba(22,27,34,.4)}
.md blockquote{border-left:3px solid var(--border);padding-left:14px;color:var(--muted);margin:10px 0}
.md hr{border:none;border-top:1px solid var(--border);margin:20px 0}
.md strong{font-weight:600}
.md a{color:var(--accent)}

/* REPORT LIST */
.report-list{list-style:none}
.report-item{display:flex;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid var(--border);color:var(--text);transition:color .1s}
.report-item:hover{color:var(--accent);text-decoration:none}
.report-item:last-child{border-bottom:none}
.report-item .meta{color:var(--muted);font-size:11px;margin-left:auto;white-space:nowrap}

/* PROGRESS / SPINNER */
.spinner{width:14px;height:14px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .5s linear infinite;display:inline-block;flex-shrink:0}
@keyframes spin{to{transform:rotate(360deg)}}
#run-status{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px}

/* SCORE */
.score-big{font-size:52px;font-weight:700;line-height:1}
.score-bar-wrap{background:var(--border);border-radius:4px;height:5px;margin:5px 0 2px}
.score-bar{height:5px;border-radius:4px;transition:width .5s}
.score-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
.score-item{background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:12px 14px}
.score-item .sname{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.score-item .sval{font-size:20px;font-weight:700;margin:3px 0 1px}

/* SETTINGS */
.settings-row{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--border)}
.settings-row:last-child{border-bottom:none}
.settings-label{flex:1}
.settings-label strong{display:block;font-size:13px}
.settings-label span{font-size:12px;color:var(--muted)}
"""

JS = """
// ---- Streaming runner ----
async function runSkill(skillId) {
  const form = document.getElementById('skill-form');
  const output = document.getElementById('output');
  const statusEl = document.getElementById('run-status');
  const runBtn = document.getElementById('run-btn');
  const saveBtn = document.getElementById('save-btn');

  const data = {};
  new FormData(form).forEach((v, k) => data[k] = v);

  output.innerHTML = '';
  output.classList.remove('empty');
  runBtn.disabled = true;
  if (saveBtn) saveBtn.style.display = 'none';
  statusEl.innerHTML = '<div class="spinner"></div> Streaming response…';

  let fullText = '';
  const cursor = document.createElement('span');
  cursor.className = 'cursor';

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({skill: skillId, fields: data})
    });

    if (!resp.ok) {
      const err = await resp.json();
      statusEl.textContent = '✗ ' + (err.error || 'Error');
      output.textContent = err.error || 'Request failed';
      runBtn.disabled = false;
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    output.appendChild(cursor);

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, {stream: true});
      // Parse SSE lines
      chunk.split('\\n').forEach(line => {
        if (line.startsWith('data: ')) {
          const raw = line.slice(6);
          if (raw === '[DONE]') return;
          try {
            const d = JSON.parse(raw);
            if (d.text) {
              fullText += d.text;
              cursor.remove();
              output.innerHTML = renderMd(fullText);
              output.appendChild(cursor);
              output.scrollTop = output.scrollHeight;
            }
            if (d.error) {
              statusEl.textContent = '✗ ' + d.error;
              output.textContent = d.error;
            }
          } catch(e) {}
        }
      });
    }

    cursor.remove();
    statusEl.textContent = '✓ Done — ' + fullText.length + ' characters';
    runBtn.disabled = false;

    // Show save button if skill has save_dir
    if (saveBtn && fullText.trim()) {
      saveBtn.style.display = 'flex';
      saveBtn.onclick = () => saveResult(skillId, fullText);
    }

    // Store for copy
    window._lastOutput = fullText;

  } catch(e) {
    cursor.remove();
    statusEl.textContent = '✗ ' + e.message;
    runBtn.disabled = false;
  }
}

async function saveResult(skillId, content) {
  const resp = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({skill: skillId, content})
  });
  const d = await resp.json();
  if (d.path) {
    const btn = document.getElementById('save-btn');
    btn.textContent = '✓ Saved to ' + d.filename;
    btn.disabled = true;
  }
}

function copyOutput() {
  if (window._lastOutput) {
    navigator.clipboard.writeText(window._lastOutput)
      .then(() => {
        const btn = document.getElementById('copy-btn');
        if (btn) { btn.textContent = '✓ Copied'; setTimeout(() => btn.textContent = '⎘ Copy', 1500); }
      });
  }
}

// ---- Minimal markdown renderer (tables + code + headings + lists) ----
function renderMd(text) {
  // Escape HTML first (but preserve our output)
  // Use a simple but complete renderer
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Headings
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Horizontal rule
    .replace(/^---+$/gm, '<hr>')
    // Bold, italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // Tables
    .replace(/^\|(.+)\|$/gm, (match) => match);

  // Handle tables
  html = html.replace(/((\|.+\|\n?)+)/gm, (block) => {
    const rows = block.trim().split('\\n').filter(r => r.trim());
    if (rows.length < 2) return block;
    const isSep = r => /^\|[\s\-:|]+\|/.test(r);
    let thead = '', tbody = '';
    let inHead = true;
    rows.forEach((row, i) => {
      if (isSep(row)) { inHead = false; return; }
      const cells = row.split('|').filter((_, i, a) => i > 0 && i < a.length - 1);
      const tag = inHead ? 'th' : 'td';
      const tr = cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('');
      if (inHead) thead += `<tr>${tr}</tr>`;
      else tbody += `<tr>${tr}</tr>`;
    });
    return `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
  });

  // Code blocks
  html = html.replace(/```[\\w]*\\n([\\s\\S]+?)```/gm, (_, code) =>
    `<pre><code>${code.trim()}</code></pre>`);

  // Lists
  html = html.replace(/(^[-*] .+\\n?)+/gm, block => {
    const items = block.trim().split('\\n').map(l => `<li>${l.replace(/^[-*] /,'')}</li>`).join('');
    return `<ul>${items}</ul>`;
  });
  html = html.replace(/(^\\d+\\. .+\\n?)+/gm, block => {
    const items = block.trim().split('\\n').map(l => `<li>${l.replace(/^\\d+\\. /,'')}</li>`).join('');
    return `<ol>${items}</ol>`;
  });

  // Paragraphs (lines not already in block tags)
  html = html.replace(/^(?!<[a-z]).+$/gm, line => line.trim() ? `<p>${line}</p>` : '');

  return '<div class="md">' + html + '</div>';
}

// ---- Settings API key toggle ----
function toggleKey() {
  const inp = document.getElementById('api-key-input');
  if (inp) inp.type = inp.type === 'password' ? 'text' : 'password';
}
"""

# ---------------------------------------------------------------------------
# Base template
# ---------------------------------------------------------------------------

def render(body: str, title: str = "Claude Blog", active: str = "", **ctx):
    api_key = get_api_key()
    key_status = "ok" if api_key else "missing"
    key_label = f"API key ✓" if api_key else "No API key"
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
  <a href="/" class="{{'active' if active=='home' else ''}}">Home</a>
  <a href="/run/keyword-research" class="{{'active' if active=='keyword-research' else ''}}">Keywords</a>
  <a href="/run/write" class="{{'active' if active=='write' else ''}}">Write</a>
  <a href="/run/rewrite" class="{{'active' if active=='rewrite' else ''}}">Rewrite</a>
  <a href="/run/brief" class="{{'active' if active=='brief' else ''}}">Brief</a>
  <a href="/saved" class="{{'active' if active=='saved' else ''}}">Saved</a>
  <a href="/analyze" class="{{'active' if active=='analyze' else ''}}">Analyzer</a>
  <a href="/cluster-map" class="{{'active' if active=='cluster' else ''}}">Clusters</a>
  <div class="nav-spacer"></div>
  <a href="/settings" class="api-pill {key_status}" title="Settings">{key_label}</a>
</nav>
<div class="page">
{body}
</div>
<script>{JS}</script>
</body>
</html>""", **ctx)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    api_key = get_api_key()
    kw_count = len(list_saved(KEYWORD_DIR))
    perf_count = len(list_saved(PERFORMANCE_DIR))

    skill_cards = "".join(f"""
      <a class="skill-card" href="/run/{sid}">
        <div class="skill-icon">{s['icon']}</div>
        <div class="skill-name">{s['label']}</div>
        <div class="skill-desc">{s['description']}</div>
      </a>""" for sid, s in SKILLS.items())

    warn = ""
    if not api_key:
        warn = """<div class="alert alert-warn">
          <strong>API key not set.</strong>
          Add your <code>ANTHROPIC_API_KEY</code> to a <code>.env</code> file in the project root,
          or <a href="/settings">configure it here</a>.
        </div>"""

    body = f"""
<h1>Claude Blog</h1>
<p class="subtitle">Local AI blog suite — v1.9.0 · {len(SKILLS)} skills · runs on {get_model()}</p>

{warn}

<div class="grid g4" style="margin-bottom:24px">
  <div class="card"><span class="stat-num">{len(SKILLS)}</span><div class="stat-label">Skills available</div></div>
  <div class="card"><span class="stat-num">15</span><div class="stat-label">Agents</div></div>
  <div class="card"><span class="stat-num">{kw_count}</span><div class="stat-label">Keyword reports</div></div>
  <div class="card"><span class="stat-num">{perf_count}</span><div class="stat-label">Performance reports</div></div>
</div>

<div class="section-header"><h2>Skills</h2></div>
<div class="grid g4" style="margin-bottom:28px">
{skill_cards}
</div>

<div class="grid g2">
  <div class="card">
    <h2>Quick Start</h2>
    <ol style="margin-left:18px;font-size:13px;line-height:2">
      <li>Set your <code>ANTHROPIC_API_KEY</code> in <code>.env</code></li>
      <li>Pick a skill above (e.g. <a href="/run/keyword-research">Keyword Research</a>)</li>
      <li>Fill the form and click Run</li>
      <li>Results stream live in the browser</li>
      <li>Save to <a href="/saved">Saved Files</a> with one click</li>
    </ol>
  </div>
  <div class="card">
    <h2>Local Tools (no API key needed)</h2>
    <div style="display:flex;flex-direction:column;gap:8px">
      <a href="/analyze" class="btn btn-secondary">📊 Blog Post Analyzer — 100-point scoring</a>
      <a href="/cluster-map" class="btn btn-secondary">🌐 Cluster Map Visualizer</a>
      <a href="/saved" class="btn btn-secondary">📁 Saved Files Browser</a>
    </div>
  </div>
</div>
"""
    return render(body, title="Dashboard", active="home")


# ---------------------------------------------------------------------------
# Skill runner (GET = form, POST handled via JS → /api/run)
# ---------------------------------------------------------------------------

@app.route("/run/<skill_id>")
def run_skill(skill_id: str):
    if skill_id not in SKILLS:
        return redirect(url_for("home"))

    s = SKILLS[skill_id]
    api_key = get_api_key()

    fields_html = ""
    for f in s["fields"]:
        required = f.get("required", True)
        req_mark = "" if not required else ""
        if f["type"] == "text":
            default = f.get("default", "")
            fields_html += f"""
<div class="form-group">
  <label>{f['label']}</label>
  <input type="text" name="{f['name']}" placeholder="{f.get('placeholder','')}" value="{default}" {'required' if required else ''}>
</div>"""
        elif f["type"] == "select":
            opts = "".join(f'<option value="{v}">{l}</option>' for v, l in f["options"])
            fields_html += f"""
<div class="form-group">
  <label>{f['label']}</label>
  <select name="{f['name']}">{opts}</select>
</div>"""
        elif f["type"] == "textarea":
            rows = f.get("rows", 8)
            fields_html += f"""
<div class="form-group">
  <label>{f['label']}</label>
  <textarea name="{f['name']}" rows="{rows}" placeholder="{f.get('placeholder','')}" {'required' if required else ''}></textarea>
</div>"""

    warn = ""
    if not api_key:
        warn = """<div class="alert alert-warn">
          API key not configured. <a href="/settings">Add your key</a> to run this skill.
        </div>"""

    # Other skills quick-nav
    other_skills = "".join(
        f'<a href="/run/{sid}" class="btn btn-ghost btn-sm">{sv["icon"]} {sv["label"]}</a>'
        for sid, sv in SKILLS.items() if sid != skill_id
    )

    body = f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
  <a href="/" class="btn btn-ghost btn-sm">← Home</a>
  <h1>{s['icon']} {s['label']}</h1>
</div>
<p class="subtitle">{s['description']}</p>

{warn}

<div style="display:grid;grid-template-columns:380px 1fr;gap:20px;align-items:start">

<div>
  <div class="card">
    <form id="skill-form" onsubmit="event.preventDefault();runSkill('{skill_id}')">
      {fields_html}
      <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
        <button type="submit" class="btn btn-primary" id="run-btn" {'disabled' if not api_key else ''}>
          ⚡ Run
        </button>
        <div id="run-status" style="font-size:12px;color:var(--muted)"></div>
      </div>
    </form>
  </div>

  <div style="margin-top:14px;font-size:12px;color:var(--muted)">
    Model: <code>{get_model()}</code>
  </div>

  <div style="margin-top:16px;display:flex;flex-wrap:wrap;gap:6px">
    {other_skills}
  </div>
</div>

<div>
  <div class="output-wrap">
    <div class="output-toolbar">
      <span class="title">Output</span>
      <button class="btn btn-ghost btn-sm" id="copy-btn" onclick="copyOutput()" style="font-size:12px">⎘ Copy</button>
      <button class="btn btn-secondary btn-sm" id="save-btn" style="display:none;font-size:12px">💾 Save</button>
    </div>
    <div class="output-box empty" id="output">
      <span>Fill the form and click Run to stream output</span>
    </div>
  </div>
</div>

</div>
"""
    return render(body, title=s["label"], active=skill_id)


# ---------------------------------------------------------------------------
# Streaming API endpoint
# ---------------------------------------------------------------------------

@app.route("/api/run", methods=["POST"])
def api_run():
    api_key = get_api_key()
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set. Configure it in .env or /settings."}), 401

    data = request.get_json()
    skill_id = data.get("skill", "")
    fields = data.get("fields", {})

    if skill_id not in SKILLS:
        return jsonify({"error": f"Unknown skill: {skill_id}"}), 400

    s = SKILLS[skill_id]
    system_prompt = load_skill_prompt(s["skill_dir"])

    # Build user message from template
    try:
        user_message = s["prompt_template"].format(**{k: v or "" for k, v in fields.items()})
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    def generate():
        try:
            import anthropic as sdk
            client = sdk.Anthropic(api_key=api_key)
            with client.messages.stream(
                model=get_model(),
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as ex:
            yield f"data: {json.dumps({'error': str(ex)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ---------------------------------------------------------------------------
# Save endpoint
# ---------------------------------------------------------------------------

@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json()
    skill_id = data.get("skill", "")
    content = data.get("content", "")

    if skill_id not in SKILLS:
        return jsonify({"error": "Unknown skill"}), 400

    s = SKILLS[skill_id]
    if not s.get("save_dir"):
        return jsonify({"error": "This skill has no save directory"}), 400

    filepath = save_result(content, s["save_dir"], s["save_prefix"])
    return jsonify({"path": str(filepath), "filename": filepath.name})


# ---------------------------------------------------------------------------
# Blog Analyzer (local — no API key)
# ---------------------------------------------------------------------------

@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    score_data = None
    error = ""
    post_content = ""

    if request.method == "POST":
        post_content = request.form.get("content", "").strip()
        filepath = request.form.get("filepath", "").strip()
        script = ROOT / "scripts" / "analyze_blog.py"

        if not script.exists():
            error = "scripts/analyze_blog.py not found."
        elif not post_content and not filepath:
            error = "Paste content or enter a file path."
        else:
            tmp_path = None
            try:
                if post_content:
                    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as tf:
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
                    out = result.stdout.strip()
                    start = out.find("{")
                    if start != -1:
                        score_data = json.loads(out[start:])
                    else:
                        error = "Could not parse analyzer output."
            except json.JSONDecodeError as e:
                error = f"JSON parse error: {e}"
            except subprocess.TimeoutExpired:
                error = "Timed out (30s)."
            except Exception as ex:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                error = str(ex)

    score_html = ""
    if score_data:
        score = score_data.get("score", score_data.get("total", 0))
        band = score_data.get("band", "")
        color = score_color(score)
        cats = score_data.get("categories", score_data.get("breakdown", {}))
        cat_html = "".join(f"""
          <div class="score-item">
            <div class="sname">{k.replace('_',' ')}</div>
            <div class="sval" style="color:{score_color(v)}">{v}</div>
            <div class="score-bar-wrap"><div class="score-bar" style="width:{min(v,100)}%;background:{score_color(v)}"></div></div>
          </div>""" for k, v in cats.items())

        issues = score_data.get("issues", score_data.get("recommendations", []))
        issues_html = "".join(f'<li style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px;color:var(--muted)">▸ {i}</li>'
                              for i in issues[:10]) if issues else ""

        score_html = f"""
<div class="card" style="margin-bottom:14px">
  <div style="display:flex;align-items:flex-end;gap:16px;margin-bottom:14px">
    <div>
      <div class="score-big" style="color:{color}">{score}</div>
      <div style="color:var(--muted);font-size:11px">/100</div>
    </div>
    <div style="flex:1">
      <div style="font-size:15px;font-weight:600">{band}</div>
      <div class="score-bar-wrap">
        <div class="score-bar" style="width:{min(float(score),100)}%;background:{color}"></div>
      </div>
    </div>
  </div>
  <div class="score-grid">{cat_html}</div>
</div>
{'<div class="card"><h3 style="margin-bottom:10px">Recommendations</h3><ul style="list-style:none">'+issues_html+'</ul></div>' if issues_html else ''}
"""

    body = f"""
<h1>📊 Blog Post Analyzer</h1>
<p class="subtitle">5-category, 100-point scoring — runs locally, no API key needed</p>

<div style="display:grid;grid-template-columns:400px 1fr;gap:20px;align-items:start">
<div class="card">
  {'<div class="alert alert-error">'+error+'</div>' if error else ''}
  <form method="POST">
    <div class="form-group">
      <label>Paste Blog Post (Markdown)</label>
      <textarea name="content" rows="12" placeholder="# My Post Title&#10;&#10;Content here…">{post_content}</textarea>
    </div>
    <div class="form-group">
      <label>— or — File Path</label>
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
    dirs = {
        "Keyword Research": KEYWORD_DIR,
        "Performance Reports": PERFORMANCE_DIR,
        "Repurposed Content": REPURPOSED_DIR,
        "Personas": PERSONAS_DIR,
    }
    # Also check any skill save dirs
    for sid, s in SKILLS.items():
        sd = s.get("save_dir")
        if sd and sd not in ("keyword-research", "performance", "repurposed", "personas"):
            label = s["label"] + " Output"
            dirs[label] = ROOT / sd

    sections = ""
    for label, path in dirs.items():
        files = list_saved(path)
        if not files:
            continue
        items = "".join(f"""
          <li>
            <a class="report-item" href="/saved/view?path={f['path']}">
              <span>📄</span>
              <div><div>{f['name']}</div><div style="font-size:11px;color:var(--muted)">{f['filename']}</div></div>
              <span class="meta">{f['size_kb']} KB</span>
            </a>
          </li>""" for f in files)
        sections += f"""
<div class="card" style="margin-bottom:14px">
  <div class="section-header"><h2>{label}</h2><span class="badge badge-blue">{len(files)}</span></div>
  <ul class="report-list">{items}</ul>
</div>"""

    if not sections:
        sections = '<div class="alert alert-info">No saved files yet. Run a skill and click Save.</div>'

    body = f"<h1>📁 Saved Files</h1><p class='subtitle'>All files generated by Claude Blog skills</p>{sections}"
    return render(body, title="Saved Files", active="saved")


@app.route("/saved/view")
def saved_view():
    path_str = request.args.get("path", "")
    path = Path(path_str)
    if not path.exists() or not path.suffix == ".md":
        return redirect(url_for("saved"))
    content_html = render_md_file(path)
    body = f"""
<a href="/saved" class="btn btn-ghost btn-sm">← Saved Files</a>
<h1 style="margin-top:10px">{path.stem}</h1>
<p class="subtitle">{path}</p>
<div class="card md" style="margin-top:14px">{content_html}</div>
"""
    return render(body, title=path.stem, active="saved")


# ---------------------------------------------------------------------------
# Cluster Map
# ---------------------------------------------------------------------------

@app.route("/cluster-map")
def cluster_map():
    body = """
<div class="section-header">
  <div>
    <h1>🌐 Cluster Map</h1>
    <p class="subtitle">Interactive force-directed topic cluster visualization</p>
  </div>
  <a href="/cluster-map/full" target="_blank" class="btn btn-secondary btn-sm">⛶ Fullscreen</a>
</div>
<div style="border-radius:8px;overflow:hidden;border:1px solid var(--border);height:580px">
  <iframe src="/cluster-map/full" style="width:100%;height:100%;border:none"></iframe>
</div>
<div class="alert alert-info" style="margin-top:14px">
  Populate with real data: run <strong>Keyword Research</strong> then
  <code>/blog cluster [topic]</code> in Claude Code to generate cluster data.
</div>
"""
    return render(body, title="Cluster Map", active="cluster")


@app.route("/cluster-map/full")
def cluster_map_full():
    if not CLUSTER_MAP.exists():
        return "Cluster map not found", 404
    return send_file(CLUSTER_MAP, mimetype="text/html")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved_msg = ""
    error_msg = ""

    if request.method == "POST":
        new_key = request.form.get("api_key", "").strip()
        new_model = request.form.get("model", DEFAULT_MODEL).strip()

        env_path = ROOT / ".env"
        try:
            lines = env_path.read_text().splitlines() if env_path.exists() else []
            new_lines = []
            found_key = found_model = False
            for line in lines:
                if line.startswith("ANTHROPIC_API_KEY="):
                    new_lines.append(f"ANTHROPIC_API_KEY={new_key}")
                    found_key = True
                elif line.startswith("CLAUDE_MODEL="):
                    new_lines.append(f"CLAUDE_MODEL={new_model}")
                    found_model = True
                else:
                    new_lines.append(line)
            if not found_key:
                new_lines.append(f"ANTHROPIC_API_KEY={new_key}")
            if not found_model:
                new_lines.append(f"CLAUDE_MODEL={new_model}")
            env_path.write_text("\n".join(new_lines) + "\n")

            # Reload into this process
            load_dotenv(env_path, override=True)
            os.environ["ANTHROPIC_API_KEY"] = new_key
            os.environ["CLAUDE_MODEL"] = new_model
            saved_msg = "Settings saved. Changes take effect immediately."
        except Exception as ex:
            error_msg = str(ex)

    current_key = os.environ.get("ANTHROPIC_API_KEY", "")
    current_model = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
    masked_key = (current_key[:8] + "…" + current_key[-4:]) if len(current_key) > 12 else ("set" if current_key else "")

    models = [
        ("claude-haiku-4-5-20251001", "Haiku 4.5 — fastest, cheapest"),
        ("claude-sonnet-4-6", "Sonnet 4.6 — balanced (recommended)"),
        ("claude-opus-4-7", "Opus 4.7 — most capable, slowest"),
    ]
    model_opts = "".join(f'<option value="{v}" {"selected" if v==current_model else ""}>{l}</option>'
                         for v, l in models)

    env_status = "✓ .env file exists" if (ROOT / ".env").exists() else "✗ No .env file — create one from .env.example"

    body = f"""
<h1>⚙️ Settings</h1>
<p class="subtitle">Configure API key and model for the local runner</p>

{'<div class="alert alert-success">'+saved_msg+'</div>' if saved_msg else ''}
{'<div class="alert alert-error">'+error_msg+'</div>' if error_msg else ''}

<div class="card" style="max-width:560px">
  <form method="POST">
    <div class="form-group">
      <label>Anthropic API Key</label>
      <div style="display:flex;gap:8px">
        <input type="password" name="api_key" id="api-key-input"
          value="{current_key}"
          placeholder="sk-ant-api03-…" style="flex:1">
        <button type="button" class="btn btn-ghost btn-sm" onclick="toggleKey()">Show</button>
      </div>
      {'<div style="font-size:11px;color:var(--green);margin-top:4px">Currently set: '+masked_key+'</div>' if current_key else '<div style="font-size:11px;color:var(--red);margin-top:4px">Not set — get your key at console.anthropic.com</div>'}
    </div>

    <div class="form-group">
      <label>Model</label>
      <select name="model">{model_opts}</select>
    </div>

    <button type="submit" class="btn btn-primary">Save Settings</button>
  </form>
</div>

<div class="card" style="max-width:560px;margin-top:14px">
  <h2>Environment</h2>
  <div class="settings-row">
    <div class="settings-label">
      <strong>.env file</strong>
      <span>Project root — loaded on startup</span>
    </div>
    <code style="font-size:11px;color:var(--muted)">{env_status}</code>
  </div>
  <div class="settings-row">
    <div class="settings-label">
      <strong>Python</strong>
      <span>Required 3.11+</span>
    </div>
    <code style="font-size:11px;color:var(--muted)">{sys.version.split()[0]}</code>
  </div>
  <div class="settings-row">
    <div class="settings-label">
      <strong>Project root</strong>
    </div>
    <code style="font-size:11px;color:var(--muted)">{ROOT}</code>
  </div>
</div>

<div class="card" style="max-width:560px;margin-top:14px">
  <h2>Manual Setup (.env file)</h2>
  <pre style="font-size:12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px">ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
PORT=5000</pre>
  <p style="font-size:12px;color:var(--muted);margin-top:8px">
    Save as <code>.env</code> in the project root, then restart the app.
    Get your key at <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>
  </p>
</div>
"""
    return render(body, title="Settings", active="settings")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Claude Blog Local Runner")
    print(f"  → http://localhost:{port}")
    api_key = get_api_key()
    if api_key:
        print(f"  → API key: {api_key[:8]}…")
    else:
        print(f"  → ⚠ No API key — add ANTHROPIC_API_KEY to .env")
    print(f"  → Model: {get_model()}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
