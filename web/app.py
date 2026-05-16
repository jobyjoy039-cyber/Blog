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
# 11-Agent Pipeline
# ---------------------------------------------------------------------------

PIPELINE_STEPS = [
    {
        "step": 1, "id": "kw", "icon": "🔍", "agent": "Agent 1", "label": "Keyword Research",
        "description": "Identify 8–10 keywords, LSI terms, competitor gaps, and placement strategy.",
        "system_prompt": (
            "You are a Professional SEO Keyword Research Specialist.\n\n"
            "Output exactly these sections:\n\n"
            "## PRIMARY KEYWORDS\n"
            "| Keyword | Volume | Difficulty | Intent | Placement |\n"
            "|---------|--------|------------|--------|-----------||\n"
            "(8–10 rows. Estimate volume. Difficulty: Easy/Medium/Hard. "
            "Intent: Informational/Navigational/Transactional/Commercial. "
            "Placement: Title/H2/Body/Meta)\n\n"
            "## LSI & RELATED KEYWORDS\n"
            "(3–5 semantic terms)\n\n"
            "## COMPETITOR GAP ANALYSIS\n"
            "Content competitors have: ...\n"
            "Content MISSING from all competitors: ...\n"
            "Content opportunity: ...\n\n"
            "## KEYWORD PLACEMENT STRATEGY\n"
            "- Title: ...\n- H2s: ...\n- Meta Description: ...\n- Body: ..."
        ),
        "fields": [
            {"name": "topic",    "label": "Topic / Niche", "type": "text",
             "placeholder": "e.g. AI blog writing tools"},
            {"name": "audience", "label": "Target Audience", "type": "textarea", "rows": 2,
             "placeholder": "e.g. solo bloggers; pain point: can't rank; goal: organic traffic"},
            {"name": "goal",     "label": "Blog Goal", "type": "select",
             "options": [("SEO ranking","SEO ranking"),("Lead generation","Lead generation"),
                         ("Brand awareness","Brand awareness"),("Engagement","Engagement")]},
            {"name": "existing", "label": "Existing articles on this topic?", "type": "select",
             "options": [("No — discover from scratch","No — discover from scratch"),
                         ("Yes — build on existing","Yes — build on existing")]},
        ],
        "prompt": "Run keyword research.\n\nTopic: {topic}\nAudience: {audience}\nGoal: {goal}\nExisting content: {existing}",
        "output_key": "kw_output",
        "saves": ["topic", "audience", "goal"],
    },
    {
        "step": 2, "id": "brief", "icon": "📋", "agent": "Agent 2", "label": "Content Brief",
        "description": "Article angle, competitor analysis, H1→H2→H3 outline, key messages, assets, tone guide.",
        "system_prompt": (
            "You are a Professional Content Strategist & Editorial Director.\n\n"
            "Create a comprehensive content brief with these sections:\n\n"
            "## CONTENT BRIEF: [TOPIC]\n\n"
            "### Article Angle\nUnique perspective, hook, reason this article should exist.\n\n"
            "### Competitor Analysis\n3–5 similar articles: what they do well, what questions they miss, the content gap.\n\n"
            "### Content Outline\nDetailed H1 → H2 → H3 hierarchy with word counts per section "
            "and what type of content goes there (explanation/data/example/story).\n\n"
            "### Key Messages\n3–5 main takeaways the reader should remember.\n\n"
            "### Reader Profile\n- Expertise level\n- What brought them here\n- Desired outcome\n\n"
            "### Required Assets\nData/stats (with sources), examples, case studies, tools/resources.\n\n"
            "### Tone & Style Guide\nSentence length, jargon level, personal stories (yes/no), formatting."
        ),
        "fields": [
            {"name": "topic",    "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "keywords", "label": "Keywords (from Step 1)", "type": "textarea", "rows": 4,
             "placeholder": "Auto-filled from Step 1 output", "state_key": "kw_output"},
            {"name": "audience", "label": "Target Audience", "type": "textarea", "rows": 2,
             "placeholder": "Auto-filled from Step 1", "state_key": "audience"},
            {"name": "tone",     "label": "Tone", "type": "select",
             "options": [("Professional","Professional"),("Casual","Casual"),
                         ("Expert","Expert"),("Accessible","Accessible"),("Mixed","Mixed")]},
            {"name": "word_count","label": "Target Word Count", "type": "select",
             "options": [("1500","1,500"),("2000","2,000"),("2500","2,500"),("3500","3,500+")]},
        ],
        "prompt": "Create a content brief.\n\nTopic: {topic}\nKeywords: {keywords}\nAudience: {audience}\nTone: {tone}\nWord count: {word_count}",
        "output_key": "brief_output",
        "saves": [],
    },
    {
        "step": 3, "id": "write", "icon": "✍️", "agent": "Agent 3", "label": "AI-Proof First Draft",
        "description": "Write an authentic first draft — varied sentences, contractions, examples, no AI tells.",
        "system_prompt": (
            "You are an Expert Freelance Content Writer. Write a first draft that reads as genuinely human.\n\n"
            "Rules:\n"
            "1. AUTHENTICITY — use personal observations, stories, examples. Write like explaining to a friend.\n"
            "2. NATURAL VOICE — vary sentence length dramatically. Short. Punchy. Then longer winding sentences. Use contractions.\n"
            "3. HOOK — start with a question or relatable statement. Never 'In this article we will explore…'\n"
            "4. BANNED WORDS — never use: delve, tapestry, testament, crucial, leverage, utilize, seamlessly, "
            "robust, comprehensive, Moreover, Furthermore, In conclusion.\n"
            "5. EVIDENCE — include data/statistics from the brief, cite examples.\n\n"
            "Structure:\n"
            "- Hook opening (don't announce what you'll cover — just start)\n"
            "- Key Takeaways box near top (3–5 bullets)\n"
            "- At least 3 real examples or mini-stories per major section\n"
            "- Bold key takeaways inline\n"
            "- Strong conclusion that ties back to the intro\n"
            "- FAQ section with 3–5 real questions"
        ),
        "fields": [
            {"name": "topic",      "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "keywords",   "label": "Keywords", "type": "textarea", "rows": 3,
             "placeholder": "Auto-filled from Step 1", "state_key": "kw_output"},
            {"name": "brief",      "label": "Content Brief (from Step 2)", "type": "textarea", "rows": 6,
             "placeholder": "Auto-filled from Step 2 output", "state_key": "brief_output"},
            {"name": "expertise",  "label": "Author Expertise / POV", "type": "textarea", "rows": 2,
             "placeholder": "e.g. 8-year SEO consultant, ran 200+ content audits"},
            {"name": "word_count", "label": "Target Word Count", "type": "select",
             "options": [("1500","1,500"),("2000","2,000"),("2500","2,500"),("3500","3,500+")]},
        ],
        "prompt": "Write a human-sounding first draft.\n\nTopic: {topic}\nKeywords: {keywords}\nBrief: {brief}\nAuthor expertise: {expertise}\nTarget: {word_count} words",
        "output_key": "draft_v1",
        "saves": [],
    },
    {
        "step": 4, "id": "seo-opt", "icon": "⚡", "agent": "Agent 4", "label": "SEO Optimizer",
        "description": "Keyword integration, title/meta, CTAs, link suggestions, readability score.",
        "system_prompt": (
            "You are an Expert SEO Content Optimizer.\n\n"
            "1. TITLE — include primary keyword, under 60 chars, compelling\n"
            "2. META DESCRIPTION — 150–160 chars, primary keyword + benefit\n"
            "3. KEYWORD INTEGRATION — primary keyword in first paragraph, ≥2 H2s, body at 0.5–1.5% density. Natural only.\n"
            "4. STRUCTURE — descriptive H2s/H3s, paragraphs 2–3 sentences, bullet lists, bold key terms\n"
            "5. LINKS — suggest 3–5 internal links (anchor text + placement), 3–5 external authority links\n"
            "6. CTAs — 3 CTAs: after intro (soft), mid-content (value-driven), conclusion (main)\n"
            "7. READABILITY — Flesch 60+ target, active voice\n\n"
            "Output:\n## OPTIMIZED BLOG POST\n[Full optimized draft]\n\n"
            "### SEO METRICS\n- Title: [title] (X chars)\n- Meta: [meta] (X chars)\n"
            "- Keyword density: X%\n- Readability: ~X\n- CTAs: X\n\n"
            "### LINK SUGGESTIONS\nInternal: ...\nExternal: ..."
        ),
        "fields": [
            {"name": "draft",           "label": "Draft to Optimize (from Step 3)", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from Step 3 output", "state_key": "draft_v1"},
            {"name": "keywords",        "label": "All Target Keywords", "type": "textarea", "rows": 3,
             "placeholder": "Auto-filled from Step 1", "state_key": "kw_output"},
            {"name": "primary_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "e.g. content marketing strategy"},
        ],
        "prompt": "SEO-optimize this draft.\n\nPrimary Keyword: {primary_keyword}\nKeywords: {keywords}\n\n---\n{draft}",
        "output_key": "draft_seo",
        "saves": ["primary_keyword"],
    },
    {
        "step": 5, "id": "factcheck", "icon": "🔬", "agent": "Agent 5", "label": "Fact Check",
        "description": "Verify every factual claim, flag unsupported stats, check logical consistency.",
        "system_prompt": (
            "You are a Professional Fact-Checker & Content Auditor.\n\n"
            "1. IDENTIFY ALL FACTUAL CLAIMS — list every statement that is factual (not opinion)\n"
            "2. VERIFY ACCURACY — check dates, names, numbers; flag anything uncertain\n"
            "3. CHECK SOURCES — do claims have citations? Are sources credible and current?\n"
            "4. FLAG UNSUPPORTED CLAIMS — no source = flag it; suggest rewording as opinion if unverifiable\n"
            "5. LOGICAL CONSISTENCY — do claims contradict each other?\n"
            "6. RED FLAGS — 'Everyone agrees…', 'Studies show…', outdated stats, conflicting figures\n\n"
            "Output:\n## FACT-CHECK REPORT\n\n### VERIFIED CLAIMS ✓\n- [Claim] — Source: [URL or publication]\n\n"
            "### FLAGGED CLAIMS ⚠️\n- [Claim] — Issue: [what's wrong]\n  Fix: [how to verify or reword]\n\n"
            "### UNSUPPORTED CLAIMS ❌\n- [Claim] — Add [source] or reword as opinion\n\n"
            "### QUALITY ISSUES\n[Vague attributions, outdated info, logical gaps]\n\n"
            "### OVERALL ASSESSMENT + RECOMMENDATIONS"
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
        "step": 6, "id": "citations", "icon": "🔐", "agent": "Agent 6", "label": "Citations & AI Audit",
        "description": "Check attribution and detect AI patterns: em-dashes, rule of three, vague sourcing.",
        "system_prompt": (
            "You are an Expert Citations Auditor & AI Detection Specialist.\n\n"
            "1. CITATION AUDIT — are all quotes attributed? are all stats sourced? are sources credible?\n"
            "2. AI DETECTION CHECK — scan for:\n"
            "   ✗ Excessive em-dashes\n"
            "   ✗ Rule of three (lists of exactly 3 in every paragraph)\n"
            "   ✗ Vague attributions ('Research shows…', 'Studies indicate…')\n"
            "   ✗ Promotional language ('must understand', 'critical to know')\n"
            "   ✗ Repetitive transitions (Moreover, Furthermore used repeatedly)\n"
            "   ✗ Missing contractions\n"
            "   Rate AI risk: Low / Medium / High\n"
            "3. AUTHENTICITY SCORE — X/10, with breakdown\n"
            "4. SOURCE DIVERSITY — 5+ publications or relying on 1–2?\n\n"
            "Output:\n## CITATIONS & AI AUDIT REPORT\n\n"
            "### CITATION CHECKLIST\n✓/✗ ...\n\n### CITATIONS NEEDED\n1. ...\n\n"
            "### AI DETECTION RISK: [LOW/MEDIUM/HIGH]\nFactors found:\n- ...\n\n"
            "### AUTHENTICITY SCORE: X/10\n\n### RECOMMENDATIONS"
        ),
        "fields": [
            {"name": "draft", "label": "Draft to Audit", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_seo",
             "fallback_key": "draft_v1"},
        ],
        "prompt": "Run a citations and AI detection audit:\n\n---\n{draft}",
        "output_key": "citations_output",
        "saves": [],
    },
    {
        "step": 7, "id": "humanize", "icon": "🧬", "agent": "Agent 7", "label": "Content Humanizer",
        "description": "Remove AI patterns, add authentic voice, vary sentence structure, add contractions.",
        "system_prompt": (
            "You are a Content Humanization Specialist.\n\n"
            "REMOVE AI PATTERNS:\n"
            "1. Em-dashes (—) — replace with periods, commas, or restructure\n"
            "2. Rule of three — don't list exactly 3 things in every paragraph\n"
            "3. Vague attributions: 'Research shows…' → 'A 2024 study found…'; 'It's important to…' → 'You need to…'\n"
            "4. Promotional words: remove 'must', 'critical', 'essential', 'crucial', 'leverage', 'utilize'\n"
            "5. Repetitive transitions — vary how you move between ideas\n"
            "6. ADD contractions: it's, don't, I'm, we're, you'll, can't\n\n"
            "ADD AUTHENTIC ELEMENTS:\n"
            "1. Personal examples: 'When I…', 'I've seen…', 'I remember…'\n"
            "2. Conversational asides in parentheses\n"
            "3. Questions to reader: 'Have you…?', 'What if…?'\n"
            "4. Sentence variety:\n"
            "   - Short. Punchy.\n"
            "   - Medium length that flows with detail.\n"
            "   - Longer sentences that wind through a thought before landing somewhere.\n\n"
            "Output the full humanized text, then after --- separator:\n"
            "### CHANGES MADE:\n"
            "- Em-dashes removed: X\n- Contractions added: X\n"
            "- Vague attributions replaced: X\n- Personal examples added: X\n"
            "- Authenticity: X/10"
        ),
        "fields": [
            {"name": "draft",      "label": "Draft to Humanize", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_seo",
             "fallback_key": "draft_v1"},
            {"name": "intensity",  "label": "Intensity", "type": "select",
             "options": [("moderate","Moderate — restructure + vocab + voice (recommended)"),
                         ("light","Light — vocabulary swap + sentence variation only"),
                         ("heavy","Heavy — full rewrite, strong authorial voice")]},
        ],
        "prompt": "Humanize this content at intensity: {intensity}\n\n---\n{draft}",
        "output_key": "draft_humanized",
        "saves": [],
    },
    {
        "step": 8, "id": "headlines", "icon": "🧪", "agent": "Agent 8", "label": "A/B Headlines",
        "description": "5 headline variants (curiosity, benefit, SEO, how-to, contrarian) with CTR scores.",
        "system_prompt": (
            "You are an Expert Headline Writer & CTR Specialist. Create 5 headline variations.\n\n"
            "For each of these 5 types, write: the title (under 60 chars), a meta description (150–160 chars), "
            "2–3 sentences on why it works, CTR potential (Low/Medium/High), best audience segment.\n\n"
            "Types:\n"
            "1. CURIOSITY/HOOK — 'Why [Expected thing] Is [Unexpected thing]'\n"
            "2. BENEFIT-DRIVEN — 'How to [Get Benefit] in [Timeframe]'\n"
            "3. SEO-OPTIMIZED — '[Keyword]: [Benefit]'\n"
            "4. HOW-TO — 'How to [Accomplish Goal] in X Steps'\n"
            "5. CONTRARIAN — 'Why [Common Belief] Is Actually [Opposite]'\n\n"
            "Then:\n### RANKING & RECOMMENDATION\n"
            "[Rank all 5 highest to lowest CTR]\n"
            "**My Recommendation:** Option X because [reason]\n\n"
            "### A/B TESTING STRATEGY\n"
            "- Test Option 1 vs Option 2 first — run 14 days — measure CTR"
        ),
        "fields": [
            {"name": "topic",    "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "article",  "label": "Article (for context)", "type": "textarea", "rows": 5,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_humanized",
             "fallback_key": "draft_seo"},
            {"name": "audience", "label": "Audience", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "audience"},
            {"name": "goal",     "label": "Goal", "type": "select",
             "options": [("SEO / Clicks","SEO / Clicks"),("Leads","Lead generation"),
                         ("Engagement","Engagement / Shares"),("Brand awareness","Brand awareness")]},
        ],
        "prompt": "Create 5 A/B headline variants.\n\nTopic: {topic}\nAudience: {audience}\nGoal: {goal}\n\nArticle:\n---\n{article}",
        "output_key": "headlines_output",
        "saves": [],
    },
    {
        "step": 9, "id": "polish", "icon": "✨", "agent": "Agent 9", "label": "Polish & Finalize",
        "description": "Stronger verbs, smooth transitions, pacing, tone consistency, choose best headline.",
        "system_prompt": (
            "You are a Professional Editor & Content Optimizer.\n\n"
            "1. POLISH SENTENCES — strong action verbs, no redundancy, active voice\n"
            "2. FIX TRANSITIONS — smooth paragraph flow, remove abrupt jumps\n"
            "3. PARAGRAPH PACING — alternate short/long, max 5 sentences per paragraph\n"
            "4. POWER WORDS — 'craft/build/create' not 'make'; 'guide/enable' not 'help'; 'gain/unlock' not 'get'\n"
            "5. TONE CONSISTENCY — no jarring formality shifts\n"
            "6. READABILITY — Flesch 70+ target\n"
            "7. SELECT BEST HEADLINE — compare all 5 headline options, choose highest-CTR one that matches content\n\n"
            "Output:\n## POLISHED FINAL DRAFT\n\n"
            "### SELECTED HEADLINE\n**Headline:** ...\n**Meta Description:** ...\n**Why This One:** ...\n\n"
            "### FINAL ARTICLE\n[Complete polished text]\n\n"
            "### POLISH CHANGES MADE\n"
            "- Weak verbs improved: X\n- Passive voice converted: X\n"
            "- Transitions improved: X\n- Readability: ~X\n- Word count: X"
        ),
        "fields": [
            {"name": "draft",      "label": "Draft to Polish", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from latest draft", "state_key": "draft_humanized",
             "fallback_key": "draft_seo"},
            {"name": "headlines",  "label": "Headline Options (from Step 8)", "type": "textarea", "rows": 5,
             "placeholder": "Auto-filled from Step 8 output", "state_key": "headlines_output"},
            {"name": "word_count", "label": "Target Word Count", "type": "select",
             "options": [("1500","1,500"),("2000","2,000"),("2500","2,500"),("3500","3,500+")]},
        ],
        "prompt": "Polish to final publication quality.\n\nTarget: {word_count} words\nHeadlines:\n{headlines}\n\n---\n{draft}",
        "output_key": "final_draft",
        "saves": [],
    },
    {
        "step": 10, "id": "seo-check", "icon": "✅", "agent": "Agent 10", "label": "SEO Check",
        "description": "Full technical SEO checklist: title, meta, headings, density, links, readability, CTAs.",
        "system_prompt": (
            "You are an SEO Technical Auditor. Run a complete SEO checklist. Mark each ✓ Pass or ⚠️ Fix.\n\n"
            "Check: title (50–60 chars, keyword present), meta (150–160 chars), "
            "H1/H2/H3 hierarchy, keyword density (0.5–1.5%), keyword in first 100 words, "
            "keyword in ≥2 H2s, readability (Flesch 60+), short paragraphs (2–4 sentences), "
            "contractions present, active voice dominant, internal links (3–5), "
            "external links (2–3), descriptive anchor text, CTAs (≥1), images have alt text.\n\n"
            "Output:\n## FINAL SEO SCORECARD\n"
            "| Item | Status | Action |\n|------|--------|--------|\n[rows for each item]\n\n"
            "## OVERALL STATUS: [✓ READY TO PUBLISH / ⚠️ FIX THESE ITEMS / ❌ NEEDS MAJOR REVISIONS]\n\n"
            "## PRIORITY FIXES\n1. [Issue] — Fix: [how]\n\n"
            "## SUGGESTED URL SLUG\n/[keyword]-[keyword]/"
        ),
        "fields": [
            {"name": "article",         "label": "Final Article", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from Step 9 output", "state_key": "final_draft",
             "fallback_key": "draft_humanized"},
            {"name": "primary_keyword", "label": "Primary Keyword", "type": "text",
             "placeholder": "Auto-filled from Step 4", "state_key": "primary_keyword"},
            {"name": "headline",        "label": "Chosen Headline", "type": "text",
             "placeholder": "Paste selected headline from Step 9"},
        ],
        "prompt": "Full SEO check.\n\nPrimary Keyword: {primary_keyword}\nHeadline: {headline}\n\n---\n{article}",
        "output_key": "seo_report",
        "saves": [],
    },
    {
        "step": 11, "id": "decay", "icon": "📉", "agent": "Agent 11", "label": "Decay Detector",
        "description": "Flag time-sensitive claims, score evergreen potential, plan refresh timeline.",
        "system_prompt": (
            "You are a Content Decay & Freshness Analyst.\n\n"
            "1. TIME-SENSITIVE CLAIMS — statements tied to years/dates, 'current' trends, "
            "statistics with dates, product versions, 'latest' references\n"
            "2. OUTDATED-RISK SECTIONS — tools, market analysis, evolving best practices\n"
            "3. EVERGREEN SCORE — rate 1–10 (1=outdated in 3 months, 10=timeless). Explain what pulls it down.\n"
            "4. REFRESH TIMELINE — 30/60/90 days / 6 months / 12 months?\n"
            "5. UPDATE-PRONE SECTIONS — which parts will need updating first?\n"
            "6. REFRESH STRATEGY — how to stay fresh without major rewrites?\n\n"
            "Output:\n## CONTENT DECAY ANALYSIS\n\n### EVERGREEN SCORE: X/10\nWhy: ...\n\n"
            "### TIME-SENSITIVE CLAIMS\n1. [Claim] — Risk: High/Medium/Low — Ages: [when] — Fix: [how]\n\n"
            "### OUTDATED-RISK SECTIONS\n- [Section] — Risk: [what changes]\n\n"
            "### REFRESH TIMELINE\n- First review: X days\n- Full audit: X days\n\n"
            "### MONITORING CHECKLIST\n- [Metric] — Check when: [condition]\n\n"
            "### REFRESH STRATEGY + LONGEVITY SUMMARY"
        ),
        "fields": [
            {"name": "article",       "label": "Final Article", "type": "textarea", "rows": 10,
             "placeholder": "Auto-filled from Step 9 output", "state_key": "final_draft",
             "fallback_key": "draft_humanized"},
            {"name": "topic",         "label": "Topic", "type": "text",
             "placeholder": "Auto-filled from Step 1", "state_key": "topic"},
            {"name": "current_date",  "label": "Current Date", "type": "text",
             "placeholder": "2026-05-16"},
        ],
        "prompt": "Analyze content decay.\n\nTopic: {topic}\nCurrent date: {current_date}\n\n---\n{article}",
        "output_key": "decay_report",
        "saves": [],
    },
]


def _build_pipeline_page():
    """Render the 11-agent pipeline page HTML."""

    # Sidebar nav
    nav_items = ""
    for s in PIPELINE_STEPS:
        n = s["step"]
        nav_items += (
            f'<div class="p-nav-item" id="p-nav-{n}" data-step="{n}" onclick="showStep({n})">'
            f'<span class="p-nav-num" id="p-nav-num-{n}">{n}</span>'
            f'<div class="p-nav-info"><div class="p-nav-label">{s["icon"]} {s["label"]}</div>'
            f'<div class="p-nav-agent">{s["agent"]}</div></div>'
            f'<span class="p-nav-check" id="p-nav-check-{n}"></span></div>'
        )

    # Step panels
    panels = ""
    for s in PIPELINE_STEPS:
        n = s["step"]
        next_s = PIPELINE_STEPS[n] if n < 11 else None
        next_label = f'Next: {next_s["label"]} →' if next_s else "🎉 Pipeline Complete!"

        # Build form fields
        fhtml = ""
        for f in s["fields"]:
            label   = f["label"]
            fname   = f["name"]
            req     = f.get("required", True)
            sk      = f.get("state_key", "")
            fk      = f.get("fallback_key", "")
            da      = (f' data-state-key="{sk}"' if sk else "") + (f' data-fallback-key="{fk}"' if fk else "")
            badge   = ' <span class="auto-badge">auto</span>' if sk else ""

            if f["type"] == "text":
                fhtml += (
                    f'<div class="form-group"><label class="field-label">{label}{badge}</label>'
                    f'<input type="text" name="{fname}" placeholder="{f.get("placeholder","")}"'
                    f'{da}{" required" if req else ""}></div>'
                )
            elif f["type"] == "textarea":
                rows = f.get("rows", 5)
                fhtml += (
                    f'<div class="form-group"><label class="field-label">{label}{badge}</label>'
                    f'<textarea name="{fname}" rows="{rows}" placeholder="{f.get("placeholder","")}"'
                    f'{da}{" required" if req else ""}></textarea></div>'
                )
            elif f["type"] == "select":
                opts = "".join(f'<option value="{v}">{l}</option>' for v, l in f["options"])
                fhtml += (
                    f'<div class="form-group"><label class="field-label">{label}</label>'
                    f'<select name="{fname}">{opts}</select></div>'
                )

        panels += f"""
<div class="p-step" id="p-step-{n}" data-step="{n}">
  <div class="p-step-header">
    <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0">
      <span class="p-agent-badge">{s["agent"]}</span>
      <span style="font-size:18px">{s["icon"]}</span>
      <div style="min-width:0">
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
                onclick="dlStep({n},'{s["id"]}')">⬇ Save</button>
      </div>
      <div class="output-box empty" id="p-out-{n}">
        <span>Run {s["agent"]} to see output here</span>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-primary btn-sm" id="p-next-{n}" style="display:none"
                onclick="nextStep({n})">{next_label}</button>
      </div>
    </div>
  </div>
</div>"""

    css_pipeline = """
.pipeline-layout{display:grid;grid-template-columns:260px 1fr;height:calc(100vh - 50px);overflow:hidden}
.pipeline-sidebar{background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.pipeline-sidebar-header{padding:14px;border-bottom:1px solid var(--border)}
.p-nav{flex:1;overflow-y:auto;padding:8px 0}
.p-nav-item{display:flex;align-items:center;gap:10px;padding:9px 14px;cursor:pointer;transition:background .12s;border-left:2px solid transparent}
.p-nav-item:hover{background:var(--surface2)}
.p-nav-item.active{background:rgba(88,166,255,.1);border-left-color:var(--accent)}
.p-nav-item.done{border-left-color:var(--green)}
.p-nav-num{width:22px;height:22px;border-radius:50%;background:var(--surface2);border:1px solid var(--border);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--muted)}
.p-nav-item.active .p-nav-num{background:var(--accent);color:#0d1117;border-color:var(--accent)}
.p-nav-item.done .p-nav-num{background:var(--green);color:#0d1117;border-color:var(--green)}
.p-nav-info{flex:1;min-width:0}
.p-nav-label{font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.p-nav-agent{font-size:10px;color:var(--muted)}
.p-nav-check{font-size:11px;color:var(--green)}
.pipeline-main{overflow-y:auto;background:var(--bg)}
.p-step{display:none;padding:20px;max-width:1100px;margin:0 auto}
.p-step.active{display:block}
.p-step-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border)}
.p-agent-badge{background:rgba(88,166,255,.15);color:var(--accent);border:1px solid rgba(88,166,255,.3);border-radius:12px;padding:2px 10px;font-size:11px;font-weight:700;flex-shrink:0}
.p-step-title{font-size:15px;font-weight:700}
.p-step-desc{font-size:12px;color:var(--muted);margin-top:2px}
.p-step-body{display:grid;grid-template-columns:340px 1fr;gap:16px;align-items:start}
.p-form-col{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px}
.p-output-col{display:flex;flex-direction:column}
.p-run-status{font-size:12px;color:var(--muted)}
.auto-badge{background:rgba(88,166,255,.12);color:var(--accent);border-radius:8px;padding:1px 6px;font-size:9px;font-weight:700;vertical-align:middle}
.pipeline-sidebar-footer{padding:12px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:6px}
@media(max-width:900px){.pipeline-layout{grid-template-columns:1fr;height:auto}.pipeline-sidebar{height:auto}.p-step-body{grid-template-columns:1fr}}
"""

    js_pipeline = r"""
const PS_KEY = 'cblog_pipeline';
function psGet(){ try{return JSON.parse(sessionStorage.getItem(PS_KEY)||'{}')}catch(e){return{}} }
function psSave(k,v){ const s=psGet(); s[k]=v; sessionStorage.setItem(PS_KEY,JSON.stringify(s)); }
function psGetVal(k,fb){ const s=psGet(); return s[k]||(fb?s[fb]:'')||''; }

function showStep(n){
  document.querySelectorAll('.p-step').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.p-nav-item').forEach(el=>el.classList.remove('active'));
  const panel=document.getElementById('p-step-'+n);
  const nav=document.getElementById('p-nav-'+n);
  if(panel) panel.classList.add('active');
  if(nav) nav.classList.add('active');
  populateStep(n);
  window._pStep=n;
}

function populateStep(n){
  const panel=document.getElementById('p-step-'+n);
  if(!panel) return;
  panel.querySelectorAll('[data-state-key]').forEach(el=>{
    if(el.value) return;
    const val=psGetVal(el.dataset.stateKey, el.dataset.fallbackKey);
    if(val) el.value=val;
  });
  // auto-fill current date for step 11
  const dateEl=panel.querySelector('input[name="current_date"]');
  if(dateEl && !dateEl.value) dateEl.value=new Date().toISOString().slice(0,10);
}

async function runPipelineStep(n){
  const form=document.getElementById('p-form-'+n);
  const outEl=document.getElementById('p-out-'+n);
  const statusEl=document.getElementById('p-status-'+n);
  const runBtn=document.getElementById('p-run-btn-'+n);
  const spinEl=document.getElementById('p-spin-'+n);

  const fields={};
  new FormData(form).forEach((v,k)=>fields[k]=v);

  // Save "saves" fields to state
  form.querySelectorAll('[data-save-key]').forEach(el=>psSave(el.dataset.saveKey, el.value));

  outEl.innerHTML=''; outEl.classList.remove('empty');
  runBtn.disabled=true;
  if(spinEl) spinEl.style.display='inline-flex';
  statusEl.textContent='Waiting for Claude…';
  document.getElementById('p-copy-'+n).style.display='none';
  document.getElementById('p-dl-'+n).style.display='none';
  document.getElementById('p-next-'+n).style.display='none';

  let fullText='';
  const cursor=document.createElement('span'); cursor.className='cursor';

  try{
    const resp=await fetch('/api/pipeline-run',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({step:n, fields})
    });
    if(!resp.ok){
      const err=await resp.json().catch(()=>({error:resp.statusText}));
      statusEl.textContent='✗ '+(err.error||'Error');
      outEl.innerHTML='<span style="color:var(--red)">'+(err.error||'Request failed')+'</span>';
      runBtn.disabled=false; if(spinEl) spinEl.style.display='none';
      return;
    }
    const reader=resp.body.getReader(); const dec=new TextDecoder();
    outEl.appendChild(cursor);
    while(true){
      const {done,value}=await reader.read(); if(done) break;
      dec.decode(value,{stream:true}).split('\n').forEach(line=>{
        if(!line.startsWith('data: ')) return;
        const pl=line.slice(6).trim(); if(pl==='[DONE]') return;
        try{
          const d=JSON.parse(pl);
          if(d.text){ fullText+=d.text; cursor.remove(); outEl.innerHTML=renderMd(fullText); outEl.appendChild(cursor); outEl.scrollTop=outEl.scrollHeight; statusEl.textContent='Streaming…'; }
          if(d.error){ statusEl.textContent='✗ '+d.error; outEl.innerHTML='<span style="color:var(--red)">'+d.error+'</span>'; }
        }catch(e){}
      });
    }
    cursor.remove();
    const words=fullText.trim().split(/\s+/).length;
    statusEl.textContent='✓ Done · '+words+' words';
    runBtn.disabled=false; if(spinEl) spinEl.style.display='none';

    // Save output to pipeline state
    window['_pOut'+n]=fullText;
    // We'll save the output key via data attribute on the panel
    const panel=document.getElementById('p-step-'+n);
    const outKey=panel ? panel.dataset.outputKey : null;
    if(outKey) psSave(outKey, fullText);

    document.getElementById('p-copy-'+n).style.display='inline-flex';
    document.getElementById('p-dl-'+n).style.display='inline-flex';
    document.getElementById('p-next-'+n).style.display='inline-flex';

    // Mark step done in sidebar
    const navItem=document.getElementById('p-nav-'+n);
    if(navItem){ navItem.classList.add('done'); }
    const navCheck=document.getElementById('p-nav-check-'+n);
    if(navCheck) navCheck.textContent='✓';

    // Enable download-all if all key outputs exist
    checkDownloadAll();
  }catch(e){
    cursor.remove(); statusEl.textContent='✗ '+e.message;
    runBtn.disabled=false; if(spinEl) spinEl.style.display='none';
  }
}

function nextStep(n){
  if(n<11) showStep(n+1);
}

function copyStepOutput(n){
  const text=window['_pOut'+n]||'';
  if(!text) return;
  const btn=document.getElementById('p-copy-'+n);
  function ok(){ if(btn){btn.textContent='✓';setTimeout(()=>btn.textContent='⎘ Copy',1500);} }
  function fb(){ const el=document.createElement('textarea'); el.value=text; el.style.cssText='position:fixed;opacity:0;top:0;left:0;width:1px;height:1px'; document.body.appendChild(el); el.focus(); el.select(); try{document.execCommand('copy');ok();}catch(e){} document.body.removeChild(el); }
  if(navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(ok).catch(fb); else fb();
}

function dlStep(n, id){
  const text=window['_pOut'+n]||'';
  if(!text) return;
  const a=document.createElement('a');
  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(text);
  a.download='step'+n+'-'+id+'.md'; a.click();
}

function checkDownloadAll(){
  const state=psGet();
  const hasAny=Object.keys(state).some(k=>k.endsWith('_output')||k==='draft_v1'||k==='final_draft');
  const btn=document.getElementById('p-dl-all');
  if(btn) btn.disabled=!hasAny;
}

function downloadAll(){
  const state=psGet();
  const keys=['kw_output','brief_output','draft_v1','draft_seo','factcheck_output',
               'citations_output','draft_humanized','headlines_output','final_draft',
               'seo_report','decay_report'];
  const labels=['Agent 1 — Keyword Research','Agent 2 — Content Brief','Agent 3 — First Draft',
                 'Agent 4 — SEO Optimized','Agent 5 — Fact Check','Agent 6 — Citations & AI Audit',
                 'Agent 7 — Humanized','Agent 8 — Headlines','Agent 9 — Polished Final',
                 'Agent 10 — SEO Check','Agent 11 — Decay Report'];
  let md='# Blog Pipeline — All Outputs\n\n';
  keys.forEach((k,i)=>{ if(state[k]) md+=`---\n\n## ${labels[i]}\n\n${state[k]}\n\n`; });
  const a=document.createElement('a');
  a.href='data:text/markdown;charset=utf-8,'+encodeURIComponent(md);
  a.download='blog-pipeline-outputs.md'; a.click();
}

function resetPipeline(){
  if(!confirm('Reset pipeline? All step outputs will be cleared.')) return;
  sessionStorage.removeItem(PS_KEY);
  for(let n=1;n<=11;n++){
    window['_pOut'+n]=null;
    const nav=document.getElementById('p-nav-'+n);
    if(nav){ nav.classList.remove('done'); }
    const check=document.getElementById('p-nav-check-'+n);
    if(check) check.textContent='';
    const out=document.getElementById('p-out-'+n);
    if(out){ out.className='output-box empty'; out.innerHTML='<span>Run Agent '+n+' to see output here</span>'; }
    const st=document.getElementById('p-status-'+n);
    if(st) st.textContent='';
    ['p-copy-','p-dl-','p-next-'].forEach(p=>{ const el=document.getElementById(p+n); if(el) el.style.display='none'; });
  }
  showStep(1);
}

// Init
document.addEventListener('DOMContentLoaded',()=>{ showStep(1); checkDownloadAll(); });
"""

    # Attach output_key as data attribute on each panel
    panels = panels.replace(
        '<div class="p-step" id="p-step-',
        '<div class="p-step" id="p-step-'
    )
    for s in PIPELINE_STEPS:
        n = s["step"]
        panels = panels.replace(
            f'<div class="p-step" id="p-step-{n}" data-step="{n}">',
            f'<div class="p-step" id="p-step-{n}" data-step="{n}" data-output-key="{s["output_key"]}">'
        )
        # Add data-save-key to "saves" fields
        for fname in s.get("saves", []):
            panels = panels.replace(
                f'name="{fname}"',
                f'name="{fname}" data-save-key="{fname}"',
                1  # replace only the first occurrence in this panel
            )

    body = f"""
<style>{css_pipeline}</style>
<div class="pipeline-layout">
  <div class="pipeline-sidebar">
    <div class="pipeline-sidebar-header">
      <a href="/" class="btn btn-ghost btn-sm" style="margin-bottom:10px;display:inline-flex">← Home</a>
      <div style="font-weight:700;font-size:13px">📋 11-Agent Pipeline</div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px">Sequential blog creation workflow</div>
    </div>
    <div class="p-nav">{nav_items}</div>
    <div class="pipeline-sidebar-footer">
      <button class="btn btn-ghost btn-sm" onclick="resetPipeline()" style="width:100%;justify-content:center">↺ Reset</button>
      <button class="btn btn-secondary btn-sm" id="p-dl-all" onclick="downloadAll()" disabled
              style="width:100%;justify-content:center">⬇ Download All Outputs</button>
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
<title>11-Agent Pipeline — Claude Blog</title>
<style>{CSS}</style>
</head>
<body>
<nav>
  <div class="nav-brand">✍ Claude<em>Blog</em></div>
  <a href="/" class="nav-link">Home</a>
  <a href="/pipeline" class="nav-link active" style="color:var(--accent);font-weight:600">⚡ Pipeline</a>
  <a href="/run/keyword-research" class="nav-link">Keywords</a>
  <a href="/run/write" class="nav-link">Write</a>
  <a href="/run/humanize" class="nav-link">Humanize</a>
  <a href="/run/ai-proof" class="nav-link">AI-Proof</a>
  <a href="/saved" class="nav-link">Saved</a>
  <a href="/settings" class="nav-link">Settings</a>
  <div class="nav-spacer"></div>
  <div class="status-pill {'ok' if claude_available() else ''}" title="Claude subscription auth">
    <span class="dot"></span>{'Claude connected' if claude_available() else 'claude CLI not found'}
  </div>
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
