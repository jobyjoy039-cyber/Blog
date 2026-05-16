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
    "humanize": {
        "label": "Content Humanizer",
        "icon": "🧬",
        "skill_dir": "blog-humanize",
        "description": "Rewrite AI-generated content to pass GPTZero, Originality.ai, Copyleaks & Turnitin. Adds burstiness, removes AI vocabulary, and injects authentic voice.",
        "fields": [
            {"name": "content",   "label": "AI-Generated Content", "type": "textarea",
             "placeholder": "Paste the AI-generated text to humanize…", "rows": 12},
            {"name": "intensity", "label": "Intensity", "type": "select",
             "options": [("moderate","Moderate — restructure sentences, replace vocab, add voice (recommended)"),
                         ("light","Light — vocabulary swap + sentence variation only"),
                         ("heavy","Heavy — full rewrite, strong authorial voice")]},
            {"name": "notes", "label": "Extra Instructions (optional)", "type": "textarea",
             "placeholder": "Keep the formal tone, preserve all statistics, write in first person…",
             "required": False, "rows": 2},
        ],
        "prompt": "Humanize this content at intensity level: {intensity}.\nExtra instructions: {notes}\n\n---\n{content}",
        "save_dir": "posts", "save_prefix": "humanized",
        "web_tools": False,
    },
    "seo-optimize": {
        "label": "SEO Optimizer",
        "icon": "⚡",
        "skill_dir": "blog-seo-optimize",
        "description": "Integrate keywords, generate optimized title/meta, add CTAs, suggest links, score readability.",
        "fields": [
            {"name": "draft",           "label": "Blog Draft", "type": "textarea",
             "placeholder": "Paste the draft to optimize…", "rows": 10},
            {"name": "primary_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. content marketing strategy"},
            {"name": "keywords",        "label": "All Target Keywords", "type": "textarea",
             "placeholder": "e.g. content marketing, blog strategy, SEO writing…", "rows": 3},
        ],
        "prompt": "SEO-optimize this draft.\n\nPrimary Keyword: {primary_keyword}\nAll Keywords: {keywords}\n\n---\n{draft}",
        "save_dir": "posts", "save_prefix": "seo-opt",
        "web_tools": False,
    },
    "citations-audit": {
        "label": "Citations & AI Audit",
        "icon": "🔐",
        "skill_dir": "blog-citations-audit",
        "description": "Check attribution, detect AI patterns (em-dashes, vague sources, rule of three), score authenticity.",
        "fields": [
            {"name": "content", "label": "Blog Post (Markdown)", "type": "textarea",
             "placeholder": "Paste the post to audit…", "rows": 12},
        ],
        "prompt": "Run a citations and AI detection audit:\n\n---\n{content}",
        "save_dir": None, "save_prefix": None,
        "web_tools": False,
    },
    "ai-proof": {
        "label": "AI-Proof Writer",
        "icon": "🛡️",
        "skill_dir": "blog-ai-proof",
        "description": "Generate blog posts from scratch that pass every AI detector — GPTZero, Originality.ai, Copyleaks, Turnitin — using built-in burstiness, authentic voice, and zero AI vocabulary.",
        "fields": [
            {"name": "keyword",    "label": "Target Keyword / Topic", "type": "text",
             "placeholder": "e.g. how to build backlinks without cold outreach"},
            {"name": "word_count", "label": "Word Count", "type": "select",
             "options": [("1500","1,500 words"),("2500","2,500 words"),
                         ("3500","3,500 words"),("5000","5,000+ (pillar)")]},
            {"name": "tone", "label": "Tone", "type": "select",
             "options": [("conversational","Conversational — opinionated, direct, uses 'I'"),
                         ("authoritative","Authoritative — expert-led, data-backed, formal-ish"),
                         ("beginner-friendly","Beginner-friendly — plain English, lots of examples")]},
            {"name": "persona", "label": "Author Persona (optional)", "type": "text",
             "placeholder": "e.g. 10-year SEO consultant, startup founder, freelance writer",
             "required": False},
            {"name": "notes", "label": "Extra Instructions (optional)", "type": "textarea",
             "placeholder": "Include a comparison table, add a case study section, target US audience…",
             "required": False, "rows": 2},
        ],
        "prompt": "Write an AI-detection-proof blog post for: \"{keyword}\"\nWord count: {word_count}\nTone: {tone}\nAuthor persona: {persona}\nExtra instructions: {notes}",
        "save_dir": "posts", "save_prefix": "ai-proof",
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
  const btn = document.getElementById('copy-btn');
  const origLabel = btn ? btn.textContent : '⎘ Copy';
  function showOk() {
    if (btn) { btn.textContent = '✓ Copied'; setTimeout(() => btn.textContent = origLabel, 1600); }
  }
  function fallback() {
    const el = document.createElement('textarea');
    el.value = window._lastOutput;
    el.style.cssText = 'position:fixed;opacity:0;top:0;left:0;width:1px;height:1px';
    document.body.appendChild(el);
    el.focus(); el.select();
    try { document.execCommand('copy'); showOk(); } catch(e) {}
    document.body.removeChild(el);
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(window._lastOutput).then(showOk).catch(fallback);
  } else {
    fallback();
  }
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
  <a href="/run/humanize" class="nav-link {'active' if active=='humanize' else ''}">Humanize</a>
  <a href="/run/ai-proof" class="nav-link {'active' if active=='ai-proof' else ''}">AI-Proof</a>
  <a href="/pipeline" class="nav-link {'active' if active=='pipeline' else ''}" style="color:var(--accent);font-weight:600">⚡ Pipeline</a>
  <a href="/authority" class="nav-link {'active' if active=='authority' else ''}" style="color:#d29922;font-weight:600">🏆 Authority</a>
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
  <div class="card"><span class="stat-num">32</span><div class="stat-label">Agents</div></div>
  <div class="card"><span class="stat-num">{kw_count}</span><div class="stat-label">Keyword reports</div></div>
  <div class="card"><span class="stat-num">{perf_count}</span><div class="stat-label">Performance reports</div></div>
</div>

<div class="sec-header"><h2>Skills</h2></div>
<div class="grid g4" style="margin-bottom:26px">{skill_cards}</div>

<div class="grid g2" style="margin-bottom:22px">
  <a href="/pipeline" style="text-decoration:none">
    <div class="card" style="border:1px solid var(--accent);cursor:pointer">
      <h2 style="color:var(--accent)">⚡ 13-Agent Pipeline</h2>
      <p style="font-size:13px;color:var(--muted)">Sequential orchestration · 6 phases · keyword research through editorial calendar · quality gates + one-shot mode</p>
      <span class="btn btn-primary btn-sm" style="margin-top:8px">Launch Pipeline →</span>
    </div>
  </a>
  <a href="/authority" style="text-decoration:none">
    <div class="card" style="border:1px solid #d29922;cursor:pointer">
      <h2 style="color:#d29922">🏆 19-Agent Authority Pipeline</h2>
      <p style="font-size:13px;color:var(--muted)">5 phases · 10,000–15,000 word articles · deep research, master blueprint, quality polish, CMS assembly, launch plan</p>
      <span class="btn btn-sm" style="margin-top:8px;background:#d2992222;color:#d29922;border:1px solid #d2992255">Launch Authority →</span>
    </div>
  </a>
</div>

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
        allowed = "WebSearch,WebFetch" if use_web else ""
        cmd = [
            "claude", "-p", user_msg,
            "--system-prompt", system_prompt,
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

        # Strip API key vars so the CLI falls back to OAuth (subscription) auth
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_ID",
                                  "ANTHROPIC_BASE_URL")}

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(ROOT),
            env=clean_env,
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
# 13-Agent Orchestration Pipeline (6 phases)
# ---------------------------------------------------------------------------

PHASES = [
    {
        "phase": 1, "label": "Research & Planning", "icon": "📋",
        "steps": [1, 2], "color": "#58a6ff",
        "gate": "Keywords are relevant and achievable for your domain authority. Brief clearly answers 'why should this article exist?'",
        "fail_routes": {"Agent 1 (Keyword Research)": 1, "Agent 2 (Content Brief)": 2},
    },
    {
        "phase": 2, "label": "Content Creation", "icon": "📝",
        "steps": [3, 4, 5], "color": "#3fb950",
        "gate": "Outline tells a complete story. Draft reads like a knowledgeable human, not AI. SEO targets met.",
        "fail_routes": {"Agent 3 (Outline Optimizer)": 3, "Agent 4 (AI-Proof Writer)": 4, "Agent 5 (SEO Optimizer)": 5},
    },
    {
        "phase": 3, "label": "Validation & Refinement", "icon": "🔍",
        "steps": [6, 7], "color": "#d29922",
        "gate": "No false or unverifiable claims. All stats attributed. Passes AI detection tools.",
        "fail_routes": {"Agent 4 (AI-Proof Writer)": 4, "Agent 6 (Fact Check)": 6, "Agent 7 (Citations Audit)": 7},
    },
    {
        "phase": 4, "label": "Enhancement & Polish", "icon": "✨",
        "steps": [8, 9, 10], "color": "#bc8cff",
        "gate": "Reads naturally, passes AI detection. Best headline selected. Every sentence earns its place.",
        "fail_routes": {"Agent 4 (AI-Proof Writer)": 4, "Agent 8 (Humanizer)": 8, "Agent 9 (Headlines)": 9, "Agent 10 (Polish)": 10},
    },
    {
        "phase": 5, "label": "Final Validation", "icon": "🔐",
        "steps": [11, 12, 13], "color": "#f85149",
        "gate": "All critical SEO checks pass. Content evergreen or clearly dated with update plan. Promotion strategy ready.",
        "fail_routes": {"Agent 5 (SEO Optimizer)": 5, "Agent 11 (SEO Check)": 11, "Agent 9 (Headlines)": 9},
    },
]

PIPELINE_STEPS = [
    # ── Phase 1 ──────────────────────────────────────────────────────────────
    {
        "step": 1, "phase": 1, "id": "kw", "icon": "🔍", "agent": "Agent 1",
        "label": "Keyword Research",
        "description": "Identify 5–10 keywords, prioritize by volume/competition/intent, map to content sections.",
        "system_prompt": (
            "You are a Professional SEO Keyword Research Specialist.\n\n"
            "Output exactly these sections:\n\n"
            "## PRIMARY KEYWORDS\n"
            "| Keyword | Volume | Difficulty | Intent | Placement |\n"
            "|---------|--------|------------|--------|----------|\n"
            "(5–10 rows. Estimate volume. Difficulty: Easy/Medium/Hard. "
            "Intent: Informational/Navigational/Transactional/Commercial. "
            "Placement: Title/H2/Body/Meta)\n\n"
            "## LSI & RELATED KEYWORDS\n(3–5 semantic supporting terms)\n\n"
            "## COMPETITOR GAP ANALYSIS\n"
            "Content competitors have: ...\nContent MISSING from all competitors: ...\nContent opportunity: ...\n\n"
            "## KEYWORD PLACEMENT STRATEGY\n"
            "- Title: ...\n- H2s: ...\n- Meta Description: ...\n- Body: ...\n\n"
            "**Quality Gate check:** Are these keywords relevant, searchable, and achievable for the domain?"
        ),
        "fields": [
            {"name": "topic",    "label": "Blog Topic", "type": "text",
             "placeholder": "e.g. AI blog writing tools, content marketing for SaaS"},
            {"name": "audience", "label": "Target Audience", "type": "textarea", "rows": 2,
             "placeholder": "e.g. marketing managers, 3–5 years experience, pain point: can't rank"},
            {"name": "goal",     "label": "Blog Goal", "type": "select",
             "options": [("SEO ranking","SEO ranking"),("Lead generation","Lead generation"),
                         ("Brand awareness","Brand awareness"),("Engagement","Engagement")]},
            {"name": "keywords", "label": "Target Keywords (optional)", "type": "text",
             "placeholder": "Leave blank to discover from scratch, or list known keywords",
             "required": False},
            {"name": "content_type", "label": "Content Type", "type": "select",
             "options": [("guide","Guide / Pillar"),("how-to","How-To / Tutorial"),
                         ("listicle","Listicle"),("opinion","Opinion / POV"),
                         ("case-study","Case Study")]},
        ],
        "prompt": "Run keyword research.\n\nTopic: {topic}\nAudience: {audience}\nGoal: {goal}\nContent type: {content_type}\nTarget keywords (if known): {keywords}",
        "output_key": "kw_output",
        "saves": ["topic", "audience", "goal", "content_type"],
    },
    {
        "step": 2, "phase": 1, "id": "brief", "icon": "📋", "agent": "Agent 2",
        "label": "Content Brief",
        "description": "Article angle, competitor analysis, H1→H2→H3 outline, key messages, assets, tone guide.",
        "system_prompt": (
            "You are a Professional Content Strategist & Editorial Director.\n\n"
            "Create a comprehensive content brief with these sections:\n\n"
            "## CONTENT BRIEF: [TOPIC]\n\n"
            "### Article Angle\nUnique perspective, hook, reason this article should exist.\n\n"
            "### Competitor Analysis\n3–5 similar articles: what they do well, what questions they miss, the content gap to fill.\n\n"
            "### Content Outline\nH1 → H2 → H3 hierarchy with word counts per section "
            "and content type per section (explanation/data/example/story).\n\n"
            "### Key Messages\n3–5 main takeaways the reader should remember.\n\n"
            "### Reader Profile\n- Expertise level\n- What brought them here\n- Desired outcome\n\n"
            "### Required Assets\nData/stats (with sources), examples, case studies, tools/resources.\n\n"
            "### Tone & Style Guide\nSentence length, jargon level, personal stories yes/no, formatting.\n\n"
            "**Quality Gate check:** Does this brief clearly answer 'why should this article exist?'"
        ),
        "fields": [
            {"name": "topic",      "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "keywords",   "label": "Keywords (from Step 1)", "type": "textarea", "rows": 4,
             "placeholder": "Auto-filled from Step 1 output", "state_key": "kw_output"},
            {"name": "audience",   "label": "Target Audience", "type": "textarea", "rows": 2,
             "placeholder": "Auto-filled from Step 1", "state_key": "audience"},
            {"name": "tone",       "label": "Tone", "type": "select",
             "options": [("Professional","Professional"),("Conversational","Conversational"),
                         ("Expert","Expert"),("Accessible","Accessible")]},
            {"name": "word_count", "label": "Target Word Count", "type": "select",
             "options": [("1000","Short — ~1,000 words"),("1500","Medium — ~1,500 words"),
                         ("2000","Long — ~2,000 words"),("2500","Long-form — 2,500+")]},
        ],
        "prompt": "Create a content brief.\n\nTopic: {topic}\nKeywords: {keywords}\nAudience: {audience}\nTone: {tone}\nWord count: {word_count}",
        "output_key": "brief_output",
        "saves": ["word_count", "tone"],
    },

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    {
        "step": 3, "phase": 2, "id": "outline", "icon": "📐", "agent": "Agent 3",
        "label": "Outline Optimizer",
        "description": "Refine the brief's outline — add subheadings, word count targets, transition notes, and data placement markers.",
        "system_prompt": (
            "You are a Content Structure Specialist. Refine the given outline into a publication-ready structure.\n\n"
            "1. Add subheadings that answer real user questions (PAA-style: 'How does X work?', 'What is the difference between X and Y?')\n"
            "2. Assign word count targets per section (total must match brief's target)\n"
            "3. Add transition notes — one sentence showing how each section connects to the next\n"
            "4. Mark data/example placement — for each section note what type of data or example to insert\n"
            "5. Ensure narrative flow — problem → insight → solution → action\n\n"
            "Output:\n## ENHANCED OUTLINE: [Title]\n**Total target:** X words | **Sections:** N\n\n"
            "For each section:\n### H2: [Section Title] (~X words)\n"
            "**Purpose:** [what this accomplishes]\n"
            "- H3: [Subsection] (~X words) — [type]\n"
            "- Data needed: [description]\n"
            "- **Transition:** [one sentence to next section]\n\n"
            "End with:\n**Story arc:** [1-sentence summary of the narrative]\n\n"
            "**Quality Gate:** Does this outline tell a complete story? Could any section be cut without losing meaning?"
        ),
        "fields": [
            {"name": "brief",      "label": "Content Brief (from Step 2)", "type": "textarea", "rows": 8,
             "placeholder": "Auto-filled from Step 2 output", "state_key": "brief_output"},
            {"name": "keywords",   "label": "Keywords", "type": "textarea", "rows": 3,
             "placeholder": "Auto-filled from Step 1", "state_key": "kw_output"},
            {"name": "word_count", "label": "Target Word Count", "type": "text",
             "placeholder": "Auto-filled from Step 2", "state_key": "word_count"},
        ],
        "prompt": "Optimize this outline.\n\nTarget word count: {word_count}\nKeywords: {keywords}\n\nContent Brief:\n---\n{brief}",
        "output_key": "outline_output",
        "saves": [],
    },
    {
        "step": 4, "phase": 2, "id": "write", "icon": "✍️", "agent": "Agent 4",
        "label": "AI-Proof First Draft",
        "description": "Write an authentic first draft — varied sentences, contractions, storytelling, no AI tells.",
        "system_prompt": (
            "You are an Expert Freelance Content Writer with deep expertise in the topic.\n"
            "Write a first draft that reads as genuinely human — not an AI essay.\n\n"
            "1. AUTHENTICITY — use personal observations, stories, concrete examples. Write like explaining to a friend.\n"
            "2. NATURAL VOICE — vary sentence length dramatically. Short. Punchy. "
            "Then longer winding sentences that zigzag through a point before arriving. Use contractions.\n"
            "3. HOOK — start with a question or relatable statement. NEVER 'In this article we will explore…'\n"
            "4. PERSONALITY — show conviction. Have opinions. Don't hedge everything.\n"
            "5. BANNED WORDS — never use: delve, tapestry, testament, crucial, leverage, utilize, seamlessly, "
            "robust, comprehensive, Moreover, Furthermore, In conclusion.\n"
            "6. EVIDENCE — include data/statistics from the outline, cite examples concretely.\n"
            "7. STRUCTURE — follow the enhanced outline. Include Key Takeaways box near top. "
            "At least 3 real examples per major section. FAQ section at end.\n\n"
            "**Quality Gate:** Read your draft aloud. Does it sound like a knowledgeable person talking, or an AI generating text?"
        ),
        "fields": [
            {"name": "topic",      "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "outline",    "label": "Enhanced Outline (from Step 3)", "type": "textarea", "rows": 8,
             "placeholder": "Auto-filled from Step 3 output", "state_key": "outline_output",
             "fallback_key": "brief_output"},
            {"name": "expertise",  "label": "Author Expertise / POV", "type": "textarea", "rows": 2,
             "placeholder": "e.g. 8-year SEO consultant, ran 200+ content audits"},
            {"name": "word_count", "label": "Target Word Count", "type": "text",
             "placeholder": "Auto-filled from Step 2", "state_key": "word_count"},
            {"name": "tone",       "label": "Tone", "type": "text",
             "placeholder": "Auto-filled from Step 2", "state_key": "tone"},
        ],
        "prompt": "Write an authentic first draft.\n\nTopic: {topic}\nTone: {tone}\nTarget: {word_count} words\nAuthor expertise: {expertise}\n\nOutline:\n---\n{outline}",
        "output_key": "draft_v1",
        "saves": [],
    },
    {
        "step": 5, "phase": 2, "id": "seo-opt", "icon": "⚡", "agent": "Agent 5",
        "label": "SEO Optimizer",
        "description": "Keyword integration, title/meta, CTAs, internal/external links, readability.",
        "system_prompt": (
            "You are an Expert SEO Content Optimizer.\n\n"
            "1. TITLE — include primary keyword, under 60 chars, compelling\n"
            "2. META DESCRIPTION — 150–160 chars, primary keyword + benefit\n"
            "3. KEYWORD INTEGRATION — primary keyword in: first paragraph (1×), ≥2 H2s, body at 0.5–1.5% density. NATURAL only.\n"
            "4. INTRO — keyword + benefit statement in first 100 words\n"
            "5. STRUCTURE — short paragraphs (2–3 sentences), bullets for lists, bold key terms\n"
            "6. LINKS — suggest 3–5 internal links (anchor text + placement), 3–5 external authority links\n"
            "7. CTAs — 3 CTAs: after intro (soft), mid-content (value-driven), conclusion (main)\n"
            "8. READABILITY — Flesch 60+ target, active voice\n\n"
            "Output the full optimized draft, then:\n"
            "### SEO METRICS\n- Title: [title] (X chars)\n- Meta: [meta] (X chars)\n"
            "- Keyword density: X%\n- Readability: ~X Flesch\n- CTAs: X\n\n"
            "### LINK SUGGESTIONS\nInternal: ...\nExternal: ...\n\n"
            "**Quality Gate:** Is keyword density 0.5–1.5%? Does every CTA feel natural and useful?"
        ),
        "fields": [
            {"name": "draft",           "label": "First Draft (from Step 4)", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from Step 4 output", "state_key": "draft_v1"},
            {"name": "keywords",        "label": "All Target Keywords", "type": "textarea", "rows": 3,
             "placeholder": "Auto-filled from Step 1", "state_key": "kw_output"},
            {"name": "primary_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. content marketing strategy"},
        ],
        "prompt": "SEO-optimize this draft.\n\nPrimary Keyword: {primary_keyword}\nKeywords: {keywords}\n\n---\n{draft}",
        "output_key": "draft_seo",
        "saves": ["primary_keyword"],
    },

    # ── Phase 3 ──────────────────────────────────────────────────────────────
    {
        "step": 6, "phase": 3, "id": "factcheck", "icon": "🔬", "agent": "Agent 6",
        "label": "Fact Check",
        "description": "Verify every factual claim, flag unsupported stats, check logical consistency.",
        "system_prompt": (
            "You are a Professional Fact-Checker & Content Auditor.\n\n"
            "1. IDENTIFY ALL FACTUAL CLAIMS — list every statement that is factual (not opinion)\n"
            "2. VERIFY ACCURACY — check dates, names, numbers; flag anything uncertain\n"
            "3. CHECK SOURCES — do claims have citations? Are sources credible and current?\n"
            "4. FLAG UNSUPPORTED CLAIMS — no source = flag it; suggest rewording as opinion if unverifiable\n"
            "5. LOGICAL CONSISTENCY — do claims contradict each other? Cause-effect relationships sound?\n"
            "6. RED FLAGS — 'Everyone agrees…', 'Studies show…', outdated stats, conflicting figures\n\n"
            "Output:\n## FACT-CHECK REPORT\n\n"
            "### VERIFIED CLAIMS ✓\n- [Claim] — Source: [URL or publication]\n\n"
            "### FLAGGED CLAIMS ⚠️\n- [Claim] — Issue: [what's wrong] — Fix: [how to verify]\n\n"
            "### UNSUPPORTED CLAIMS ❌\n- [Claim] — Add [source] or reword as opinion\n\n"
            "### QUALITY ISSUES\n[Vague attributions, outdated info, logical gaps]\n\n"
            "### OVERALL ASSESSMENT + RECOMMENDATIONS\n\n"
            "**Quality Gate:** Are there any false or unverifiable claims? Is every stat attributed?"
        ),
        "fields": [
            {"name": "draft", "label": "Draft to Fact-Check", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_seo",
             "fallback_key": "draft_v1"},
            {"name": "topic", "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
        ],
        "prompt": "Fact-check this article on '{topic}':\n\n---\n{draft}",
        "output_key": "factcheck_output",
        "saves": [],
    },
    {
        "step": 7, "phase": 3, "id": "citations", "icon": "🔐", "agent": "Agent 7",
        "label": "GEO / AI Citations Audit",
        "description": "Verify attribution, check AI detector patterns, ensure source diversity and original analysis.",
        "system_prompt": (
            "You are an Expert Citations Auditor & AI Detection Specialist (GEO/AEO focus).\n\n"
            "1. CITATION AUDIT — all quotes attributed? all stats sourced? sources credible? citation format correct?\n"
            "2. AI DETECTION CHECK — scan for:\n"
            "   ✗ Excessive em-dashes (—)\n"
            "   ✗ Rule of three (exactly 3 items in every paragraph)\n"
            "   ✗ Vague attributions ('Research shows…', 'Studies indicate…', 'Experts say…')\n"
            "   ✗ Inflated symbolism / overwrought metaphors\n"
            "   ✗ Promotional language ('must understand', 'critical to know')\n"
            "   ✗ Repetitive transitions (Moreover, Furthermore used repeatedly)\n"
            "   ✗ Missing contractions — too formal\n"
            "   Rate AI risk: Low / Medium / High\n"
            "3. AUTHENTICITY — does original analysis/perspective come through? Real examples?\n"
            "4. SOURCE DIVERSITY — 5+ different publications, or relying on 1–2?\n"
            "5. AI CITATION READINESS (GEO) — would Perplexity, ChatGPT, or Claude cite this? "
            "Add citation capsules if missing: short, self-contained answer blocks.\n\n"
            "Output:\n## CITATIONS & AI AUDIT REPORT\n\n"
            "### CITATION CHECKLIST\n✓/✗ ...\n\n### CITATIONS NEEDED\n1. ...\n\n"
            "### AI DETECTION RISK: [LOW/MEDIUM/HIGH]\nFactors found:\n- ...\n\n"
            "### AUTHENTICITY SCORE: X/10\n\n"
            "### GEO CITATION READINESS\n\n### RECOMMENDATIONS\n\n"
            "**Quality Gate:** Does this pass GPTZero, Originality.ai, and similar detectors? Are citations diverse?"
        ),
        "fields": [
            {"name": "draft", "label": "Draft to Audit", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_seo",
             "fallback_key": "draft_v1"},
        ],
        "prompt": "Run a GEO/AI citations audit:\n\n---\n{draft}",
        "output_key": "citations_output",
        "saves": [],
    },

    # ── Phase 4 ──────────────────────────────────────────────────────────────
    {
        "step": 8, "phase": 4, "id": "humanize", "icon": "🧬", "agent": "Agent 8",
        "label": "Content Humanizer",
        "description": "Remove AI patterns, inject authentic voice, vary sentence structure, add contractions.",
        "system_prompt": (
            "You are a Content Humanization Specialist.\n\n"
            "REMOVE AI PATTERNS:\n"
            "1. Em-dashes (—) — replace with periods, commas, or restructure\n"
            "2. Rule of three — don't list exactly 3 things in every paragraph\n"
            "3. Vague attributions → specific ones: 'Research shows…' → 'A 2025 MIT study found…'\n"
            "4. Promotional words: remove 'must', 'critical', 'essential', 'crucial'\n"
            "5. Repetitive transitions — vary how you move between ideas\n"
            "6. ADD contractions: it's, don't, I'm, we're, you'll, can't\n\n"
            "ADD AUTHENTIC ELEMENTS:\n"
            "1. Personal examples: 'When I…', 'I've seen…', 'I remember…'\n"
            "2. Conversational asides in parentheses\n"
            "3. Questions to reader: 'Have you…?', 'What if…?'\n"
            "4. Sentence variety — short punchy sentences mixed with longer winding ones\n\n"
            "Output the full humanized text, then after --- separator:\n"
            "### CHANGES MADE:\n"
            "- Em-dashes removed: X\n- Contractions added: X\n"
            "- Vague attributions replaced: X\n- Personal examples added: X\n- Authenticity: X/10\n\n"
            "**Quality Gate:** Read a random paragraph aloud. Does it sound like a real person talking?"
        ),
        "fields": [
            {"name": "draft",     "label": "Draft to Humanize", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_seo",
             "fallback_key": "draft_v1"},
            {"name": "intensity", "label": "Intensity", "type": "select",
             "options": [("moderate","Moderate — restructure + vocab + voice (recommended)"),
                         ("light","Light — vocabulary swap + sentence variation only"),
                         ("heavy","Heavy — full rewrite, strong authorial voice")]},
        ],
        "prompt": "Humanize this content at intensity: {intensity}\n\n---\n{draft}",
        "output_key": "draft_humanized",
        "saves": [],
    },
    {
        "step": 9, "phase": 4, "id": "headlines", "icon": "🧪", "agent": "Agent 9",
        "label": "A/B Headlines",
        "description": "5 headline variants (curiosity, benefit, SEO, how-to, contrarian) with CTR scores.",
        "system_prompt": (
            "You are an Expert Headline Writer & CTR Specialist.\n\n"
            "Create 5 headline variations. For each, write: title (under 60 chars), "
            "meta description (150–160 chars), 2–3 sentences on why it works, "
            "CTR potential (Low/Medium/High), and best audience segment.\n\n"
            "Types:\n"
            "1. CURIOSITY/HOOK — 'Why [Expected thing] Is [Unexpected thing]'\n"
            "2. BENEFIT-DRIVEN — 'How to [Get Benefit] in [Timeframe]'\n"
            "3. SEO-OPTIMIZED — '[Keyword]: [Benefit]'\n"
            "4. HOW-TO — 'How to [Goal] in X Steps'\n"
            "5. CONTRARIAN — 'Why [Common Belief] Is Actually [Opposite]'\n\n"
            "Then:\n### RANKING & RECOMMENDATION\n[Rank highest to lowest CTR]\n"
            "**My Recommendation:** Option X because [reason]\n\n"
            "### A/B TESTING STRATEGY\nTest top 2 options for 14 days, measure CTR.\n\n"
            "**Quality Gate:** Does each headline trigger genuine curiosity or a click? Does it match search intent?"
        ),
        "fields": [
            {"name": "topic",    "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "article",  "label": "Article (for context)", "type": "textarea", "rows": 5,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_humanized",
             "fallback_key": "draft_seo"},
            {"name": "audience", "label": "Audience", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "audience"},
            {"name": "goal",     "label": "Goal", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "goal"},
        ],
        "prompt": "Create 5 A/B headline variants.\n\nTopic: {topic}\nAudience: {audience}\nGoal: {goal}\n\nArticle:\n---\n{article}",
        "output_key": "headlines_output",
        "saves": [],
    },
    {
        "step": 10, "phase": 4, "id": "polish", "icon": "✨", "agent": "Agent 10",
        "label": "Rewrite & Optimize",
        "description": "Final polish — stronger verbs, smooth transitions, pacing, tone consistency, select best headline.",
        "system_prompt": (
            "You are a Professional Editor & Content Optimizer.\n\n"
            "1. CLARITY & CONCISENESS — remove redundancy, say it once and say it well\n"
            "2. STRONG VERBS — no weak verbs. 'craft/build/create' not 'make'; 'guide/enable' not 'help'\n"
            "3. TRANSITIONS — smooth paragraph flow, remove abrupt jumps, logical progression\n"
            "4. PACING — alternate short/long paragraphs, max 5 sentences per paragraph\n"
            "5. TONE CONSISTENCY — no jarring formality shifts, consistent reader relationship\n"
            "6. READABILITY — Flesch 70+ target\n"
            "7. POWER WORDS — action verbs, specific language, vivid descriptions\n"
            "8. SELECT BEST HEADLINE — pick the highest-CTR headline option that matches the content\n\n"
            "Output:\n## POLISHED FINAL DRAFT\n\n"
            "### SELECTED HEADLINE\n**Headline:** ...\n**Meta Description:** ...\n**Why:** ...\n\n"
            "### FINAL ARTICLE\n[Complete polished text]\n\n"
            "### CHANGES MADE\n- Weak verbs: X improved\n- Passive voice: X converted\n"
            "- Readability: ~X Flesch\n- Word count: X\n\n"
            "**Quality Gate:** Does every sentence earn its place? Does every paragraph have purpose?"
        ),
        "fields": [
            {"name": "draft",     "label": "Draft to Polish", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_humanized",
             "fallback_key": "draft_seo"},
            {"name": "headlines", "label": "Headline Options (from Step 9)", "type": "textarea", "rows": 5,
             "placeholder": "Auto-filled from Step 9 output", "state_key": "headlines_output"},
        ],
        "prompt": "Polish to final publication quality.\n\nHeadlines:\n{headlines}\n\n---DRAFT---\n{draft}",
        "output_key": "final_draft",
        "saves": [],
    },

    # ── Phase 5 ──────────────────────────────────────────────────────────────
    {
        "step": 11, "phase": 5, "id": "seo-check", "icon": "✅", "agent": "Agent 11",
        "label": "SEO Check",
        "description": "Full technical SEO checklist: title, meta, headings, density, links, readability, CTAs.",
        "system_prompt": (
            "You are an SEO Technical Auditor. Run a complete SEO checklist. Mark each ✓ Pass or ⚠️ Fix.\n\n"
            "Check: title (50–60 chars, keyword present, compelling), meta (150–160 chars, keyword + benefit), "
            "H1 present with keyword, H2s descriptive (3–7 for 2,000-word post), H3s support H2s, "
            "keyword in first 100 words, density 0.5–1.5%, keyword in ≥2 H2s, synonyms used, "
            "Flesch 60+ (aim 70), short paragraphs, contractions present, active voice dominant, "
            "internal links 3–5, external links 2–3, descriptive anchor text, CTAs ≥1 and action-oriented, "
            "images have alt text.\n\n"
            "Output:\n## FINAL SEO SCORECARD\n"
            "| Item | Status | Action |\n|------|--------|--------|\n[row per item]\n\n"
            "## OVERALL STATUS: [✓ READY TO PUBLISH / ⚠️ FIX THESE ITEMS / ❌ NEEDS MAJOR REVISIONS]\n\n"
            "## PRIORITY FIXES\n1. [Issue] — Fix: [how]\n\n## SUGGESTED URL SLUG\n/[keyword]-[keyword]/\n\n"
            "**Quality Gate:** Do all critical SEO items pass? Is the content genuinely ready to index?"
        ),
        "fields": [
            {"name": "article",         "label": "Final Article", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from Step 10 output", "state_key": "final_draft",
             "fallback_key": "draft_humanized"},
            {"name": "primary_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "Auto-filled from Step 5", "state_key": "primary_keyword"},
            {"name": "headline",        "label": "Chosen Headline", "type": "text",
             "placeholder": "Paste the selected headline from Step 10"},
        ],
        "prompt": "Full SEO technical check.\n\nPrimary Keyword: {primary_keyword}\nHeadline: {headline}\n\n---\n{article}",
        "output_key": "seo_report",
        "saves": [],
    },
    {
        "step": 12, "phase": 5, "id": "decay", "icon": "📉", "agent": "Agent 12",
        "label": "Decay Detector",
        "description": "Flag time-sensitive claims, assess evergreen score, plan refresh timeline.",
        "system_prompt": (
            "You are a Content Decay & Freshness Analyst.\n\n"
            "1. TIME-SENSITIVE CLAIMS — statements tied to years/dates, 'current' trends, "
            "statistics with dates, product versions, 'latest' references\n"
            "2. OUTDATED-RISK SECTIONS — tools, market analysis, evolving best practices\n"
            "3. EVERGREEN SCORE — rate 1–10 (1=outdated in 3 months, 10=timeless). Explain what pulls it down.\n"
            "4. REFRESH TIMELINE — 30/60/90 days or 6/12 months?\n"
            "5. UPDATE-PRONE SECTIONS — which parts need updating first?\n"
            "6. REMEDIATION PLAN — how to stay fresh without major rewrites?\n\n"
            "Output:\n## CONTENT DECAY ANALYSIS\n\n### EVERGREEN SCORE: X/10\nWhy: ...\n\n"
            "### TIME-SENSITIVE CLAIMS\n1. [Claim] — Risk: H/M/L — Ages: [when] — Fix: [how]\n\n"
            "### OUTDATED-RISK SECTIONS\n- [Section] — Risk: [what could change]\n\n"
            "### REFRESH TIMELINE\n- First review: X days\n- Next audit: X days\n\n"
            "### MONITORING CHECKLIST\n- [Metric] — Check when: [condition]\n\n"
            "### REMEDIATION PLAN\n[Step-by-step]\n\n"
            "**Quality Gate:** Is content evergreen or clearly dated with an update plan?"
        ),
        "fields": [
            {"name": "article",      "label": "Final Article", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from Step 10 output", "state_key": "final_draft",
             "fallback_key": "draft_humanized"},
            {"name": "topic",        "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "current_date", "label": "Current Date", "type": "text",
             "placeholder": "2026-05-16"},
        ],
        "prompt": "Analyze content decay.\n\nTopic: {topic}\nCurrent date: {current_date}\n\n---\n{article}",
        "output_key": "decay_report",
        "saves": [],
    },
    {
        "step": 13, "phase": 5, "id": "editorial", "icon": "📅", "agent": "Agent 13",
        "label": "Editorial Calendar",
        "description": "Publication timing, 30-day promo schedule, refresh cycle, A/B test plan, follow-up content.",
        "system_prompt": (
            "You are an Editorial Calendar Strategist.\n\n"
            "1. PUBLICATION TIMING — optimal publish date/time based on topic, seasonality, and goal\n"
            "2. 30-DAY PROMOTION SCHEDULE — platform-specific posts for first 30 days\n"
            "3. SOCIAL MEDIA VARIANTS — draft 3 platform-native posts:\n"
            "   - Twitter/X thread (8–12 tweets)\n"
            "   - LinkedIn post (professional, 150–200 words)\n"
            "   - Reddit post (which subreddit + native-feeling opening)\n"
            "4. REFRESH CYCLE — 30/60/90-day and 12-month check-in plan\n"
            "5. A/B TEST PLAN — headline test, CTA test, intro length test\n"
            "6. FOLLOW-UP CONTENT — 3–5 related article ideas that create a topic cluster\n\n"
            "Output:\n## EDITORIAL CALENDAR ENTRY\n\n"
            "### PUBLICATION TIMING\n...\n\n"
            "### 30-DAY PROMOTION SCHEDULE\n"
            "| Day | Platform | Action |\n|-----|----------|--------|\n...\n\n"
            "### SOCIAL MEDIA VARIANTS\n[Twitter/X thread, LinkedIn, Reddit]\n\n"
            "### REFRESH CYCLE\n| Checkpoint | When | What to review |\n...\n\n"
            "### A/B TEST PLAN\n...\n\n"
            "### FOLLOW-UP CONTENT IDEAS\n1. ...\n2. ...\n3. ...\n\n"
            "**Quality Gate:** Is there a clear plan for promotion and long-term content freshness?"
        ),
        "fields": [
            {"name": "topic",    "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "headline", "label": "Final Headline", "type": "text",
             "placeholder": "Paste selected headline from Step 10"},
            {"name": "goal",     "label": "Blog Goal", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "goal"},
            {"name": "audience", "label": "Target Audience", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "audience"},
            {"name": "draft",    "label": "Final Article", "type": "textarea", "rows": 5,
             "placeholder": "Auto-filled from Step 10 output", "state_key": "final_draft",
             "fallback_key": "draft_humanized"},
        ],
        "prompt": "Create editorial calendar and promotion strategy.\n\nTopic: {topic}\nHeadline: {headline}\nGoal: {goal}\nAudience: {audience}\n\nArticle:\n---\n{draft}",
        "output_key": "calendar_output",
        "saves": [],
    },
]


def _build_pipeline_page():
    """Render the 13-agent, 6-phase orchestration pipeline page."""

    # ── Sidebar nav ──────────────────────────────────────────────────────────
    nav_items = ""
    prev_phase = 0
    for s in PIPELINE_STEPS:
        n = s["step"]
        ph = s["phase"]
        if ph != prev_phase:
            ph_data = PHASES[ph - 1]
            nav_items += (
                f'<div class="p-phase-header" style="border-left:3px solid {ph_data["color"]}">'
                f'{ph_data["icon"]} Phase {ph}: {ph_data["label"]}</div>'
            )
            prev_phase = ph
        nav_items += (
            f'<div class="p-nav-item" id="p-nav-{n}" data-step="{n}" onclick="showStep({n})">'
            f'<span class="p-nav-num" id="p-nav-num-{n}">{n}</span>'
            f'<div class="p-nav-info"><div class="p-nav-label">{s["icon"]} {s["label"]}</div>'
            f'<div class="p-nav-agent">{s["agent"]}</div></div>'
            f'<span class="p-nav-check" id="p-nav-check-{n}"></span></div>'
        )
    # Phase 6 nav entry
    nav_items += (
        '<div class="p-phase-header" style="border-left:3px solid #3fb950">📦 Phase 6: Final Assembly</div>'
        '<div class="p-nav-item" id="p-nav-14" data-step="14" onclick="showStep(14)">'
        '<span class="p-nav-num" id="p-nav-num-14">6</span>'
        '<div class="p-nav-info"><div class="p-nav-label">📦 Final Assembly</div>'
        '<div class="p-nav-agent">6 Deliverables</div></div>'
        '<span class="p-nav-check" id="p-nav-check-14"></span></div>'
    )

    # ── Phase quality gate panels ────────────────────────────────────────────
    def gate_panel(ph_data):
        ph = ph_data["phase"]
        routes = "".join(
            f'<option value="{step}">{label}</option>'
            for label, step in ph_data["fail_routes"].items()
        )
        return (
            f'<div class="phase-gate" id="gate-{ph}">'
            f'<div class="gate-icon">🔍</div>'
            f'<div class="gate-body">'
            f'<div class="gate-title">Phase {ph} Quality Gate</div>'
            f'<div class="gate-criteria">{ph_data["gate"]}</div>'
            f'<div class="gate-actions">'
            f'<button class="btn btn-primary btn-sm" onclick="passGate({ph})">✓ Pass — Next Phase</button>'
            f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
            f'<button class="btn btn-ghost btn-sm" style="color:var(--red)" '
            f'onclick="failGate({ph})">✗ Fail — Route back to:</button>'
            f'<select id="gate-route-{ph}" class="gate-select"><option value="">Select agent...</option>{routes}</select>'
            f'</div></div></div></div>'
        )

    # ── Step panels ──────────────────────────────────────────────────────────
    panels = ""
    last_phase = 0
    for s in PIPELINE_STEPS:
        n = s["step"]
        ph = s["phase"]
        ph_data = PHASES[ph - 1]
        next_s = PIPELINE_STEPS[n] if n < 13 else None
        next_label = f'Next: {next_s["label"]} →' if next_s else "Proceed to Phase 6 →"

        fhtml = ""
        for f in s["fields"]:
            sk  = f.get("state_key", "")
            fk  = f.get("fallback_key", "")
            da  = (f' data-state-key="{sk}"' if sk else "") + (f' data-fallback-key="{fk}"' if fk else "")
            badge = ' <span class="auto-badge">auto</span>' if sk else ""
            req = f.get("required", True)

            if f["type"] == "text":
                fhtml += (
                    f'<div class="form-group"><label class="field-label">{f["label"]}{badge}</label>'
                    f'<input type="text" name="{f["name"]}" placeholder="{f.get("placeholder","")}"'
                    f'{da}{" required" if req else ""}></div>'
                )
            elif f["type"] == "textarea":
                rows = f.get("rows", 5)
                fhtml += (
                    f'<div class="form-group"><label class="field-label">{f["label"]}{badge}</label>'
                    f'<textarea name="{f["name"]}" rows="{rows}" placeholder="{f.get("placeholder","")}"'
                    f'{da}{" required" if req else ""}></textarea></div>'
                )
            elif f["type"] == "select":
                opts = "".join(f'<option value="{v}">{l}</option>' for v, l in f["options"])
                fhtml += (
                    f'<div class="form-group"><label class="field-label">{f["label"]}</label>'
                    f'<select name="{f["name"]}">{opts}</select></div>'
                )

        # Phase header banner inside main area
        phase_banner = ""
        if ph != last_phase:
            phase_banner = (
                f'<div class="p-phase-banner" style="border-left:4px solid {ph_data["color"]}">'
                f'{ph_data["icon"]} <strong>Phase {ph}: {ph_data["label"]}</strong>'
                f'</div>'
            )
            last_phase = ph

        panels += f"""
{phase_banner}
<div class="p-step" id="p-step-{n}" data-step="{n}" data-output-key="{s['output_key']}">
  <div class="p-step-header">
    <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0">
      <span class="p-agent-badge" style="border-color:rgba(88,166,255,.4)">{s["agent"]}</span>
      <span style="font-size:18px">{s["icon"]}</span>
      <div>
        <div class="p-step-title">{s["label"]}</div>
        <div class="p-step-desc">{s["description"]}</div>
      </div>
    </div>
    <span id="p-status-{n}" class="p-run-status"></span>
  </div>
  <div class="p-step-body">
    <div class="p-form-col">
      <form id="p-form-{n}" onsubmit="event.preventDefault()">
        {fhtml}
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:6px">
          <button type="button" class="btn btn-primary" id="p-run-btn-{n}"
                  onclick="runPipelineStep({n})">⚡ Run {s["agent"]}</button>
          <span id="p-spin-{n}" style="display:none"><span class="spinner"></span></span>
        </div>
      </form>
    </div>
    <div class="p-output-col">
      <div class="output-toolbar">
        <span class="title" style="font-size:11px">{s["agent"]} · {s["label"]}</span>
        <button class="btn btn-ghost btn-sm" id="p-copy-{n}" style="display:none"
                onclick="copyStepOutput({n})">⎘ Copy</button>
        <button class="btn btn-ghost btn-sm" id="p-dl-{n}" style="display:none"
                onclick="dlStep({n},'{s["id"]}')">⬇ Save .md</button>
      </div>
      <div class="output-box empty" id="p-out-{n}">
        <span>Run {s["agent"]} to see output</span>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-primary btn-sm" id="p-next-{n}" style="display:none"
                onclick="nextStep({n})">{next_label}</button>
      </div>
    </div>
  </div>
</div>"""

        # Append gate panel at end of each phase
        if n == ph_data["steps"][-1]:
            panels += gate_panel(ph_data)

    # ── Phase 6: Final Assembly ──────────────────────────────────────────────
    panels += """
<div class="p-phase-banner" style="border-left:4px solid #3fb950">📦 <strong>Phase 6: Final Assembly & Quality Assurance</strong></div>
<div class="p-step" id="p-step-14" data-step="14" data-output-key="">
  <div class="p-step-header">
    <div style="display:flex;align-items:center;gap:10px">
      <span class="p-agent-badge" style="background:rgba(63,185,80,.15);border-color:rgba(63,185,80,.4);color:var(--green)">Phase 6</span>
      <span style="font-size:18px">📦</span>
      <div>
        <div class="p-step-title">Final Assembly & QA</div>
        <div class="p-step-desc">6 deliverables ready to publish. Download individually or all at once.</div>
      </div>
    </div>
  </div>

  <div style="margin-bottom:16px">
    <div class="grid g3" style="margin-bottom:12px">
      <div class="card" style="cursor:pointer" onclick="dlDeliverable(1)">
        <div style="font-size:20px;margin-bottom:4px">📄</div>
        <div style="font-weight:600;font-size:13px">Blog Post</div>
        <div style="font-size:11px;color:var(--muted)">Formatted, CMS-ready</div>
        <div id="qa-1" style="margin-top:8px"></div>
      </div>
      <div class="card" style="cursor:pointer" onclick="dlDeliverable(2)">
        <div style="font-size:20px;margin-bottom:4px">🏷️</div>
        <div style="font-weight:600;font-size:13px">SEO Metadata</div>
        <div style="font-size:11px;color:var(--muted)">Title, meta, keywords, slug</div>
        <div id="qa-2" style="margin-top:8px"></div>
      </div>
      <div class="card" style="cursor:pointer" onclick="dlDeliverable(3)">
        <div style="font-size:20px;margin-bottom:4px">📱</div>
        <div style="font-weight:600;font-size:13px">Social Media</div>
        <div style="font-size:11px;color:var(--muted)">3–5 platform variants</div>
        <div id="qa-3" style="margin-top:8px"></div>
      </div>
      <div class="card" style="cursor:pointer" onclick="dlDeliverable(4)">
        <div style="font-size:20px;margin-bottom:4px">🔗</div>
        <div style="font-weight:600;font-size:13px">Internal Link Map</div>
        <div style="font-size:11px;color:var(--muted)">From SEO optimizer</div>
        <div id="qa-4" style="margin-top:8px"></div>
      </div>
      <div class="card" style="cursor:pointer" onclick="dlDeliverable(5)">
        <div style="font-size:20px;margin-bottom:4px">📉</div>
        <div style="font-weight:600;font-size:13px">Decay Report</div>
        <div style="font-size:11px;color:var(--muted)">Freshness + refresh plan</div>
        <div id="qa-5" style="margin-top:8px"></div>
      </div>
      <div class="card" style="cursor:pointer" onclick="dlDeliverable(6)">
        <div style="font-size:20px;margin-bottom:4px">📝</div>
        <div style="font-weight:600;font-size:13px">Editorial Notes</div>
        <div style="font-size:11px;color:var(--muted)">Fact-check + citations summary</div>
        <div id="qa-6" style="margin-top:8px"></div>
      </div>
    </div>

    <div class="card" style="margin-bottom:14px">
      <h3 style="margin-bottom:10px">Final Quality Gates</h3>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px;font-size:12px" id="qa-gates">
        <div>☐ <strong>Accuracy:</strong> All facts verified</div>
        <div>☐ <strong>SEO:</strong> Technical requirements met</div>
        <div>☐ <strong>Authenticity:</strong> Passes AI detection</div>
        <div>☐ <strong>Readability:</strong> Logical flow, clear purpose</div>
        <div>☐ <strong>Engagement:</strong> Strong hook, examples, CTA</div>
        <div>☐ <strong>Freshness:</strong> Decay risks identified</div>
        <div>☐ <strong>Optimization:</strong> Best headline selected</div>
        <div>☐ <strong>Promotion:</strong> Editorial calendar ready</div>
      </div>
    </div>

    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-primary" onclick="downloadAll()">⬇ Download All 6 Deliverables</button>
      <button class="btn btn-secondary" onclick="checkAllGates()">✓ Run QA Checklist</button>
    </div>
  </div>
</div>"""

    # ── CSS ──────────────────────────────────────────────────────────────────
    css_pipeline = """
.pipeline-layout{display:grid;grid-template-columns:270px 1fr;height:calc(100vh - 50px);overflow:hidden}
.pipeline-sidebar{background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.pipeline-sidebar-header{padding:14px;border-bottom:1px solid var(--border)}
.p-nav{flex:1;overflow-y:auto;padding:6px 0}
.p-phase-header{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;padding:10px 14px 4px;margin-top:4px}
.p-nav-item{display:flex;align-items:center;gap:8px;padding:7px 14px;cursor:pointer;transition:background .12s;border-left:2px solid transparent}
.p-nav-item:hover{background:var(--surface2)}
.p-nav-item.active{background:rgba(88,166,255,.1);border-left-color:var(--accent)}
.p-nav-item.done{border-left-color:var(--green)}
.p-nav-num{width:20px;height:20px;border-radius:50%;background:var(--surface2);border:1px solid var(--border);font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--muted)}
.p-nav-item.active .p-nav-num{background:var(--accent);color:#0d1117;border-color:var(--accent)}
.p-nav-item.done .p-nav-num{background:var(--green);color:#0d1117;border-color:var(--green)}
.p-nav-info{flex:1;min-width:0}
.p-nav-label{font-size:11px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.p-nav-agent{font-size:10px;color:var(--muted)}
.p-nav-check{font-size:10px;color:var(--green);font-weight:700}
.pipeline-main{overflow-y:auto;background:var(--bg)}
.p-phase-banner{font-size:12px;padding:8px 20px;background:var(--surface);border-bottom:1px solid var(--border);color:var(--muted);display:none}
.p-phase-banner.visible{display:flex;align-items:center;gap:8px;position:sticky;top:0;z-index:10}
.p-step{display:none;padding:18px 20px;max-width:1100px}
.p-step.active{display:block}
.p-step-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.p-agent-badge{background:rgba(88,166,255,.12);color:var(--accent);border:1px solid rgba(88,166,255,.3);border-radius:12px;padding:2px 9px;font-size:11px;font-weight:700;flex-shrink:0}
.p-step-title{font-size:14px;font-weight:700}
.p-step-desc{font-size:11px;color:var(--muted);margin-top:2px}
.p-step-body{display:grid;grid-template-columns:320px 1fr;gap:14px;align-items:start}
.p-form-col{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px}
.p-output-col{display:flex;flex-direction:column}
.p-run-status{font-size:11px;color:var(--muted)}
.auto-badge{background:rgba(88,166,255,.12);color:var(--accent);border-radius:8px;padding:1px 5px;font-size:9px;font-weight:700;vertical-align:middle}
.pipeline-sidebar-footer{padding:10px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:6px}
.phase-gate{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px;margin:0 20px 14px;display:none}
.phase-gate.visible{display:flex;gap:12px;align-items:flex-start}
.gate-icon{font-size:20px;flex-shrink:0}
.gate-body{flex:1}
.gate-title{font-weight:700;font-size:13px;margin-bottom:4px}
.gate-criteria{font-size:12px;color:var(--muted);margin-bottom:10px}
.gate-actions{display:flex;flex-direction:column;gap:8px}
.gate-select{background:var(--bg);border:1px solid var(--border);border-radius:5px;color:var(--text);padding:4px 8px;font-size:12px}
.oneshot-card{margin:20px 20px 0;background:var(--surface);border:1px solid rgba(88,166,255,.4);border-radius:8px;padding:16px}
@media(max-width:900px){.pipeline-layout{grid-template-columns:1fr;height:auto}.p-step-body{grid-template-columns:1fr}}
"""

    # ── JavaScript ───────────────────────────────────────────────────────────
    js_pipeline = r"""
const PS_KEY='cblog_pipeline';
function psGet(){try{return JSON.parse(sessionStorage.getItem(PS_KEY)||'{}')}catch(e){return{}}}
function psSave(k,v){const s=psGet();s[k]=v;sessionStorage.setItem(PS_KEY,JSON.stringify(s));}
function psGetVal(k,fb){const s=psGet();return s[k]||(fb?s[fb]:'')||'';}

function showStep(n){
  document.querySelectorAll('.p-step').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.p-nav-item').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.p-phase-banner,.phase-gate').forEach(el=>el.classList.remove('visible'));
  const panel=document.getElementById('p-step-'+n);
  const nav=document.getElementById('p-nav-'+n);
  if(panel){panel.classList.add('active');
    // show phase banner before this step
    const prev=panel.previousElementSibling;
    if(prev&&prev.classList.contains('p-phase-banner')) prev.classList.add('visible');
    // show gate after the last step of a phase when returning
  }
  if(nav) nav.classList.add('active');
  populateStep(n);
  window._pStep=n;
}

function populateStep(n){
  const panel=document.getElementById('p-step-'+n);
  if(!panel) return;
  panel.querySelectorAll('[data-state-key]').forEach(el=>{
    if(el.value) return;
    const val=psGetVal(el.dataset.stateKey,el.dataset.fallbackKey);
    if(val) el.value=val;
  });
  const dateEl=panel.querySelector('input[name="current_date"]');
  if(dateEl&&!dateEl.value) dateEl.value=new Date().toISOString().slice(0,10);
}

async function runPipelineStep(n){
  const form=document.getElementById('p-form-'+n);
  const outEl=document.getElementById('p-out-'+n);
  const statusEl=document.getElementById('p-status-'+n);
  const runBtn=document.getElementById('p-run-btn-'+n);
  const spinEl=document.getElementById('p-spin-'+n);
  const fields={};
  new FormData(form).forEach((v,k)=>fields[k]=v);
  form.querySelectorAll('[data-save-key]').forEach(el=>psSave(el.dataset.saveKey,el.value));
  outEl.innerHTML='';outEl.classList.remove('empty');
  runBtn.disabled=true;if(spinEl)spinEl.style.display='inline-flex';
  statusEl.textContent='Waiting for Claude…';
  ['p-copy-','p-dl-','p-next-'].forEach(p=>{const el=document.getElementById(p+n);if(el)el.style.display='none';});
  let fullText='';
  const cursor=document.createElement('span');cursor.className='cursor';
  try{
    const resp=await fetch('/api/pipeline-run',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({step:n,fields})});
    if(!resp.ok){const err=await resp.json().catch(()=>({error:resp.statusText}));
      statusEl.textContent='✗ '+(err.error||'Error');
      outEl.innerHTML='<span style="color:var(--red)">'+(err.error||'Request failed')+'</span>';
      runBtn.disabled=false;if(spinEl)spinEl.style.display='none';return;}
    const reader=resp.body.getReader();const dec=new TextDecoder();
    outEl.appendChild(cursor);
    while(true){
      const{done,value}=await reader.read();if(done)break;
      dec.decode(value,{stream:true}).split('\n').forEach(line=>{
        if(!line.startsWith('data: '))return;
        const pl=line.slice(6).trim();if(pl==='[DONE]')return;
        try{const d=JSON.parse(pl);
          if(d.text){fullText+=d.text;cursor.remove();outEl.innerHTML=renderMd(fullText);outEl.appendChild(cursor);outEl.scrollTop=outEl.scrollHeight;statusEl.textContent='Streaming…';}
          if(d.error){statusEl.textContent='✗ '+d.error;outEl.innerHTML='<span style="color:var(--red)">'+d.error+'</span>';}
        }catch(e){}
      });
    }
    cursor.remove();
    const words=fullText.trim().split(/\s+/).length;
    statusEl.textContent='✓ Done · '+words+' words';
    runBtn.disabled=false;if(spinEl)spinEl.style.display='none';
    window['_pOut'+n]=fullText;
    const outKey=document.getElementById('p-step-'+n)?.dataset?.outputKey;
    if(outKey) psSave(outKey,fullText);
    document.getElementById('p-copy-'+n).style.display='inline-flex';
    document.getElementById('p-dl-'+n).style.display='inline-flex';
    document.getElementById('p-next-'+n).style.display='inline-flex';
    const navItem=document.getElementById('p-nav-'+n);if(navItem)navItem.classList.add('done');
    const navCheck=document.getElementById('p-nav-check-'+n);if(navCheck)navCheck.textContent='✓';
    // Show quality gate if this was last step in a phase
    showGateIfPhaseComplete(n);
    checkDownloadAll();
    return fullText;
  }catch(e){
    cursor.remove();statusEl.textContent='✗ '+e.message;
    runBtn.disabled=false;if(spinEl)spinEl.style.display='none';
  }
}

function showGateIfPhaseComplete(n){
  // Phase boundary map: last step of each phase → gate id
  const boundaries={2:1,5:2,7:3,10:4,13:5};
  if(boundaries[n]){
    const gate=document.getElementById('gate-'+boundaries[n]);
    if(gate) gate.classList.add('visible');
  }
}

function nextStep(n){
  if(n<13) showStep(n+1); else showStep(14);
}

function passGate(ph){
  // next phase start steps
  const starts={1:3,2:6,3:8,4:11,5:14};
  showStep(starts[ph]||14);
}

function failGate(ph){
  const sel=document.getElementById('gate-route-'+ph);
  const step=parseInt(sel?.value||'0');
  if(step>0) showStep(step);
}

// One-shot: run all 13 agents in sequence
async function runOneShot(){
  const btn=document.getElementById('oneshot-btn');
  if(btn) btn.disabled=true;
  for(let n=1;n<=13;n++){
    showStep(n);
    await new Promise(r=>setTimeout(r,200));
    try{ await runPipelineStep(n); }catch(e){ console.warn('Step '+n+' error:',e); }
  }
  showStep(14);
  if(btn) btn.disabled=false;
}

function copyStepOutput(n){
  const text=window['_pOut'+n]||'';if(!text)return;
  const btn=document.getElementById('p-copy-'+n);
  function ok(){if(btn){btn.textContent='✓';setTimeout(()=>btn.textContent='⎘ Copy',1500);}}
  function fb(){const el=document.createElement('textarea');el.value=text;el.style.cssText='position:fixed;opacity:0;top:0;left:0;width:1px;height:1px';document.body.appendChild(el);el.focus();el.select();try{document.execCommand('copy');ok();}catch(e){}document.body.removeChild(el);}
  if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(text).then(ok).catch(fb);else fb();
}

function dlStep(n,id){
  const text=window['_pOut'+n]||'';if(!text)return;
  const a=document.createElement('a');
  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(text);
  a.download='step'+n+'-'+id+'.md';a.click();
}

function dlDeliverable(d){
  const s=psGet();
  const content={
    1:s.final_draft||s.draft_humanized||s.draft_seo||'',
    2:s.seo_report||'',
    3:s.calendar_output||'',
    4:s.draft_seo||'',
    5:s.decay_report||'',
    6:(s.factcheck_output||'')+(s.citations_output?'\n\n---\n\n'+s.citations_output:''),
  }[d]||'';
  const names={1:'blog-post',2:'seo-metadata',3:'social-media',4:'link-map',5:'decay-report',6:'editorial-notes'};
  if(!content){alert('Run the relevant agents first to generate this deliverable.');return;}
  const a=document.createElement('a');
  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(content);
  a.download='deliverable-'+d+'-'+names[d]+'.md';a.click();
}

function downloadAll(){
  const s=psGet();
  const keys=['kw_output','brief_output','outline_output','draft_v1','draft_seo',
              'factcheck_output','citations_output','draft_humanized','headlines_output',
              'final_draft','seo_report','decay_report','calendar_output'];
  const labels=['Agent 1 — Keyword Research','Agent 2 — Content Brief','Agent 3 — Outline',
                'Agent 4 — First Draft','Agent 5 — SEO Optimized','Agent 6 — Fact Check',
                'Agent 7 — Citations Audit','Agent 8 — Humanized','Agent 9 — Headlines',
                'Agent 10 — Polished Final','Agent 11 — SEO Check','Agent 12 — Decay Report',
                'Agent 13 — Editorial Calendar'];
  let md='# Blog Orchestration Pipeline — All Outputs\n\n';
  md+='> Generated: '+new Date().toLocaleString()+'\n\n';
  md+='---\n\n## 📦 DELIVERABLES SUMMARY\n\n';
  md+='1. Blog Post — see Agent 10 Polished Final\n';
  md+='2. SEO Metadata — see Agent 11 SEO Check\n';
  md+='3. Social Media — see Agent 13 Editorial Calendar\n';
  md+='4. Internal Link Map — see Agent 5 SEO Optimized\n';
  md+='5. Decay Report — see Agent 12\n';
  md+='6. Editorial Notes — see Agents 6 & 7\n\n---\n\n';
  keys.forEach((k,i)=>{if(s[k])md+=`## ${labels[i]}\n\n${s[k]}\n\n---\n\n`;});
  const a=document.createElement('a');
  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(md);
  a.download='blog-pipeline-complete.md';a.click();
}

function checkDownloadAll(){
  const s=psGet();
  const hasAny=Object.keys(s).some(k=>k.endsWith('_output')||k==='draft_v1'||k==='final_draft');
  const btn=document.getElementById('p-dl-all');if(btn)btn.disabled=!hasAny;
  // Update QA gate indicators
  const gateMap={1:'final_draft',2:'seo_report',3:'calendar_output',4:'draft_seo',5:'decay_report',6:'factcheck_output'};
  Object.entries(gateMap).forEach(([d,k])=>{
    const el=document.getElementById('qa-'+d);
    if(el) el.innerHTML=s[k]?'<span style="color:var(--green);font-size:11px">✓ Ready</span>':'<span style="color:var(--muted);font-size:11px">Pending</span>';
  });
}

function checkAllGates(){
  const s=psGet();
  const gates=document.getElementById('qa-gates');
  if(!gates) return;
  const checks=[
    {label:'Accuracy: All facts verified',key:'factcheck_output'},
    {label:'SEO: Technical requirements met',key:'seo_report'},
    {label:'Authenticity: Passes AI detection',key:'citations_output'},
    {label:'Readability: Logical flow, clear purpose',key:'final_draft'},
    {label:'Engagement: Strong hook, examples, CTA',key:'draft_humanized'},
    {label:'Freshness: Decay risks identified',key:'decay_report'},
    {label:'Optimization: Best headline selected',key:'final_draft'},
    {label:'Promotion: Editorial calendar ready',key:'calendar_output'},
  ];
  gates.innerHTML=checks.map(c=>
    `<div>${s[c.key]?'✅':'☐'} <strong>${c.label.split(':')[0]}:</strong> ${c.label.split(':')[1]}</div>`
  ).join('');
}

function resetPipeline(){
  if(!confirm('Reset pipeline? All step outputs will be cleared.'))return;
  sessionStorage.removeItem(PS_KEY);
  for(let n=1;n<=13;n++){
    window['_pOut'+n]=null;
    const nav=document.getElementById('p-nav-'+n);if(nav)nav.classList.remove('done');
    const check=document.getElementById('p-nav-check-'+n);if(check)check.textContent='';
    const out=document.getElementById('p-out-'+n);
    if(out){out.className='output-box empty';out.innerHTML='<span>Run Agent '+n+' to see output here</span>';}
    const st=document.getElementById('p-status-'+n);if(st)st.textContent='';
    ['p-copy-','p-dl-','p-next-'].forEach(p=>{const el=document.getElementById(p+n);if(el)el.style.display='none';});
  }
  document.querySelectorAll('.phase-gate').forEach(el=>el.classList.remove('visible'));
  showStep(1);
}

document.addEventListener('DOMContentLoaded',()=>{showStep(1);checkDownloadAll();});
"""

    # ── One-shot quick start card ────────────────────────────────────────────
    oneshot_html = """
<div class="oneshot-card" id="oneshot-panel">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
    <div>
      <div style="font-weight:700;font-size:13px">⚡ Quick Start — One-Shot Mode</div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px">
        Fill in the details, then run all 13 agents automatically in sequence.
      </div>
    </div>
    <button class="btn btn-ghost btn-sm" onclick="document.getElementById('oneshot-panel').style.display='none'">×</button>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px">
    <div class="form-group" style="margin:0">
      <label class="field-label">Topic</label>
      <input type="text" id="os-topic" placeholder="e.g. AI content marketing">
    </div>
    <div class="form-group" style="margin:0">
      <label class="field-label">Audience</label>
      <input type="text" id="os-audience" placeholder="e.g. marketing managers">
    </div>
    <div class="form-group" style="margin:0">
      <label class="field-label">Goal</label>
      <select id="os-goal">
        <option>SEO ranking</option><option>Lead generation</option>
        <option>Brand awareness</option><option>Engagement</option>
      </select>
    </div>
    <div class="form-group" style="margin:0">
      <label class="field-label">Tone</label>
      <select id="os-tone">
        <option>Conversational</option><option>Professional</option>
        <option>Expert</option><option>Accessible</option>
      </select>
    </div>
    <div class="form-group" style="margin:0">
      <label class="field-label">Length</label>
      <select id="os-length">
        <option value="1500">Medium — 1,500 words</option>
        <option value="2000">Long — 2,000 words</option>
        <option value="2500">Long-form — 2,500+</option>
      </select>
    </div>
    <div class="form-group" style="margin:0">
      <label class="field-label">Content Type</label>
      <select id="os-type">
        <option value="guide">Guide / Pillar</option>
        <option value="how-to">How-To / Tutorial</option>
        <option value="listicle">Listicle</option>
        <option value="opinion">Opinion / POV</option>
      </select>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <button class="btn btn-primary" id="oneshot-btn" onclick="prefillAndRunAll()">
      🚀 Run All 13 Agents
    </button>
    <span style="font-size:11px;color:var(--muted)">Estimated time: 10–20 min depending on model</span>
  </div>
</div>
<script>
function prefillAndRunAll(){
  const topic=document.getElementById('os-topic').value.trim();
  if(!topic){alert('Enter a topic first.');return;}
  psSave('topic',topic);
  psSave('audience',document.getElementById('os-audience').value||'general audience');
  psSave('goal',document.getElementById('os-goal').value);
  psSave('tone',document.getElementById('os-tone').value);
  psSave('word_count',document.getElementById('os-length').value);
  psSave('content_type',document.getElementById('os-type').value);
  runOneShot();
}
</script>
"""

    # Build the body
    ok = claude_available()
    pill_cls = "ok" if ok else ""
    pill_label = "Claude connected" if ok else "claude CLI not found"

    body = f"""
<style>{css_pipeline}</style>
{oneshot_html}
<div class="pipeline-layout">
  <div class="pipeline-sidebar">
    <div class="pipeline-sidebar-header">
      <a href="/" class="btn btn-ghost btn-sm" style="margin-bottom:8px;display:inline-flex">← Home</a>
      <div style="font-weight:700;font-size:13px">📋 13-Agent Pipeline</div>
      <div style="font-size:10px;color:var(--muted);margin-top:2px">6 phases · sequential orchestration</div>
    </div>
    <div class="p-nav">{nav_items}</div>
    <div class="pipeline-sidebar-footer">
      <button class="btn btn-ghost btn-sm" onclick="resetPipeline()" style="width:100%;justify-content:center">↺ Reset</button>
      <button class="btn btn-secondary btn-sm" id="p-dl-all" onclick="downloadAll()" disabled
              style="width:100%;justify-content:center">⬇ Download All</button>
    </div>
  </div>
  <div class="pipeline-main">
    {panels}
  </div>
</div>
<script>{js_pipeline}</script>
"""

    return render_template_string(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blog Orchestration Pipeline — Claude Blog</title>
<style>{CSS}</style>
</head>
<body>
<nav>
  <div class="nav-brand">✍ Claude<em>Blog</em></div>
  <a href="/" class="nav-link">Home</a>
  <a href="/pipeline" class="nav-link active" style="color:var(--accent);font-weight:600">⚡ Pipeline</a>
  <a href="/authority" class="nav-link" style="color:#d29922;font-weight:600">🏆 Authority</a>
  <a href="/run/keyword-research" class="nav-link">Keywords</a>
  <a href="/run/write" class="nav-link">Write</a>
  <a href="/run/humanize" class="nav-link">Humanize</a>
  <a href="/run/ai-proof" class="nav-link">AI-Proof</a>
  <a href="/saved" class="nav-link">Saved</a>
  <a href="/settings" class="nav-link">Settings</a>
  <div class="nav-spacer"></div>
  <div class="status-pill {pill_cls}"><span class="dot"></span>{pill_label}</div>
</nav>
{body}
<script>{JS}</script>
</body>
</html>""")


@app.route("/pipeline")
def pipeline():
    return _build_pipeline_page()


@app.route("/api/pipeline-run", methods=["POST"])
def api_pipeline_run():
    if not claude_available():
        return jsonify({"error": "claude CLI not found"}), 503

    data   = request.get_json()
    step_n = int(data.get("step", 0))
    fields = data.get("fields", {})

    if step_n < 1 or step_n > len(PIPELINE_STEPS):
        return jsonify({"error": f"Invalid step: {step_n}"}), 400

    s             = PIPELINE_STEPS[step_n - 1]
    system_prompt = s["system_prompt"]

    try:
        user_msg = s["prompt"].format(**{k: v or "" for k, v in fields.items()})
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    def generate():
        cmd = [
            "claude", "-p", user_msg,
            "--system-prompt", system_prompt,
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--no-session-persistence",
            "--tools", "",
        ]
        if get_model():
            cmd += ["--model", get_model()]

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_ID", "ANTHROPIC_BASE_URL")}

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(ROOT), env=clean_env,
        )

        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("type") == "stream_event":
                    inner = ev.get("event", {})
                    if inner.get("type") == "content_block_delta":
                        delta = inner.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield f"data: {json.dumps({'text': text})}\n\n"
                elif ev.get("type") == "result" and ev.get("is_error"):
                    yield f"data: {json.dumps({'error': ev.get('result','Unknown error')})}\n\n"
            except json.JSONDecodeError:
                pass

        proc.wait()
        if proc.returncode not in (0, None):
            err = proc.stderr.read() if proc.stderr else ""
            if err:
                yield f"data: {json.dumps({'error': err[:300]})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



# ===========================================================================
# AUTHORITY ARTICLE PIPELINE  (19 agents · 5 phases · 10,000–15,000 words)
# ===========================================================================

AUTHORITY_PHASES = [{'phase': 1, 'label': 'Research Foundation', 'icon': '🔬', 'steps': [1, 2, 3, 4, 5, 6], 'color': '#58a6ff', 'gate': 'All research complete: audience mapped, competitors analyzed, 25+ statistics sourced, keyword strategy locked, content architecture approved, data library compiled.', 'fail_routes': {'Step 1 (Audience Research)': 1, 'Step 2 (Competitive Research)': 2, 'Step 3 (Trend & Data)': 3, 'Step 4 (Keyword Strategy)': 4, 'Step 5 (Content Architecture)': 5, 'Step 6 (Data Enrichment)': 6}}, {'phase': 2, 'label': 'Strategic Blueprint', 'icon': '🗺', 'steps': [7], 'color': '#d29922', 'gate': 'Master blueprint reviewed: 15-section structure, word counts, data allocation map, keyword integration plan, visual asset specs all confirmed.', 'fail_routes': {'Step 7 (Master Blueprint)': 7}}, {'phase': 3, 'label': 'Content Creation', 'icon': '✍', 'steps': [8, 9, 10], 'color': '#3fb950', 'gate': '4,000-6,000 word draft complete. SEO targets met. All appendices, FAQ (30+ Qs), glossary (40 terms), and supplemental package finished.', 'fail_routes': {'Step 8 (Authority Writer)': 8, 'Step 9 (SEO Optimization)': 9, 'Step 10 (Appendices)': 10}}, {'phase': 4, 'label': 'Quality & Polish', 'icon': '💎', 'steps': [11, 12, 13, 14, 15, 16], 'color': '#bc8cff', 'gate': 'Passes AI detection. All facts verified. All citations attributed. Best headline selected. Every word earns its place. SEO audit green.', 'fail_routes': {'Step 11 (Humanizer)': 11, 'Step 12 (Headlines)': 12, 'Step 13 (Editorial Polish)': 13, 'Step 14 (Fact Check)': 14, 'Step 15 (Citations Audit)': 15, 'Step 16 (SEO Audit)': 16}}, {'phase': 5, 'label': 'Publication Ready', 'icon': '🚀', 'steps': [17, 18, 19], 'color': '#f85149', 'gate': 'CMS package assembled. Schema markup valid. Social variants written. 30-day promotion calendar complete. All launch checklist items checked.', 'fail_routes': {'Step 17 (CMS Assembly)': 17, 'Step 18 (Social & Metadata)': 18, 'Step 19 (Launch Prep)': 19}}]

AUTHORITY_STEPS = [{'step': 1, 'phase': 1, 'id': 'aud', 'icon': '👥', 'agent': 'Agent 1', 'label': 'Audience Research', 'description': 'Deep-dive audience analysis: demographics, 15-20 pain points, 3-5 segments, decision-making patterns, direct quotes, journey map.', 'web_tools': True, 'system_prompt': "You are an Audience Intelligence Specialist. Conduct a deep-dive audience analysis (3,000+ words).\n\n## DELIVERABLES\n\n### 1. DEMOGRAPHIC PROFILE\nAge range, gender split, income, education, job titles, geography, company size if B2B.\n\n### 2. PSYCHOGRAPHIC DEEP-DIVE\nCore values, motivations, identity, aspirations, fears, daily friction points.\n\n### 3. PAIN POINTS (15-20 ranked)\nFor each: problem -> emotional impact -> what they've tried -> why it failed -> what they really need.\nRank by: Urgency (1-10) | Frequency (1-10) | Cost of not solving (1-10)\n\n### 4. DECISION-MAKING PATTERNS\nHow do they research? Who influences them? What triggers action? What objections block them?\n\n### 5. AUDIENCE SEGMENTS (3-5)\nFor each: name, size estimate, primary pain point, preferred content format, purchase behavior, best CTA.\n\n### 6. CUSTOMER JOURNEY MAP\nAwareness -> Consideration -> Decision -> Retention.\nWhat content does each stage need?\n\n### 7. VOICE OF CUSTOMER (direct quotes)\n3-5 realistic quotes capturing exact language. Note source for each.\n\nOutput minimum 3,000 words. Use real language patterns from this audience.", 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'e.g. Email marketing automation for SaaS'}, {'name': 'industry', 'label': 'Industry / Niche', 'type': 'text', 'placeholder': 'e.g. B2B SaaS, e-commerce, healthcare'}], 'prompt': 'Conduct a complete audience intelligence analysis for an authority article on: {topic}\n\nIndustry/niche: {industry}', 'output_key': 'audience_research', 'saves': ['topic', 'industry']}, {'step': 2, 'phase': 1, 'id': 'comp', 'icon': '🏆', 'agent': 'Agent 2', 'label': 'Competitive Landscape', 'description': 'Analyze 20 competitor articles, build competitive matrix, identify 5-10 content gaps, inventory 30+ authority sources.', 'web_tools': True, 'system_prompt': 'You are a Competitive Landscape Mapper. Analyze the competitive content landscape (3,000+ words).\n\n## TASK 1: COMPETITOR IDENTIFICATION\nIdentify 20 competitor articles ranking for this topic.\nURL | Domain | Word count (estimate) | Publish date | Format type\n\n## TASK 2: COMPETITIVE MATRIX\nRate each competitor 1-5 across: Depth | Data | Examples | Originality | UX | CTAs | Freshness | Visuals | Expert Quotes | Case Studies | Actionability | SEO | Structure | Tone | Authority\n\n## TASK 3: CONTENT GAP ANALYSIS (5-10 gaps)\nFor each gap: describe it -> why it matters -> how to fill it.\n\n## TASK 4: AUTHORITY SOURCE INVENTORY (30+ sources)\nTier 1 (academic/gov) | Tier 2 (industry research) | Tier 3 (company blogs)\n\n## TASK 5: FORMAT ANALYSIS\nWhat content formats dominate? What is missing?\n\n## TASK 6: UNIQUE ANGLE RECOMMENDATIONS (3-5)\nFor each: angle | target segment | why it wins\n\nOutput minimum 3,000 words. Be specific about gaps with exact examples.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'industry', 'label': 'Industry / Niche', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'industry'}], 'prompt': 'Analyze the competitive content landscape for: {topic}\n\nIndustry: {industry}', 'output_key': 'competitive_research', 'saves': []}, {'step': 3, 'phase': 1, 'id': 'trend', 'icon': '📊', 'agent': 'Agent 3', 'label': 'Trend & Data Research', 'description': 'Find 25-40 verified statistics with sources, 10+ expert quotes, 3-5 case studies with measurable results, tools comparison matrix.', 'web_tools': True, 'system_prompt': 'You are a Trend & Data Research Specialist. Build the complete data foundation (4,000+ words).\n\n## TASK 1: INDUSTRY TREND ANALYSIS\nWhat is changing in this space right now?\nWhat emerging tools are disrupting it?\nWhat best practices evolved in the last 2-3 years?\nWhat predictions are experts making for the next 1-3 years?\n\n## TASK 2: STATISTICS INVENTORY (25-40 stats)\nFormat: # | Statistic | Source | Year | Sample size | Why it matters | Tier (1/2/3) | Surprising? (Y/N)\nRules: Only stats from 2022-2025. Tier 1 preferred. Exact numbers only.\n\n## TASK 3: EXPERT PERSPECTIVES (10+ quotes)\nFor each: Full name + credentials | Direct quote | Source + date | What point it supports\n\n## TASK 4: CASE STUDIES (3-5)\nFor each: Company/size | Challenge | Approach (3-5 steps) | Results (specific %, $, time) | Lesson | Source\n\n## TASK 5: TOOLS & SOLUTIONS MATRIX (10-15 tools)\nTool | Best For | Price Range | Pros | Cons | Who Should Use It\n\nOutput minimum 4,000 words. Every statistic must have a source.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'industry', 'label': 'Industry / Niche', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'industry'}], 'prompt': 'Build the complete data foundation for an authority article on: {topic}\n\nIndustry: {industry}', 'output_key': 'trend_research', 'saves': []}, {'step': 4, 'phase': 1, 'id': 'kw', 'icon': '🔍', 'agent': 'Agent 4', 'label': 'Keyword Strategy', 'description': 'Primary keyword selection, LSI mapping, question keywords, search intent, keyword density targets, title/meta variants.', 'web_tools': False, 'system_prompt': 'You are an SEO Keyword Strategy Specialist. Build the complete keyword map.\n\n## 1. PRIMARY KEYWORD SELECTION\nBest primary keyword: rationale, estimated volume, difficulty, search intent.\n\n## 2. SECONDARY KEYWORDS (5-8)\nKeyword | Volume est. | Intent | Best placement\n\n## 3. QUESTION KEYWORDS (10-15)\nQuestions this article should answer. Prioritize PAA-style questions.\n\n## 4. LSI / SEMANTIC KEYWORDS (15-20)\nSemantically related terms. Map each to the section where it fits naturally.\n\n## 5. LONG-TAIL OPPORTUNITIES (5-8)\nLow competition, high intent long-tail variants.\n\n## 6. KEYWORD DENSITY TARGETS\nPrimary keyword: target 0.5-1.5%.\n\n## 7. TITLE TAG OPTIONS (5 variants)\nOne emotional, one number-led, one question, one how-to, one definitive guide.\n\n## 8. META DESCRIPTION (3 variants, 150-160 chars each)\n\n## 9. URL SLUG\nShort, keyword-rich, no stop words.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'audience_research', 'label': 'Audience Research', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 1 output', 'state_key': 'audience_research'}, {'name': 'competitive_research', 'label': 'Competitive Research', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 2 output', 'state_key': 'competitive_research'}], 'prompt': 'Build the complete keyword strategy.\n\nTopic: {topic}\n\nAudience Research:\n---\n{audience_research}\n\nCompetitive Research:\n---\n{competitive_research}', 'output_key': 'keyword_strategy', 'saves': []}, {'step': 5, 'phase': 1, 'id': 'arch', 'icon': '🏛', 'agent': 'Agent 5', 'label': 'Content Architecture', 'description': '4-7 content pillars, sub-topic tree, depth framework, information sequencing, differentiation strategy, dependency map.', 'web_tools': False, 'system_prompt': 'You are a Strategic Content Design Specialist. Design the information architecture.\n\n## TASK 1: CONTENT PILLARS (4-7)\nFor each: name | why essential | audience segment | depth level (surface/intermediate/expert)\n\n## TASK 2: SUB-TOPIC MAPPING\nFor each pillar, 2-5 sub-topics with rationale.\n\n## TASK 3: DEPTH FRAMEWORK\nFor each section: surface | intermediate | expert | recommended depth for THIS article.\n\n## TASK 4: INFORMATION SEQUENCING\nOptimal reading order. Dependency chain. Aha moment location.\nEmotional arc: Problem -> Tension -> Insight -> Relief -> Action\n\n## TASK 5: DIFFERENTIATION STRATEGY\nWhat can this article add that NO OTHER article has?\n\n## TASK 6: CONTENT DEPENDENCY MAP\nTree showing how sections connect and build on each other.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'audience_research', 'label': 'Audience Research', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 1', 'state_key': 'audience_research'}, {'name': 'competitive_research', 'label': 'Competitive Research', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 2', 'state_key': 'competitive_research'}, {'name': 'keyword_strategy', 'label': 'Keyword Strategy', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 4', 'state_key': 'keyword_strategy'}], 'prompt': 'Design the content architecture.\n\nTopic: {topic}\n\nAudience:\n---\n{audience_research}\n\nCompetitive Research:\n---\n{competitive_research}\n\nKeyword Strategy:\n---\n{keyword_strategy}', 'output_key': 'content_architecture', 'saves': []}, {'step': 6, 'phase': 1, 'id': 'data', 'icon': '📚', 'agent': 'Agent 6', 'label': 'Data Enrichment Library', 'description': 'Compile all research: statistics reference, case study library, expert insights, tools matrix, templates inventory, research gaps.', 'web_tools': False, 'system_prompt': 'You are a Data Enrichment Specialist. Compile all research into a structured library.\n\n## SECTION 1: STATISTICS REFERENCE\nFor each stat: STAT #N | Statistic | Source | Year | Tier | Best used in | Context | Surprising?\nGroup by theme.\n\n## SECTION 2: CASE STUDY LIBRARY (3-10)\nCASE STUDY: [Company] | Industry | Size\nChallenge | Approach | Results (specific numbers) | Quote | Lesson | Use in: [section]\n\n## SECTION 3: EXPERT INSIGHTS\nEXPERT: [Name] | Credentials | Key insight | Direct quote | Source | Use in: [section]\n\n## SECTION 4: TOOLS COMPARISON MATRIX\nReady-to-embed comparison table.\n\n## SECTION 5: TEMPLATES & FRAMEWORKS\nWhat it is | Source | How reader can use it\n\n## SECTION 6: RESEARCH GAPS\nWhat data is missing? Where does research feel thin?\n\nOutput: Complete annotated library with 50+ sources.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'trend_research', 'label': 'Trend & Data Research', 'type': 'textarea', 'rows': 5, 'placeholder': 'Auto-filled from Step 3 output', 'state_key': 'trend_research'}], 'prompt': 'Compile all research into a structured reference library.\n\nTopic: {topic}\n\nResearch Data:\n---\n{trend_research}', 'output_key': 'data_library', 'saves': []}, {'step': 7, 'phase': 2, 'id': 'blueprint', 'icon': '🗺', 'agent': 'Agent 7', 'label': 'Master Blueprint', 'description': '15-section article structure with word counts, data allocation map, keyword integration plan, visual asset specs (8-10), CTA strategy.', 'web_tools': False, 'system_prompt': 'You are a Master Content Architect. Build the complete writing blueprint.\n\n## MASTER OUTLINE (15 sections, 4,000-6,000 words main body)\n\nFor EACH section:\nSection title (H2) | Purpose | Target word count\nWhich statistics (by number) | Which case study | Which expert quote\nSubheadings (H3s) with word count targets\nData/example placement notes\nTransition to next section\n\nRequired sections:\n1. Opening (~500) -- hook, takeaways box, primary keyword\n2. Foundational Knowledge (~700)\n3-6. Core Concepts (~900 each)\n7. Advanced Strategies (~1,100)\n8. Implementation Framework (~1,300)\n9. Common Mistakes (~700)\n10. Tools & Solutions (~700)\n11. Advanced Considerations (~900)\n12. Expert Perspectives (~700)\n13. ROI & Business Case (~900)\n14. Quick Start Guide (~450)\n15. Conclusion (~450)\n\n## DATA ALLOCATION MAP\nMap every stat, case study, and expert quote to its section. Nothing unassigned.\n\n## KEYWORD INTEGRATION STRATEGY\nPrimary: title, H1, intro, 2+ H2s. Secondary: one per H2. Questions: as H3s.\n\n## VISUAL ASSET PLAN (8-10 assets)\nType | What it shows | Which section | Data source\n\n## CTA STRATEGY\nOpening CTA | 2-3 mid-article CTAs | Closing CTA\n\n## SUPPORTING CONTENT PLAN\n6 appendices | FAQ (30+ questions) | Glossary (30-50 terms) | Resources hub | Internal links (3-5)\n\nOutput: Complete blueprint. Writer can execute without asking a single clarifying question.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'keyword_strategy', 'label': 'Keyword Strategy', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 4', 'state_key': 'keyword_strategy'}, {'name': 'content_architecture', 'label': 'Content Architecture', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 5', 'state_key': 'content_architecture'}, {'name': 'data_library', 'label': 'Data Library', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 6', 'state_key': 'data_library'}], 'prompt': 'Build the complete master blueprint.\n\nTopic: {topic}\n\nKeyword Strategy:\n---\n{keyword_strategy}\n\nContent Architecture:\n---\n{content_architecture}\n\nData Library:\n---\n{data_library}', 'output_key': 'master_blueprint', 'saves': []}, {'step': 8, 'phase': 3, 'id': 'write', 'icon': '✍', 'agent': 'Agent 8', 'label': 'Authority Writer', 'description': 'Write 4,000-6,000 word article: answer-first formatting, E-E-A-T signals, burstiness, inline citations, all 15 sections per blueprint.', 'web_tools': False, 'system_prompt': "You are an Authority Content Writer. Transform the blueprint into a publication-ready draft.\n\n## WRITING MANDATE\nTarget: 4,000-6,000 words main article body.\nFollow the 15-section blueprint exactly.\nEvery factual claim must cite a source from the data library.\n\n## ANSWER-FIRST FORMATTING\nOpen every H2 with a 1-2 sentence direct answer.\nKey takeaways box in opening (3-5 bullets).\n\n## E-E-A-T SIGNALS\nEmbed expert quotes naturally. Reference case studies with specific outcomes.\nCite sources inline: (Gartner, 2024). Acknowledge complexity where honest.\n\n## BURSTINESS\nAlternate short (5-12 words), medium (15-25), complex (30-45) sentences.\nNever 3+ same length back-to-back.\n\n## BANNED WORDS (never use)\ndelve, tapestry, nuanced, multifaceted, game-changer, leverage (verb), synergy,\nparadigm shift, holistic, seamless, robust, cutting-edge, utilize, facilitate,\nmoreover, furthermore, in conclusion, it is worth noting\n\n## AI CITATION OPTIMIZATION\nStandalone declarative sentences for key facts.\nPrecise numbers (73%, not 'most'). Define terms on first use.\nFAQ-style Q&A for 3-5 key questions per major section.\n\n## OUTPUT FORMAT\nFull article with H2/H3 hierarchy, [VISUAL] markers, inline citations.\nEnd each section: <!-- [SECTION NAME: XXX words] -->\nEnd document with total word count. Zero placeholders.", 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'master_blueprint', 'label': 'Master Blueprint', 'type': 'textarea', 'rows': 5, 'placeholder': 'Auto-filled from Step 7 output', 'state_key': 'master_blueprint'}, {'name': 'data_library', 'label': 'Data Library', 'type': 'textarea', 'rows': 4, 'placeholder': 'Auto-filled from Step 6 output', 'state_key': 'data_library'}], 'prompt': 'Write the complete authority article.\n\nTopic: {topic}\n\nMaster Blueprint:\n---\n{master_blueprint}\n\nData Library:\n---\n{data_library}', 'output_key': 'article_draft', 'saves': []}, {'step': 9, 'phase': 3, 'id': 'seo', 'icon': '📈', 'agent': 'Agent 9', 'label': 'SEO Optimization', 'description': 'Embed keywords, validate title/meta/H2 coverage, optimize featured snippets, add link anchors, readability scoring.', 'web_tools': False, 'system_prompt': 'You are an SEO Optimization Specialist. Optimize the article for maximum search visibility.\n\n## TASK 1: KEYWORD INTEGRATION AUDIT\nPrimary keyword in: title, first 100 words, 2+ H2s, meta description.\nSecondary: one per H2. Questions: as H3s. LSI: distributed naturally.\nDensity check: primary 0.5-1.5%.\n\n## TASK 2: TITLE & META OPTIMIZATION\nFinal title (60 chars max) | Meta description (150-160 chars) | URL slug\n\n## TASK 3: HEADING HIERARCHY\nOne H1. Logical H2 progression. H3s only under H2s. No skipped levels.\n\n## TASK 4: FEATURED SNIPPET OPTIMIZATION\n3-5 positions to win. For each: question | format | content adjustment.\n\n## TASK 5: LINK ANCHORS\nMark 3-5 internal link spots: [INTERNAL LINK: anchor text | target page topic]\n\n## TASK 6: EXTERNAL LINK AUDIT\nMark all source links: [EXTERNAL LINK: anchor | destination | rel=follow]\n\n## TASK 7: READABILITY\nTarget 8th-10th grade. Flag dense paragraphs (>5 lines).\n\n## OUTPUT\n1. SEO-optimized full article\n2. SEO checklist: pass/fail\n3. Recommended changes summary', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'keyword_strategy', 'label': 'Keyword Strategy', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 4', 'state_key': 'keyword_strategy'}, {'name': 'article_draft', 'label': 'Article Draft', 'type': 'textarea', 'rows': 6, 'placeholder': 'Auto-filled from Step 8 output', 'state_key': 'article_draft'}], 'prompt': 'SEO-optimize the authority article.\n\nTopic: {topic}\n\nKeyword Strategy:\n---\n{keyword_strategy}\n\nArticle Draft:\n---\n{article_draft}', 'output_key': 'article_seo', 'saves': []}, {'step': 10, 'phase': 3, 'id': 'appx', 'icon': '📎', 'agent': 'Agent 10', 'label': 'Appendices & Supplements', 'description': 'Build 6 appendices (300-600 words each), FAQ (30+ Qs), glossary (40 terms), resources hub, internal/external link targets.', 'web_tools': False, 'system_prompt': "You are a Supplemental Content Architect. Build the complete supporting package.\n\n## DELIVERABLE 1: 6 APPENDICES (300-600 words each)\nThemes: (1) Step-by-step implementation | (2) Tools & resources reference |\n(3) Case study deep-dive | (4) Templates & frameworks | (5) Troubleshooting | (6) Advanced techniques\nEach: Title | Extends which section | Word count | Full text (no placeholders)\n\n## DELIVERABLE 2: FAQ SECTION (30+ questions)\nGroup into 4-6 clusters:\nQ: [question exactly as user types] | A: [2-5 direct sentences]\nMark 5 as 'Featured Snippet Targets'.\nClusters: Beginner | Implementation | Troubleshooting | Advanced | Cost/ROI\n\n## DELIVERABLE 3: GLOSSARY (30-50 terms)\nAlphabetical. Term: definition (1-3 plain English sentences). Related terms: [2-3]\n\n## DELIVERABLE 4: RESOURCES HUB\nTools | Research sources | Communities | Books (URL, best-for, price tier)\n\n## DELIVERABLE 5: INTERNAL LINK TARGETS (3-5)\nAnchor text | Target page | Placement | SEO rationale\n\n## DELIVERABLE 6: EXTERNAL AUTHORITY LINKS (5-8)\nAnchor text | Target publication | Domain authority | rel\n\nAll appendices fully written. All FAQ answers complete. No placeholder text.", 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'article_seo', 'label': 'SEO-Optimized Article', 'type': 'textarea', 'rows': 5, 'placeholder': 'Auto-filled from Step 9 output', 'state_key': 'article_seo'}, {'name': 'data_library', 'label': 'Data Library', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 6 output', 'state_key': 'data_library'}], 'prompt': 'Build the complete supplemental content package.\n\nTopic: {topic}\n\nArticle:\n---\n{article_seo}\n\nData Library:\n---\n{data_library}', 'output_key': 'appendices', 'saves': []}, {'step': 11, 'phase': 4, 'id': 'human', 'icon': '🙋', 'agent': 'Agent 11', 'label': 'Content Humanizer', 'description': 'Remove AI patterns, add burstiness and contractions, inject personal voice, vary sentence length, remove banned vocabulary.', 'web_tools': False, 'system_prompt': "You are a Content Humanization Specialist. Make this indistinguishable from expert human writing.\n\n## SENTENCE PATTERNS\nVary length dramatically: 6-word punches + 35-word complex sentences.\nAdd intentional fragments occasionally ('Worth it? Absolutely.').\nUse contractions: don't, won't, it's, here's, they're.\nStart some sentences with 'And', 'But', 'So', 'Because'.\n\n## BANNED AI VOCABULARY (eliminate every instance)\ndelve, tapestry, nuanced, multifaceted, game-changer, leverage (verb), synergy,\nparadigm shift, holistic, seamless, robust, cutting-edge, best-in-class, empower,\ntransformative, utilize, facilitate, endeavor, moreover, furthermore,\nin conclusion, it is worth noting, it goes without saying, as we navigate,\nin today's rapidly evolving, at the end of the day\n\n## STRUCTURAL CHANGES\nBreak any paragraph >5 lines into 2-3 shorter ones.\nReplace passive voice: 'it was found' -> 'researchers found'.\nAdd specific concrete details. Insert 1-2 rhetorical questions per major section.\n\n## VOICE MARKERS\nInclude an honest caveat per major section.\nUse specific, personal analogies. Drop occasional parenthetical observations.\n\n## OUTPUT\n1. Full humanized article\n2. Humanization report: changes made, banned words removed (count), top 3 impactful changes", 'fields': [{'name': 'article_seo', 'label': 'SEO Article', 'type': 'textarea', 'rows': 6, 'placeholder': 'Auto-filled from Step 9 output', 'state_key': 'article_seo'}], 'prompt': 'Humanize this authority article:\n\n{article_seo}', 'output_key': 'article_humanized', 'saves': []}, {'step': 12, 'phase': 4, 'id': 'head', 'icon': '🎯', 'agent': 'Agent 12', 'label': 'Headline Optimizer', 'description': 'Generate 20+ headline variants, score each on emotional impact/SEO/clarity, select winner, optimize all H2/H3 subheadings.', 'web_tools': False, 'system_prompt': 'You are a Headline and Subheading Optimization Specialist.\n\n## TASK 1: TITLE TAG -- 20 VARIANTS\nFor each: Title | Format | Emotional trigger | SEO score (1-10) | Clarity score (1-10) | Click score (1-10)\n\nFormats: 3 number-led | 3 how-to | 3 question | 3 emotional | 3 definitive guide | 3 contrarian | 2 curiosity gap\n\n## TASK 2: WINNER SELECTION\nPick the single best title. Explain why it beats the others.\n\n## TASK 3: SUBHEADING AUDIT\nFor each H2/H3: Current -> Improved -> Reason\nRules: promise a specific benefit | keyword where natural | front-load key word | no generic headers\n\n## TASK 4: HOOK SENTENCES\nFor each H2: write an improved opening hook sentence.\n\n## OUTPUT\n1. All 20 title variants with scores\n2. Recommended winner with rationale\n3. Updated subheadings list\n4. Updated hook sentences per section\n5. Full article with headlines/hooks applied', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'keyword_strategy', 'label': 'Primary Keyword', 'type': 'textarea', 'rows': 2, 'placeholder': 'Auto-filled from Step 4', 'state_key': 'keyword_strategy'}, {'name': 'article_humanized', 'label': 'Humanized Article', 'type': 'textarea', 'rows': 5, 'placeholder': 'Auto-filled from Step 11 output', 'state_key': 'article_humanized'}], 'prompt': 'Optimize all headlines and subheadings.\n\nTopic: {topic}\n\nKeyword Strategy:\n---\n{keyword_strategy}\n\nArticle:\n---\n{article_humanized}', 'output_key': 'article_headlines', 'saves': []}, {'step': 13, 'phase': 4, 'id': 'polish', 'icon': '✨', 'agent': 'Agent 13', 'label': 'Editorial Polish', 'description': 'Final line-edit pass: cut deadwood, fix transitions, strengthen weak sentences, check paragraph flow, verify word counts.', 'web_tools': False, 'system_prompt': "You are a Senior Editor. Perform a rigorous editorial polish pass.\n\n## CUT (ruthlessly remove)\nThroat-clearing openers ('In this article we will explore...')\nRedundant summaries. Hedge words: 'somewhat', 'rather', 'quite', 'very'.\nDouble-barrelled phrases: 'basic and fundamental', 'end result', 'future plans'.\nAny sentence that does not add information.\n\n## STRENGTHEN\nReplace weak verbs with specific, active verbs.\nEnsure every paragraph has one clear main point.\nVerify transitions feel earned, not mechanical.\nCheck each section opening delivers on the heading's promise.\n\n## STRUCTURE CHECK\nVerify key takeaways box in opening.\nCheck H2 -> H3 hierarchy is logical.\nEnsure conclusion drives toward clear action.\nVerify no section exceeds +-15% of target word count.\n\n## FLOW\nFlag awkward sentences: [AWKWARD] marker.\nConsistent tone throughout. No 3+ consecutive dense paragraphs.\n\n## OUTPUT\n1. Fully polished article\n2. Edit summary: what was cut | strengthened | words removed | readability improvement | top 5 edits", 'fields': [{'name': 'article_headlines', 'label': 'Article with Headlines', 'type': 'textarea', 'rows': 6, 'placeholder': 'Auto-filled from Step 12 output', 'state_key': 'article_headlines'}], 'prompt': 'Perform a final editorial polish pass:\n\n{article_headlines}', 'output_key': 'article_polished', 'saves': []}, {'step': 14, 'phase': 4, 'id': 'fact', 'icon': '✅', 'agent': 'Agent 14', 'label': 'Fact Check', 'description': 'Verify every statistic and claim against cited sources, flag unverifiable claims, confidence-score each data point.', 'web_tools': False, 'system_prompt': 'You are a Fact-Checking Specialist. Verify every claim in this authority article.\n\n## TASK 1: STATISTICS AUDIT\nFor every statistic:\nSTAT: [exact quote] | Source cited: [as written] | Verifiable: [Yes/No/Likely]\nConfidence: [High/Medium/Low] | Issues: [red flags] | Recommendation: [Keep/Update/Replace/Remove]\n\n## TASK 2: CLAIMS AUDIT\nFlag: no specific source | company blog | data >3 years old | speculative claim.\n\n## TASK 3: CONSISTENCY CHECK\nDo numbers contradict each other? Are percentages accurate? Do before/after claims add up?\n\n## TASK 4: ATTRIBUTION COMPLETENESS\nList all statistics with NO citation. Mark with [NEEDS SOURCE].\n\n## OUTPUT\n1. Full fact-check report\n2. Corrected article with [NEEDS SOURCE] and [FLAGGED] markers\n3. Priority fix list: top 5 issues to resolve before publishing', 'fields': [{'name': 'article_polished', 'label': 'Polished Article', 'type': 'textarea', 'rows': 6, 'placeholder': 'Auto-filled from Step 13 output', 'state_key': 'article_polished'}], 'prompt': 'Fact-check every claim and statistic:\n\n{article_polished}', 'output_key': 'factcheck_report', 'saves': []}, {'step': 15, 'phase': 4, 'id': 'cite', 'icon': '📋', 'agent': 'Agent 15', 'label': 'Citations Audit', 'description': 'Audit all citations for completeness, source quality, attribution patterns. Flag AI citation patterns. Score attribution authenticity.', 'web_tools': False, 'system_prompt': "You are a Citations Specialist. Audit all citations and attribution.\n\n## TASK 1: CITATION INVENTORY\nFor every citation: # | Citation as written | Type | Source tier | Format correct? | Issues\n\n## TASK 2: SOURCE QUALITY AUDIT\nPrimary or secondary? Recent? Biased? Accessible?\nRecommend upgrade if Tier 3 and Tier 1 equivalent exists.\n\n## TASK 3: AI CITATION PATTERN DETECTION\nFlag: 'research shows', 'experts agree', 'studies suggest' with no specific source.\nSuspiciously round numbers (80% of companies, no source).\nEm-dash heavy sentences near citations. Rule of three with no citations.\n\n## TASK 4: AUTHENTICITY SCORE (0-100)\nTier 1 sources (40 pts) | Completeness (30 pts) | Diversity (15 pts) | Recency (15 pts)\n\n## TASK 5: FORMAT STANDARDIZATION\nRecommend one consistent format. List corrections needed.\n\n## OUTPUT\n1. Full citation audit report\n2. Authenticity score with breakdown\n3. Priority fixes (top 5)\n4. Article with citations corrected/flagged", 'fields': [{'name': 'factcheck_report', 'label': 'Fact-Checked Article', 'type': 'textarea', 'rows': 6, 'placeholder': 'Auto-filled from Step 14 output', 'state_key': 'factcheck_report'}], 'prompt': 'Audit all citations and attribution:\n\n{factcheck_report}', 'output_key': 'citations_audit', 'saves': []}, {'step': 16, 'phase': 4, 'id': 'seoaudit', 'icon': '🔎', 'agent': 'Agent 16', 'label': 'SEO Audit', 'description': 'Final SEO validation: title tag, meta, heading hierarchy, keyword density, links, canonical, OG tags, schema readiness. Pass/fail checklist.', 'web_tools': False, 'system_prompt': 'You are an SEO Audit Specialist. Run the final pre-publish SEO validation.\n\n## CHECKLIST (Pass / Fail / Fix Required)\n\nON-PAGE BASICS:\nTitle tag: 60 chars max, primary keyword, compelling.\nMeta description: 150-160 chars, primary keyword, includes CTA.\nURL slug: short, keyword-rich, no stop words.\nH1: matches title, exactly one H1.\n\nHEADING HIERARCHY:\nLogical H2 progression. H3s only under H2s. Primary keyword in 2+ H2s.\n\nKEYWORD USAGE:\nPrimary density: 0.5-1.5%. In first 100 words. LSI distributed. No stuffing.\n\nLINKS:\n3-5 internal links. 3-5 external links to authoritative sources. Proper rel attributes.\n\nTECHNICAL:\nCanonical URL. OG meta tags. Schema markup specified. Images alt text. Read time.\n\nREADABILITY:\n8th-10th grade. No paragraph >5 lines. Bullets for 3+ items. Key terms bolded.\n\n## OUTPUT\n1. Full checklist Pass/Fail/Fix\n2. Critical issues (must fix)\n3. Recommended improvements\n4. Overall SEO readiness: X/100\n5. Article with SEO fixes applied', 'fields': [{'name': 'citations_audit', 'label': 'Citations-Audited Article', 'type': 'textarea', 'rows': 6, 'placeholder': 'Auto-filled from Step 15 output', 'state_key': 'citations_audit'}, {'name': 'keyword_strategy', 'label': 'Keyword Strategy', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 4', 'state_key': 'keyword_strategy'}], 'prompt': 'Run the final SEO audit.\n\nKeyword Strategy:\n---\n{keyword_strategy}\n\nArticle:\n---\n{citations_audit}', 'output_key': 'seo_audit', 'saves': []}, {'step': 17, 'phase': 5, 'id': 'cms', 'icon': '🖥', 'agent': 'Agent 17', 'label': 'CMS Assembly', 'description': 'Complete CMS package: formatted Markdown, jump-link TOC, anchor IDs, read time, Article+FAQ schema JSON-LD, OG/Twitter tags, canonical URL.', 'web_tools': False, 'system_prompt': 'You are a CMS Publishing Specialist. Assemble the complete paste-and-publish package.\n\n## TASK 1: CONTENT FORMATTING\nCMS-ready Markdown: H2=##, H3=###, bold key terms, blockquotes for quotes, bullet lists.\n\n## TASK 2: TABLE OF CONTENTS\nJump-link TOC from all H2s and H3s. Anchor slugs: lowercase-with-hyphens.\nPlace after key takeaways box.\n\n## TASK 3: READ TIME\nWord count / 238 wpm = X min read. Display: **X min read - Updated [Month Year]**\n\n## TASK 4: ARTICLE SCHEMA (JSON-LD)\nComplete Article schema: headline, description, author, datePublished, dateModified, wordCount, articleSection, keywords.\n\n## TASK 5: FAQPAGE SCHEMA (JSON-LD)\nComplete FAQPage schema from the FAQ section (all 30+ questions).\n\n## TASK 6: OG + TWITTER CARD TAGS\nAll meta tags ready for <head>: og:title, og:description, og:type, og:image, article:published_time, twitter:card.\n\n## TASK 7: CANONICAL + ROBOTS\ncanonical href | robots: index, follow\n\n## TASK 8: ASSEMBLY CHECKLIST\nPass/fail: title 60 | meta 150-160 | keyword placement | links | schema valid | TOC anchors | word count.\n\n## OUTPUT ORDER\n1. METADATA BLOCK | 2. SCHEMA | 3. OG/TWITTER | 4. TABLE OF CONTENTS | 5. FULL ARTICLE | 6. APPENDICES | 7. ANCHOR ID REFERENCE | 8. ASSEMBLY CHECKLIST', 'fields': [{'name': 'seo_audit', 'label': 'SEO-Audited Article', 'type': 'textarea', 'rows': 5, 'placeholder': 'Auto-filled from Step 16 output', 'state_key': 'seo_audit'}, {'name': 'appendices', 'label': 'Appendices Package', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 10 output', 'state_key': 'appendices'}], 'prompt': 'Assemble the complete CMS-ready publication package.\n\nArticle:\n---\n{seo_audit}\n\nAppendices:\n---\n{appendices}', 'output_key': 'cms_package', 'saves': []}, {'step': 18, 'phase': 5, 'id': 'social', 'icon': '📣', 'agent': 'Agent 18', 'label': 'Social & Metadata', 'description': 'Social variants for 5 platforms (Twitter thread, LinkedIn, Reddit, Facebook, Pinterest), email newsletter, analytics event setup.', 'web_tools': False, 'system_prompt': "You are a Content Distribution Specialist. Build the complete social media package.\n\n## DELIVERABLE 1: TWITTER/X THREAD (12-15 tweets)\nTweet 1 (Hook): bold claim or surprising stat, max 280 chars, must stop the scroll.\nTweets 2-10: numbered, one key insight per tweet.\nTweet 11: practical takeaway | Tweet 12: CTA | Tweet 13: engagement question.\nNo em-dashes. Conversational. Natural human voice.\n\n## DELIVERABLE 2: LINKEDIN POST (800-1,200 words)\nPattern interrupt opener | Personal story hook (2-3 sentences) |\n3-5 numbered insights | Broader implication | CTA | 3-5 hashtags\n\n## DELIVERABLE 3: REDDIT POST\nTitle: informational or question format, no marketing language.\nBody: value-first, helpful, self-promotion buried after value.\n\n## DELIVERABLE 4: FACEBOOK POST\nConversational opener | Key benefit in plain language | 1-2 stats | Link.\n\n## DELIVERABLE 5: PINTEREST\nPin title (100 chars) | Pin description (200-500 chars) | Board suggestion | Image brief.\n\n## DELIVERABLE 6: EMAIL NEWSLETTER\nSubject line (50 chars) | Preview text (90 chars) |\nBody: greeting | 2-sentence hook | 3 things they'll learn | 1 stat | CTA | P.S. line\n\n## DELIVERABLE 7: ANALYTICS EVENTS\n5 KPIs to track + gtag snippets for scroll depth, time milestones, CTA clicks.", 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'cms_package', 'label': 'CMS Package', 'type': 'textarea', 'rows': 5, 'placeholder': 'Auto-filled from Step 17 output', 'state_key': 'cms_package'}], 'prompt': 'Build the complete social media and distribution package.\n\nTopic: {topic}\n\nCMS Package:\n---\n{cms_package}', 'output_key': 'social_package', 'saves': []}, {'step': 19, 'phase': 5, 'id': 'launch', 'icon': '🚀', 'agent': 'Agent 19', 'label': 'Launch Checklist', 'description': '30-day promotion calendar with daily actions, full pre/at/post-publish checklist, first-48-hours playbook, 30-day review framework.', 'web_tools': False, 'system_prompt': 'You are a Content Launch Strategist. Build the complete launch plan.\n\n## DELIVERABLE 1: 30-DAY PROMOTION CALENDAR\nDay | Platform | Action | Content/Notes\nDay 1: Twitter thread + LinkedIn post\nDay 2: Reddit submission\nDay 3: Email newsletter\nDay 7: Twitter recap tweet\nDay 14: LinkedIn follow-up angle\nDay 21: Quora answer\nDay 30: Metrics review\nFill ALL 30 days with specific actions.\n\n## DELIVERABLE 2: PRE-PUBLISH CHECKLIST\nTitle in SERP preview | Meta description | Featured image 1200x630 + alt text\nCanonical URL | Schema validated | Internal links | Mobile preview | Page speed 85+\n\n## DELIVERABLE 3: AT-PUBLISH ACTIONS\nSubmit to Google Search Console | Ping sitemap\nPost to primary social | Add internal link from 2 existing posts\n\n## DELIVERABLE 4: FIRST 48 HOURS\nMonitor GSC indexing | Reply to comments within 4 hours\nTrack traffic baseline | Reach out to 2-3 people mentioned\n\n## DELIVERABLE 5: 30-DAY REVIEW\nCheck rankings | Scroll depth + time-on-page\nBest traffic source | Comments -> FAQ expansion | Schedule 6-month refresh\n\nOutput: Complete, ready-to-execute plan. All 30 days filled with specific actions.', 'fields': [{'name': 'topic', 'label': 'Article Topic', 'type': 'text', 'placeholder': 'Auto-filled from Step 1', 'state_key': 'topic'}, {'name': 'social_package', 'label': 'Social Package', 'type': 'textarea', 'rows': 4, 'placeholder': 'Auto-filled from Step 18 output', 'state_key': 'social_package'}, {'name': 'cms_package', 'label': 'CMS Package', 'type': 'textarea', 'rows': 3, 'placeholder': 'Auto-filled from Step 17 output', 'state_key': 'cms_package'}], 'prompt': 'Build the complete launch plan.\n\nTopic: {topic}\n\nSocial Package:\n---\n{social_package}\n\nCMS Package:\n---\n{cms_package}', 'output_key': 'launch_plan', 'saves': []}]



# ===========================================================================
# AUTHORITY ARTICLE PIPELINE  (19 agents · 5 phases · 10,000–15,000 words)
# ===========================================================================
# NOTE: AUTHORITY_PHASES and AUTHORITY_STEPS are injected by build_authority.py
# This file contains only the page-builder function, route, and endpoint.


def _build_authority_page():
    """Render the 19-agent, 5-phase authority article pipeline page."""

    ATOTAL = len(AUTHORITY_STEPS)
    GATE_BOUNDARY = {6: 1, 7: 2, 10: 3, 16: 4, 19: 5}
    DELIVERABLES = [
        ("Full Article",   "article_polished",  "authority_article.md"),
        ("SEO Package",    "seo_audit",         "authority_seo.md"),
        ("Appendices",     "appendices",        "authority_appendices.md"),
        ("CMS Package",    "cms_package",       "authority_cms.md"),
        ("Social Package", "social_package",    "authority_social.md"),
        ("Launch Plan",    "launch_plan",       "authority_launch.md"),
    ]

    # ── Sidebar nav ──────────────────────────────────────────────────────────
    nav_items = ""
    prev_phase = 0
    for s in AUTHORITY_STEPS:
        n  = s["step"]
        ph = s["phase"]
        if ph != prev_phase:
            ph_data = AUTHORITY_PHASES[ph - 1]
            nav_items += (
                '<div class="p-phase-header" style="border-left:3px solid ' +
                ph_data["color"] + '">' + ph_data["icon"] +
                ' Phase ' + str(ph) + ': ' + ph_data["label"] + '</div>'
            )
            prev_phase = ph
        nav_items += (
            '<div class="p-nav-item" id="p-nav-' + str(n) +
            '" data-step="' + str(n) + '" onclick="showStep(' + str(n) + ')">' +
            '<span class="p-nav-num" id="p-nav-num-' + str(n) + '">' + str(n) + '</span>' +
            '<div class="p-nav-info"><div class="p-nav-label">' +
            s["icon"] + ' ' + s["label"] + '</div>' +
            '<div class="p-nav-agent">' + s["agent"] + '</div></div>' +
            '<span class="p-nav-check" id="p-nav-check-' + str(n) + '"></span></div>'
        )
    nav_items += (
        '<div class="p-phase-header" style="border-left:3px solid #3fb950">'
        '&#128230; Phase 6: Final Deliverables</div>'
        '<div class="p-nav-item" id="p-nav-20" data-step="20" onclick="showStep(20)">'
        '<span class="p-nav-num" id="p-nav-num-20">&#128230;</span>'
        '<div class="p-nav-info"><div class="p-nav-label">&#128230; Final Deliverables</div>'
        '<div class="p-nav-agent">All outputs assembled</div></div></div>'
    )

    # ── Step panels ──────────────────────────────────────────────────────────
    panels = ""
    for s in AUTHORITY_STEPS:
        n         = s["step"]
        ph        = s["phase"]
        ph_data   = AUTHORITY_PHASES[ph - 1]
        color     = ph_data["color"]
        ph_lbl    = ph_data["label"]
        next_s    = AUTHORITY_STEPS[n] if n < ATOTAL else None
        save_key  = s.get("output_key", "")
        next_label = ("Step " + str(next_s["step"]) + ": " + next_s["label"]) if next_s else "Final Deliverables"

        form_html = ""
        for f in s.get("fields", []):
            fname   = f["name"]
            ftype   = f.get("type", "text")
            sk      = f.get("state_key", "")
            fbk     = f.get("fallback_key", "")
            da      = ('data-state-key="' + sk + '"') if sk else ""
            if fbk:
                da += ' data-fallback-key="' + fbk + '"'
            lbl     = f["label"]
            ph_text = f.get("placeholder", "")
            if ftype == "textarea":
                rows = str(f.get("rows", 4))
                form_html += (
                    '<div class="form-group"><label class="form-label">' + lbl + '</label>'
                    '<textarea name="' + fname + '" class="form-control" rows="' + rows +
                    '" placeholder="' + ph_text + '" ' + da + '></textarea></div>'
                )
            else:
                form_html += (
                    '<div class="form-group"><label class="form-label">' + lbl + '</label>'
                    '<input type="text" name="' + fname + '" class="form-control"'
                    ' placeholder="' + ph_text + '" ' + da + '></div>'
                )

        web_badge = (
            '<span style="font-size:10px;background:#1c2d3a;color:#58a6ff;padding:2px 6px;'
            'border-radius:4px;margin-left:6px">&#127760; web</span>'
        ) if s.get("web_tools") else ""

        back_style = ' style="display:none"' if n == 1 else ""
        prev_n = max(1, n - 1)

        panels += (
            '<div class="p-panel" id="p-panel-' + str(n) + '" style="display:none">'
            '<div class="p-panel-header" style="border-left:4px solid ' + color + '">'
            '<div>'
            '<div class="p-panel-title">' + s["icon"] + ' Step ' + str(n) + ': ' + s["label"] + web_badge + '</div>'
            '<div class="p-panel-meta">' + s["agent"] + ' &middot; Phase ' + str(ph) + ': ' + ph_lbl + '</div>'
            '</div>'
            '<span class="p-status-badge" id="p-status-' + str(n) + '">Ready</span>'
            '</div>'
            '<p style="color:var(--muted);font-size:13px;margin-bottom:16px">' + s["description"] + '</p>'
            '<form id="p-form-' + str(n) + '" onsubmit="return false">'
            + form_html +
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px">'
            '<button type="button" class="btn btn-primary" onclick="runAuthorityStep(' + str(n) + ')">&#9654; Run ' + s["agent"] + '</button>'
            '<button type="button" class="btn btn-ghost btn-sm" onclick="showStep(' + str(prev_n) + ')"' + back_style + '>&#8592; Back</button>'
            '</div>'
            '</form>'
            '<div class="p-output-area" id="p-output-area-' + str(n) + '" style="display:none">'
            '<div class="p-output-toolbar">'
            '<span class="p-output-label">Output &mdash; ' + s["agent"] + '</span>'
            '<div style="display:flex;gap:6px">'
            '<button class="btn btn-ghost btn-sm" onclick="copyOutput()">&#10232; Copy</button>'
            '<button class="btn btn-ghost btn-sm" onclick="downloadOutput(\'authority_step' + str(n) + '_' + s["id"] + '.md\')">&#11015; Save</button>'
            '<button class="btn btn-secondary btn-sm" onclick="useAndNext(' + str(n) + ',\'' + save_key + '\',\'' + next_label.replace("'", "\\'") + '\')" id="p-use-btn-' + str(n) + '">'
            'Use &#8594; ' + next_label + '</button>'
            '</div>'
            '</div>'
            '<div class="p-output" id="p-output-' + str(n) + '"></div>'
            '</div>'
            '</div>'
        )

        # Quality gate after phase-boundary steps
        if n in GATE_BOUNDARY:
            ph_num = GATE_BOUNDARY[n]
            ph_d   = AUTHORITY_PHASES[ph_num - 1]
            fail_opts = "".join(
                '<option value="' + str(v) + '">' + k + '</option>'
                for k, v in ph_d["fail_routes"].items()
            )
            next_ph = str(ph_num + 1) if ph_num < 5 else "6"
            panels += (
                '<div class="p-gate" id="a-gate-' + str(ph_num) + '" style="display:none">'
                '<div class="p-gate-inner">'
                '<div class="p-gate-title">' + ph_d["icon"] + ' Phase ' + str(ph_num) + ' Quality Gate: ' + ph_d["label"] + '</div>'
                '<p class="p-gate-check">' + ph_d["gate"] + '</p>'
                '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px">'
                '<button class="btn btn-primary" onclick="passAuthorityGate(' + str(ph_num) + ')">&#10003; Pass &mdash; Continue to Phase ' + next_ph + '</button>'
                '<div style="display:flex;align-items:center;gap:6px">'
                '<select class="form-control" id="a-gate-fail-' + str(ph_num) + '" style="width:auto;padding:6px 10px;font-size:13px">'
                + fail_opts +
                '</select>'
                '<button class="btn btn-ghost btn-sm" onclick="failAuthorityGate(' + str(ph_num) + ')">&#8635; Revise</button>'
                '</div>'
                '</div>'
                '</div>'
                '</div>'
            )

    # Final deliverables panel
    dl_rows = ""
    for label, key, fname in DELIVERABLES:
        dl_rows += (
            '<tr>'
            '<td style="padding:8px 0;border-bottom:1px solid var(--border)">'
            '<button class="btn btn-ghost btn-sm" onclick="downloadDeliverable(\'' + key + '\',\'' + fname + '\')">'
            '&#11015; ' + label + '</button></td>'
            '<td style="padding:8px 0;border-bottom:1px solid var(--border);color:var(--muted);font-size:12px">'
            '<span id="a-dl-' + key + '-status">Waiting</span></td>'
            '</tr>'
        )

    panels += (
        '<div class="p-panel" id="p-panel-20" style="display:none">'
        '<div class="p-panel-header" style="border-left:4px solid #3fb950">'
        '<div>'
        '<div class="p-panel-title">&#128230; Final Deliverables</div>'
        '<div class="p-panel-meta">All 19 agents complete &middot; Authority article ready to publish</div>'
        '</div>'
        '</div>'
        '<p style="color:var(--muted);font-size:13px;margin-bottom:20px">'
        'Your 10,000&ndash;15,000 word authority article is complete. Download each deliverable below.'
        '</p>'
        '<table style="width:100%;border-collapse:collapse">' + dl_rows + '</table>'
        '<div style="margin-top:20px;display:flex;gap:8px;flex-wrap:wrap">'
        '<button class="btn btn-primary" onclick="downloadAllAuthority()">&#11015; Download All</button>'
        '<button class="btn btn-ghost btn-sm" onclick="resetAuthority()">&#8635; Start New Article</button>'
        '</div>'
        '</div>'
    )

    # Phase badge HTML
    phase_badges = ""
    for ph_data in AUTHORITY_PHASES:
        c = ph_data["color"]
        phase_badges += (
            '<span style="font-size:11px;padding:3px 8px;border-radius:12px;'
            'background:' + c + '22;color:' + c + ';border:1px solid ' + c + '55">'
            + ph_data["icon"] + ' ' + ph_data["label"] + '</span>'
        )

    # Step metadata for JavaScript (output_key per step)
    import json as _json
    step_meta_js = _json.dumps([
        {"output_key": s.get("output_key", ""), "saves": s.get("saves", [])}
        for s in AUTHORITY_STEPS
    ])
    dl_keys_js   = _json.dumps([key  for _, key, _ in DELIVERABLES])
    dl_fnames_js = _json.dumps([fname for _, _, fname in DELIVERABLES])
    gate_js      = _json.dumps(GATE_BOUNDARY)

    js_authority = (
        "const AUTHORITY_STATE_KEY='cblog_authority';\n"
        "const AUTHORITY_TOTAL=" + str(ATOTAL) + ";\n"
        "const AUTHORITY_GATE_BOUNDARY=" + gate_js + ";\n"
        "const STEP_META=" + step_meta_js + ";\n"
        "const DL_KEYS=" + dl_keys_js + ";\n"
        "const DL_FNAMES=" + dl_fnames_js + ";\n"
        "\n"
        "function aState(){try{return JSON.parse(sessionStorage.getItem(AUTHORITY_STATE_KEY)||'{}');}catch(e){return {};}}\n"
        "function aSave(d){sessionStorage.setItem(AUTHORITY_STATE_KEY,JSON.stringify(d));}\n"
        "\n"
        "function showStep(n){\n"
        "  document.querySelectorAll('.p-panel,.p-gate').forEach(el=>el.style.display='none');\n"
        "  const panel=document.getElementById('p-panel-'+n);\n"
        "  if(panel){panel.style.display='block';populateAuthorityFields(n);}\n"
        "  document.querySelectorAll('.p-nav-item').forEach(el=>el.classList.remove('active'));\n"
        "  const nav=document.getElementById('p-nav-'+n);\n"
        "  if(nav) nav.classList.add('active');\n"
        "  window._currentAuthorityStep=n;\n"
        "}\n"
        "\n"
        "function populateAuthorityFields(n){\n"
        "  const state=aState();\n"
        "  const panel=document.getElementById('p-panel-'+n);\n"
        "  if(!panel) return;\n"
        "  panel.querySelectorAll('[data-state-key]').forEach(el=>{\n"
        "    const key=el.getAttribute('data-state-key');\n"
        "    const fb=el.getAttribute('data-fallback-key');\n"
        "    const val=state[key]||(fb?state[fb]:'')||'';\n"
        "    if(val&&!el.value) el.value=val;\n"
        "  });\n"
        "}\n"
        "\n"
        "function runAuthorityStep(n){\n"
        "  const form=document.getElementById('p-form-'+n);\n"
        "  const fields={};\n"
        "  if(form) form.querySelectorAll('input,textarea,select').forEach(el=>{if(el.name) fields[el.name]=el.value;});\n"
        "  const outputArea=document.getElementById('p-output-area-'+n);\n"
        "  const outputEl=document.getElementById('p-output-'+n);\n"
        "  const statusEl=document.getElementById('p-status-'+n);\n"
        "  if(outputArea) outputArea.style.display='block';\n"
        "  if(outputEl) outputEl.textContent='';\n"
        "  if(statusEl){statusEl.textContent='Running...';statusEl.className='p-status-badge running';}\n"
        "  let full=''; window._lastOutput='';\n"
        "  fetchSSE('/api/authority-run',{step:n,fields},\n"
        "    (chunk)=>{full+=chunk;window._lastOutput=full;if(outputEl) outputEl.textContent=full;},\n"
        "    (err)=>{if(statusEl){statusEl.textContent='Error';statusEl.className='p-status-badge error';}if(outputEl) outputEl.textContent+='\\n\\n[Error: '+err+']';},\n"
        "    ()=>{\n"
        "      if(statusEl){statusEl.textContent='Complete';statusEl.className='p-status-badge complete';}\n"
        "      const checkEl=document.getElementById('p-nav-check-'+n);\n"
        "      if(checkEl) checkEl.textContent='\\u2713';\n"
        "      const navNum=document.getElementById('p-nav-num-'+n);\n"
        "      if(navNum) navNum.style.background='var(--success)';\n"
        "      const state=aState();\n"
        "      if(form) form.querySelectorAll('[name]').forEach(el=>{if(el.name&&el.value) state[el.name]=el.value;});\n"
        "      const meta=STEP_META[n-1];\n"
        "      if(meta&&meta.output_key&&full) state[meta.output_key]=full;\n"
        "      state['_step'+n+'_done']=true;\n"
        "      aSave(state);\n"
        "      showAuthorityGateIfPhaseComplete(n);\n"
        "    }\n"
        "  );\n"
        "}\n"
        "\n"
        "function useAndNext(n,saveKey,nextLabel){\n"
        "  const state=aState();\n"
        "  if(window._lastOutput&&saveKey) state[saveKey]=window._lastOutput;\n"
        "  aSave(state);\n"
        "  if(n<AUTHORITY_TOTAL) showStep(n+1); else showStep(20);\n"
        "}\n"
        "\n"
        "function showAuthorityGateIfPhaseComplete(stepN){\n"
        "  const phaseNum=AUTHORITY_GATE_BOUNDARY[stepN];\n"
        "  if(!phaseNum) return;\n"
        "  const gateEl=document.getElementById('a-gate-'+phaseNum);\n"
        "  if(gateEl){\n"
        "    document.querySelectorAll('.p-panel,.p-gate').forEach(el=>el.style.display='none');\n"
        "    gateEl.style.display='block';\n"
        "    document.getElementById('p-dl-all').disabled=false;\n"
        "  }\n"
        "}\n"
        "\n"
        "function passAuthorityGate(phaseNum){\n"
        "  const entries=Object.entries(AUTHORITY_GATE_BOUNDARY);\n"
        "  const entry=entries.find(([k,v])=>v===phaseNum);\n"
        "  if(!entry) return;\n"
        "  const afterStep=parseInt(entry[0])+1;\n"
        "  if(afterStep>AUTHORITY_TOTAL) showStep(20); else showStep(afterStep);\n"
        "}\n"
        "function failAuthorityGate(phaseNum){\n"
        "  const sel=document.getElementById('a-gate-fail-'+phaseNum);\n"
        "  if(sel) showStep(parseInt(sel.value));\n"
        "}\n"
        "\n"
        "function downloadDeliverable(key,filename){\n"
        "  const state=aState(); const content=state[key]||'No output yet.';\n"
        "  const a=document.createElement('a');\n"
        "  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(content);\n"
        "  a.download=filename; a.click();\n"
        "  const el=document.getElementById('a-dl-'+key+'-status');\n"
        "  if(el) el.textContent='Downloaded';\n"
        "}\n"
        "\n"
        "function downloadAllAuthority(){\n"
        "  DL_FNAMES.forEach((f,i)=>{\n"
        "    const state=aState(); const content=state[DL_KEYS[i]]||'No output yet.';\n"
        "    setTimeout(()=>{const a=document.createElement('a');a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(content);a.download=f;a.click();},i*300);\n"
        "  });\n"
        "}\n"
        "\n"
        "function resetAuthority(){\n"
        "  if(confirm('Reset all authority pipeline state? This cannot be undone.')){\n"
        "    sessionStorage.removeItem(AUTHORITY_STATE_KEY);\n"
        "    showStep(1);\n"
        "    document.querySelectorAll('.p-nav-check').forEach(el=>el.textContent='');\n"
        "    document.querySelectorAll('.p-nav-num').forEach(el=>el.style.background='');\n"
        "  }\n"
        "}\n"
        "\n"
        "async function runAllAuthority(){\n"
        "  const btn=document.getElementById('a-oneshot-btn');\n"
        "  if(btn){btn.disabled=true;btn.textContent='Running...';}\n"
        "  for(let n=1;n<=AUTHORITY_TOTAL;n++){\n"
        "    showStep(n);\n"
        "    await new Promise((resolve)=>{\n"
        "      const form=document.getElementById('p-form-'+n);\n"
        "      const fields={};\n"
        "      if(form) form.querySelectorAll('input,textarea,select').forEach(el=>{if(el.name) fields[el.name]=el.value;});\n"
        "      const outputEl=document.getElementById('p-output-'+n);\n"
        "      const statusEl=document.getElementById('p-status-'+n);\n"
        "      if(statusEl){statusEl.textContent='Running...';statusEl.className='p-status-badge running';}\n"
        "      let full='';\n"
        "      fetchSSE('/api/authority-run',{step:n,fields},\n"
        "        (chunk)=>{full+=chunk;window._lastOutput=full;if(outputEl) outputEl.textContent=full;},\n"
        "        (err)=>{resolve();},\n"
        "        ()=>{\n"
        "          const state=aState();\n"
        "          const meta=STEP_META[n-1];\n"
        "          if(full&&meta&&meta.output_key) state[meta.output_key]=full;\n"
        "          aSave(state);\n"
        "          if(statusEl){statusEl.textContent='Complete';statusEl.className='p-status-badge complete';}\n"
        "          const checkEl=document.getElementById('p-nav-check-'+n);\n"
        "          if(checkEl) checkEl.textContent='\\u2713';\n"
        "          resolve();\n"
        "        }\n"
        "      );\n"
        "    });\n"
        "    await new Promise(r=>setTimeout(r,800));\n"
        "  }\n"
        "  showStep(20);\n"
        "  if(btn){btn.disabled=false;btn.textContent='\\u25b6\\u25b6 Run All (One-Shot)';}\n"
        "}\n"
        "\n"
        "document.addEventListener('DOMContentLoaded',()=>{showStep(1);});\n"
    )

    body = (
        '<div class="p-layout" style="padding-top:0">'
        '<div class="p-header-bar" style="background:linear-gradient(135deg,#0d1117 0%,#1a1f2e 100%);padding:20px 32px;border-bottom:1px solid var(--border)">'
        '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">'
        '<div>'
        '<h2 style="margin:0;font-size:22px">&#127942; Authority Article Pipeline</h2>'
        '<p style="margin:4px 0 0;color:var(--muted);font-size:13px">19 agents &middot; 5 phases &middot; targets 10,000&ndash;15,000 words</p>'
        '</div>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
        '<div style="font-size:12px;color:var(--muted)">Phase progress:</div>'
        + phase_badges +
        '<button id="a-oneshot-btn" class="btn btn-secondary btn-sm" onclick="runAllAuthority()">&#9654;&#9654; Run All (One-Shot)</button>'
        '</div>'
        '</div>'
        '</div>'
        '<div style="display:flex;height:calc(100vh - 120px)">'
        '<div class="pipeline-sidebar" style="width:240px;min-width:240px">'
        '<div style="padding:12px 16px;border-bottom:1px solid var(--border)">'
        '<a href="/" class="btn btn-ghost btn-sm" style="margin-bottom:8px;display:inline-flex">&#8592; Home</a>'
        '<div style="font-weight:700;font-size:13px">&#127942; 19-Agent Authority Pipeline</div>'
        '<div style="font-size:10px;color:var(--muted);margin-top:2px">5 phases &middot; 10K&ndash;15K word articles</div>'
        '</div>'
        '<div class="p-nav">' + nav_items + '</div>'
        '<div class="pipeline-sidebar-footer">'
        '<button class="btn btn-ghost btn-sm" onclick="resetAuthority()" style="width:100%;justify-content:center">&#8635; Reset</button>'
        '<button class="btn btn-secondary btn-sm" id="p-dl-all" onclick="downloadAllAuthority()" disabled style="width:100%;justify-content:center">&#11015; Download All</button>'
        '</div>'
        '</div>'
        '<div class="pipeline-main">' + panels + '</div>'
        '</div>'
        '</div>'
        '<script>' + js_authority + '</script>'
    )

    pill_cls, pill_label = ("pill-ok", "Claude ✓") if claude_available() else ("pill-err", "Claude ✗")
    return render_template_string(
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        "<title>Authority Article Pipeline — Claude Blog</title>\n"
        "<style>" + CSS + "</style>\n"
        "</head>\n"
        "<body>\n"
        "<nav>\n"
        "  <div class=\"nav-brand\">✍ Claude<em>Blog</em></div>\n"
        "  <a href=\"/\" class=\"nav-link\">Home</a>\n"
        "  <a href=\"/pipeline\" class=\"nav-link\">⚡ Pipeline</a>\n"
        "  <a href=\"/authority\" class=\"nav-link active\" style=\"color:#d29922;font-weight:600\">\U0001f3c6 Authority</a>\n"
        "  <a href=\"/run/keyword-research\" class=\"nav-link\">Keywords</a>\n"
        "  <a href=\"/run/write\" class=\"nav-link\">Write</a>\n"
        "  <a href=\"/run/humanize\" class=\"nav-link\">Humanize</a>\n"
        "  <a href=\"/saved\" class=\"nav-link\">Saved</a>\n"
        "  <a href=\"/settings\" class=\"nav-link\">Settings</a>\n"
        "  <div class=\"nav-spacer\"></div>\n"
        "  <div class=\"status-pill " + pill_cls + "\"><span class=\"dot\"></span>" + pill_label + "</div>\n"
        "</nav>\n"
        + body +
        "\n<script>" + JS + "</script>\n"
        "</body>\n"
        "</html>"
    )


@app.route("/authority")
def authority():
    return _build_authority_page()


@app.route("/api/authority-run", methods=["POST"])
def api_authority_run():
    if not claude_available():
        return jsonify({"error": "claude CLI not found"}), 503

    data      = request.get_json()
    step_n    = int(data.get("step", 0))
    fields    = data.get("fields", {})

    if step_n < 1 or step_n > len(AUTHORITY_STEPS):
        return jsonify({"error": f"Invalid step: {step_n}"}), 400

    s             = AUTHORITY_STEPS[step_n - 1]
    system_prompt = s["system_prompt"]

    try:
        user_msg = s["prompt"].format(**{k: v or "" for k, v in fields.items()})
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 400

    web_tools     = s.get("web_tools", False)
    allowed_tools = "WebSearch,WebFetch" if web_tools else ""

    def generate():
        model = get_model()
        cmd = [
            "claude", "-p", user_msg,
            "--system-prompt", system_prompt,
            "--output-format", "stream-json",
            "--include-partial-messages", "--verbose",
            "--no-session-persistence",
        ]
        if allowed_tools:
            cmd += ["--allowedTools", allowed_tools]
        else:
            cmd += ["--tools", ""]
        if model:
            cmd += ["--model", model]

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_ID", "ANTHROPIC_BASE_URL")}

        proc = subprocess.Popen(
            cmd, env=clean_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(ROOT),
        )

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("type") == "stream_event":
                    inner = ev.get("event", {})
                    if inner.get("type") == "content_block_delta":
                        delta = inner.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield f"data: {json.dumps({'text': text})}\n\n"
                elif ev.get("type") == "result" and ev.get("is_error"):
                    yield f"data: {json.dumps({'error': ev.get('result', 'Unknown error')})}\n\n"
            except json.JSONDecodeError:
                pass

        proc.wait()
        if proc.returncode not in (0, None):
            err = proc.stderr.read() if proc.stderr else ""
            if err:
                yield f"data: {json.dumps({'error': err[:300]})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
