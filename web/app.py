#!/usr/bin/env python3
"""
Claude Blog — Browser UI
Run: python3 web/app.py
Then open: http://localhost:5000
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
from flask import Flask, jsonify, redirect, render_template_string, request, send_file, url_for

ROOT = Path(__file__).parent.parent
KEYWORD_DIR = ROOT / "keyword-research"
PERFORMANCE_DIR = ROOT / "performance"
CLUSTER_MAP = ROOT / "skills" / "blog-cluster" / "templates" / "cluster-map.html"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CSS (shared across all pages, no external CDN)
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --muted: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --yellow: #d29922;
  --red: #f85149;
  --purple: #bc8cff;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
  font-size: 14px;
  line-height: 1.6;
  min-height: 100vh;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ---- nav ---- */
nav {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 0;
  height: 52px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
  margin-right: 32px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-brand span { color: var(--accent); }

nav a {
  color: var(--muted);
  padding: 0 14px;
  height: 52px;
  display: flex;
  align-items: center;
  font-size: 13px;
  border-bottom: 2px solid transparent;
  transition: color .15s, border-color .15s;
}

nav a:hover { color: var(--text); text-decoration: none; }
nav a.active { color: var(--text); border-bottom-color: var(--accent); }

/* ---- layout ---- */
.page { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--text); }
h3 { font-size: 14px; font-weight: 600; color: var(--text); }

.subtitle { color: var(--muted); font-size: 13px; margin-bottom: 28px; }

/* ---- cards ---- */
.grid { display: grid; gap: 16px; margin-bottom: 32px; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-2 { grid-template-columns: repeat(2, 1fr); }

@media (max-width: 720px) {
  .grid-3, .grid-2 { grid-template-columns: 1fr; }
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}

.card-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--accent);
  display: block;
  margin-bottom: 4px;
}

.card-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }

/* ---- stat badge ---- */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}
.badge-blue { background: rgba(88,166,255,.15); color: var(--accent); }
.badge-green { background: rgba(63,185,80,.15); color: var(--green); }
.badge-yellow { background: rgba(210,153,34,.15); color: var(--yellow); }
.badge-red { background: rgba(248,81,73,.15); color: var(--red); }
.badge-purple { background: rgba(188,140,255,.15); color: var(--purple); }

/* ---- report list ---- */
.report-list { list-style: none; }
.report-list li {
  border-bottom: 1px solid var(--border);
}
.report-list li:last-child { border-bottom: none; }

.report-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  color: var(--text);
  transition: color .1s;
}
.report-item:hover { color: var(--accent); text-decoration: none; }
.report-item .icon { color: var(--muted); font-size: 16px; flex-shrink: 0; }
.report-item .meta { color: var(--muted); font-size: 12px; margin-left: auto; white-space: nowrap; }

/* ---- buttons ---- */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all .15s;
  text-decoration: none;
}

.btn-primary { background: var(--accent); color: #0d1117; border-color: var(--accent); }
.btn-primary:hover { background: #79c0ff; text-decoration: none; }

.btn-secondary {
  background: transparent;
  color: var(--text);
  border-color: var(--border);
}
.btn-secondary:hover { background: var(--border); text-decoration: none; color: var(--text); }

.btn-ghost { background: transparent; color: var(--muted); border-color: transparent; }
.btn-ghost:hover { color: var(--text); background: var(--border); text-decoration: none; }

/* ---- forms ---- */
.form-group { margin-bottom: 16px; }
label { display: block; font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }

input[type=text], input[type=file], select, textarea {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: border-color .15s;
}
input[type=text]:focus, select:focus, textarea:focus { border-color: var(--accent); }
textarea { resize: vertical; min-height: 160px; }

/* ---- markdown render ---- */
.md-body { max-width: 800px; }

.md-body h1 { font-size: 20px; margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.md-body h2 { font-size: 17px; margin: 22px 0 10px; }
.md-body h3 { font-size: 15px; margin: 18px 0 8px; }
.md-body h4 { font-size: 13px; margin: 14px 0 6px; }
.md-body p { margin-bottom: 12px; }
.md-body ul, .md-body ol { margin: 8px 0 12px 24px; }
.md-body li { margin-bottom: 4px; }
.md-body code { background: rgba(110,118,129,.15); padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; }
.md-body pre { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px; overflow-x: auto; margin: 12px 0; }
.md-body pre code { background: none; padding: 0; }
.md-body table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
.md-body th { background: var(--surface); border: 1px solid var(--border); padding: 8px 12px; text-align: left; font-weight: 600; }
.md-body td { border: 1px solid var(--border); padding: 8px 12px; }
.md-body tr:nth-child(even) td { background: rgba(22,27,34,.5); }
.md-body blockquote { border-left: 3px solid var(--border); padding-left: 16px; color: var(--muted); margin: 12px 0; }
.md-body hr { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
.md-body strong { font-weight: 600; }

/* ---- score display ---- */
.score-bar-wrap { background: var(--border); border-radius: 4px; height: 6px; margin: 6px 0 2px; }
.score-bar { height: 6px; border-radius: 4px; transition: width .4s; }

.score-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }

.score-item { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
.score-item .name { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .4px; }
.score-item .value { font-size: 24px; font-weight: 700; margin: 4px 0 2px; }

/* ---- tabs ---- */
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
.tab { padding: 10px 16px; border-radius: 6px 6px 0 0; font-size: 13px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; background: none; border-top: none; border-left: none; border-right: none; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--text); border-bottom-color: var(--accent); }

/* ---- section header ---- */
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }

/* ---- alerts ---- */
.alert { border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; }
.alert-info { background: rgba(88,166,255,.1); border: 1px solid rgba(88,166,255,.3); color: var(--accent); }
.alert-success { background: rgba(63,185,80,.1); border: 1px solid rgba(63,185,80,.3); color: var(--green); }
.alert-warn { background: rgba(210,153,34,.1); border: 1px solid rgba(210,153,34,.3); color: var(--yellow); }

/* ---- command chip ---- */
.cmd-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 14px;
  font-family: monospace;
  font-size: 12px;
  color: var(--muted);
  margin: 4px 4px 4px 0;
}
.cmd-chip .cmd-action { color: var(--accent); font-weight: 600; }

/* ---- spinner ---- */
.spinner { display: none; width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.loading .spinner { display: inline-block; }
.loading .btn-label { display: none; }
"""

# ---------------------------------------------------------------------------
# Shared base template
# ---------------------------------------------------------------------------

BASE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} — Claude Blog</title>
<style>{{ css }}</style>
</head>
<body>
<nav>
  <div class="nav-brand">&#9997; Claude<span>Blog</span></div>
  <a href="/" class="{{ 'active' if active=='dashboard' else '' }}">Dashboard</a>
  <a href="/keywords" class="{{ 'active' if active=='keywords' else '' }}">Keywords</a>
  <a href="/analyze" class="{{ 'active' if active=='analyze' else '' }}">Analyzer</a>
  <a href="/reports" class="{{ 'active' if active=='reports' else '' }}">Reports</a>
  <a href="/cluster-map" class="{{ 'active' if active=='cluster' else '' }}">Cluster Map</a>
</nav>
<div class="page">
  {% block content %}{% endblock %}
</div>
<script>{{ js }}</script>
</body>
</html>"""

JS = """
function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    const el = document.getElementById('copy-toast');
    if (el) { el.style.opacity = 1; setTimeout(() => el.style.opacity = 0, 1800); }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // Tab switching
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      const group = t.closest('.tab-group');
      group.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      const target = t.dataset.target;
      document.querySelectorAll('.tab-panel').forEach(p => {
        p.style.display = p.id === target ? '' : 'none';
      });
    });
  });

  // Auto-submit search on Enter
  const search = document.getElementById('topic-search');
  if (search) {
    search.addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('search-form').submit();
    });
  }
});
"""


def render(template_str, **kwargs):
    from flask import render_template_string as rts
    return rts(
        BASE_HTML.replace("{% block content %}{% endblock %}", "{% block content %}" + template_str + "{% endblock %}"),
        css=CSS, js=JS, **kwargs
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_reports(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    reports = []
    for f in sorted(directory.glob("*.md"), reverse=True):
        stat = f.stat()
        size_kb = round(stat.st_size / 1024, 1)
        reports.append({"name": f.stem, "path": str(f), "size_kb": size_kb, "filename": f.name})
    return reports


def render_md(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
        output_format="html"
    )


def score_color(score: float) -> str:
    if score >= 80:
        return "#3fb950"
    if score >= 60:
        return "#58a6ff"
    if score >= 40:
        return "#d29922"
    return "#f85149"


def score_badge(score: float) -> str:
    if score >= 80:
        return "badge-green"
    if score >= 60:
        return "badge-blue"
    if score >= 40:
        return "badge-yellow"
    return "badge-red"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    kw_reports = list_reports(KEYWORD_DIR)
    perf_reports = list_reports(PERFORMANCE_DIR)

    # Count blog posts in common locations
    post_dirs = [ROOT / "posts", ROOT / "content", ROOT / "blog"]
    post_count = sum(len(list(d.glob("**/*.md"))) for d in post_dirs if d.exists())

    tmpl = """
<h1>Dashboard</h1>
<p class="subtitle">Claude Blog v1.9.0 — Blog creation and optimization suite</p>

<div class="grid grid-3">
  <div class="card">
    <span class="card-number">{{ kw_count }}</span>
    <div class="card-label">Keyword Reports</div>
  </div>
  <div class="card">
    <span class="card-number">{{ perf_count }}</span>
    <div class="card-label">Performance Reports</div>
  </div>
  <div class="card">
    <span class="card-number">{{ post_count }}</span>
    <div class="card-label">Blog Posts Tracked</div>
  </div>
</div>

<div class="grid grid-2">

  <div class="card">
    <div class="section-header">
      <h2>Recent Keyword Research</h2>
      <a href="/keywords" class="btn btn-ghost" style="font-size:12px">View all →</a>
    </div>
    {% if kw_reports %}
    <ul class="report-list">
      {% for r in kw_reports[:5] %}
      <li>
        <a class="report-item" href="/keywords/{{ r.name }}">
          <span class="icon">&#128269;</span>
          <span>{{ r.name | replace('-', ' ') | title }}</span>
          <span class="meta">{{ r.size_kb }} KB</span>
        </a>
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <p style="color:var(--muted)">No keyword reports yet.</p>
    {% endif %}
  </div>

  <div class="card">
    <h2>Quick Actions</h2>
    <div style="display:flex;flex-direction:column;gap:10px">
      <a href="/keywords" class="btn btn-primary">&#128269; Browse Keyword Reports</a>
      <a href="/analyze" class="btn btn-secondary">&#128200; Analyze a Blog Post</a>
      <a href="/cluster-map" class="btn btn-secondary">&#127760; View Cluster Map</a>
      <a href="/keywords/new" class="btn btn-secondary">&#43; Run New Keyword Research</a>
    </div>
  </div>

</div>

<div class="card">
  <h2>Available /blog Commands</h2>
  <div style="display:flex;flex-wrap:wrap;gap:0">
    {% for cmd in commands %}
    <div class="cmd-chip"><span class="cmd-action">/blog</span> {{ cmd }}</div>
    {% endfor %}
  </div>
  <p style="color:var(--muted);font-size:12px;margin-top:12px">
    Run any command via Claude Code CLI: <code>/blog [command] [topic or file]</code>
  </p>
</div>
"""
    commands = [
        "write", "rewrite", "analyze", "brief", "outline", "calendar",
        "strategy", "seo-check", "schema", "chart", "repurpose", "geo",
        "image", "audit", "factcheck", "persona", "taxonomy", "keyword-research",
        "cluster", "multilingual", "translate", "localize", "flow",
    ]
    return render(tmpl,
                  title="Dashboard",
                  active="dashboard",
                  kw_count=len(kw_reports),
                  perf_count=len(perf_reports),
                  post_count=post_count,
                  kw_reports=kw_reports,
                  commands=commands)


@app.route("/keywords")
def keywords_list():
    reports = list_reports(KEYWORD_DIR)
    tmpl = """
<div class="section-header">
  <div>
    <h1>Keyword Research Reports</h1>
    <p class="subtitle">Live SERP-analyzed keyword maps generated by the blog-keyword-research skill</p>
  </div>
  <a href="/keywords/new" class="btn btn-primary">&#43; New Research</a>
</div>

{% if reports %}
<div class="card">
  <ul class="report-list">
    {% for r in reports %}
    <li>
      <a class="report-item" href="/keywords/{{ r.name }}">
        <span class="icon">&#128269;</span>
        <div>
          <div>{{ r.name | replace('-', ' ') | title }}</div>
          <div style="font-size:12px;color:var(--muted)">{{ r.filename }}</div>
        </div>
        <span class="meta">{{ r.size_kb }} KB</span>
      </a>
    </li>
    {% endfor %}
  </ul>
</div>
{% else %}
<div class="alert alert-info">No keyword reports found in keyword-research/. Run /blog keyword-research [topic] to generate one.</div>
{% endif %}
"""
    return render(tmpl, title="Keywords", active="keywords", reports=reports)


@app.route("/keywords/new", methods=["GET", "POST"])
def keywords_new():
    result_html = ""
    topic = ""
    error = ""

    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        if not topic:
            error = "Please enter a topic."
        else:
            # Run analyze via subprocess if we have a script, otherwise show CLI command
            script = ROOT / "scripts" / "keyword_research.py"
            if script.exists():
                try:
                    r = subprocess.run(
                        [sys.executable, str(script), topic, "--format", "markdown"],
                        capture_output=True, text=True, timeout=60, cwd=ROOT
                    )
                    result_html = markdown.markdown(r.stdout or r.stderr, extensions=["tables", "fenced_code"])
                except Exception as ex:
                    error = f"Script error: {ex}"
            else:
                result_html = f"""
<div class="alert alert-info">
  <strong>Claude Code CLI command:</strong><br>
  Run this in your terminal to generate a keyword research report for <em>{topic}</em>:
</div>
<div class="cmd-chip" style="font-size:13px;padding:12px 16px;margin-top:8px;display:block">
  /blog keyword-research "{topic}"
</div>
<p style="color:var(--muted);margin-top:16px;font-size:13px">
  The report will be saved to <code>keyword-research/</code> and appear on the
  <a href="/keywords">Keywords</a> page automatically.
</p>
"""

    tmpl = """
<h1>New Keyword Research</h1>
<p class="subtitle">Enter a topic or niche to generate a priority keyword map with SERP analysis</p>

<div class="card" style="max-width:600px">
  <form method="POST" id="search-form">
    <div class="form-group">
      <label>Topic or Niche</label>
      <input type="text" name="topic" id="topic-search" value="{{ topic }}"
             placeholder="e.g. AI blog writing tools, content marketing for SaaS" autofocus>
    </div>
    <div class="form-group">
      <label>Depth</label>
      <select name="depth">
        <option value="standard" selected>Standard — 65+ keywords, SERP analysis (default)</option>
        <option value="quick">Quick — 10 keywords, Claude knowledge only</option>
        <option value="deep">Deep — 100+ keywords, full competitive analysis</option>
      </select>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <button type="submit" class="btn btn-primary" id="run-btn">
        <span class="spinner"></span>
        <span class="btn-label">&#9889; Run Research</span>
      </button>
      <a href="/keywords" class="btn btn-ghost">Cancel</a>
    </div>
  </form>
</div>

{% if error %}
<div class="alert alert-warn" style="margin-top:16px">{{ error }}</div>
{% endif %}

{% if result_html %}
<div class="card md-body" style="margin-top:24px">
  {{ result_html|safe }}
</div>
{% endif %}

<script>
document.getElementById('search-form').addEventListener('submit', function() {
  const btn = document.getElementById('run-btn');
  btn.classList.add('loading');
});
</script>
"""
    return render(tmpl, title="New Research", active="keywords",
                  topic=topic, error=error, result_html=result_html)


@app.route("/keywords/<report_name>")
def keywords_view(report_name):
    path = KEYWORD_DIR / f"{report_name}.md"
    if not path.exists():
        return redirect(url_for("keywords_list"))

    content_html = render_md(path)
    raw = path.read_text(encoding="utf-8")
    line_count = len(raw.splitlines())

    # Extract title from first H1
    title = report_name.replace("-", " ").title()
    for line in raw.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    tmpl = """
<div class="section-header">
  <div>
    <a href="/keywords" style="color:var(--muted);font-size:12px">← All Reports</a>
    <h1 style="margin-top:6px">{{ title }}</h1>
    <p class="subtitle">{{ line_count }} lines &nbsp;·&nbsp; keyword-research/{{ report_name }}.md</p>
  </div>
  <div style="display:flex;gap:8px">
    <a href="/api/keywords/{{ report_name }}/raw" class="btn btn-secondary" download>&#8595; Download</a>
  </div>
</div>

<div class="card md-body">
  {{ content_html|safe }}
</div>
"""
    return render(tmpl, title=title, active="keywords",
                  content_html=content_html, line_count=line_count,
                  report_name=report_name, title_h1=title)


@app.route("/api/keywords/<report_name>/raw")
def keywords_raw(report_name):
    path = KEYWORD_DIR / f"{report_name}.md"
    if not path.exists():
        return "Not found", 404
    return send_file(path, mimetype="text/markdown", as_attachment=True)


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
            error = "analyze_blog.py not found in scripts/"
        elif not post_content and not filepath:
            error = "Paste blog post content or enter a file path."
        else:
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

                if post_content:
                    os.unlink(tmp_path)

                if result.returncode != 0:
                    error = result.stderr or "Analyzer returned an error."
                else:
                    # Parse JSON output
                    output = result.stdout.strip()
                    # Find JSON object in output
                    start = output.find("{")
                    if start != -1:
                        score_data = json.loads(output[start:])
                    else:
                        error = "Could not parse analyzer output."

            except json.JSONDecodeError as e:
                error = f"JSON parse error: {e}"
            except subprocess.TimeoutExpired:
                error = "Analyzer timed out (30s)."
            except Exception as ex:
                error = f"Error: {ex}"

    tmpl = """
<h1>Blog Post Analyzer</h1>
<p class="subtitle">5-category, 100-point scoring: Content · SEO · E-E-A-T · Technical · AI Citation Readiness</p>

<div class="grid grid-2">
<div>
  <form method="POST">
    <div class="tabs tab-group" style="margin-bottom:16px">
      <button type="button" class="tab active" data-target="paste-panel">Paste Content</button>
      <button type="button" class="tab" data-target="path-panel">File Path</button>
    </div>

    <div id="paste-panel" class="tab-panel">
      <div class="form-group">
        <label>Blog Post (Markdown)</label>
        <textarea name="content" placeholder="Paste your blog post markdown here..." style="min-height:280px">{{ post_content }}</textarea>
      </div>
    </div>

    <div id="path-panel" class="tab-panel" style="display:none">
      <div class="form-group">
        <label>File Path</label>
        <input type="text" name="filepath" placeholder="posts/my-blog-post.md">
      </div>
    </div>

    <button type="submit" class="btn btn-primary" id="analyze-btn">
      <span class="spinner"></span>
      <span class="btn-label">&#128200; Analyze Post</span>
    </button>
  </form>

  {% if error %}
  <div class="alert alert-warn" style="margin-top:16px">{{ error }}</div>
  {% endif %}
</div>

<div>
{% if score_data %}
  {% set score = score_data.get('score', score_data.get('total', 0)) %}
  {% set band = score_data.get('band', '') %}
  <div class="card" style="margin-bottom:16px">
    <div style="display:flex;align-items:flex-end;gap:16px;margin-bottom:12px">
      <div>
        <div style="font-size:48px;font-weight:700;color:{{ score_color(score) }};line-height:1">{{ score }}</div>
        <div style="color:var(--muted);font-size:12px">/100</div>
      </div>
      <div>
        <div style="font-size:16px;font-weight:600">{{ band or 'Score' }}</div>
        <div class="score-bar-wrap" style="width:180px">
          <div class="score-bar" style="width:{{ score }}%;background:{{ score_color(score) }}"></div>
        </div>
      </div>
    </div>
  </div>

  {% set cats = score_data.get('categories', score_data.get('breakdown', {})) %}
  {% if cats %}
  <div class="score-grid">
    {% for name, val in cats.items() %}
    <div class="score-item">
      <div class="name">{{ name | replace('_', ' ') }}</div>
      <div class="value" style="color:{{ score_color(val) }}">{{ val }}</div>
      <div class="score-bar-wrap">
        <div class="score-bar" style="width:{{ val }}%;background:{{ score_color(val) }}"></div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% set issues = score_data.get('issues', score_data.get('recommendations', [])) %}
  {% if issues %}
  <div class="card" style="margin-top:16px">
    <h3 style="margin-bottom:12px">Recommendations</h3>
    <ul style="list-style:none">
      {% for issue in issues[:8] %}
      <li style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;color:var(--muted)">
        &#9888; {{ issue }}
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

{% else %}
  <div class="card" style="text-align:center;padding:40px 24px;color:var(--muted)">
    <div style="font-size:40px;margin-bottom:12px">&#128200;</div>
    <div>Paste a blog post and click Analyze</div>
    <div style="font-size:12px;margin-top:8px">Scoring takes 2-5 seconds</div>
  </div>
{% endif %}
</div>
</div>

<script>
document.getElementById('analyze-btn').closest('form').addEventListener('submit', function() {
  document.getElementById('analyze-btn').classList.add('loading');
});
</script>
"""
    return render(tmpl, title="Analyzer", active="analyze",
                  score_data=score_data, error=error,
                  post_content=post_content, score_color=score_color)


@app.route("/reports")
def reports():
    perf_reports = list_reports(PERFORMANCE_DIR)
    kw_reports = list_reports(KEYWORD_DIR)

    tmpl = """
<h1>Reports</h1>
<p class="subtitle">Performance analytics and keyword research archive</p>

<div class="grid grid-2">
  <div class="card">
    <div class="section-header">
      <h2>Performance Reports</h2>
      <span class="badge badge-blue">{{ perf_reports|length }}</span>
    </div>
    {% if perf_reports %}
    <ul class="report-list">
      {% for r in perf_reports %}
      <li>
        <a class="report-item" href="/reports/performance/{{ r.name }}">
          <span class="icon">&#128202;</span>
          <div>
            <div>{{ r.name }}</div>
            <div style="font-size:12px;color:var(--muted)">{{ r.size_kb }} KB</div>
          </div>
        </a>
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <p style="color:var(--muted);font-size:13px">
      No performance reports yet.<br>
      Run <code>/blog analyze --batch</code> to generate one.
    </p>
    {% endif %}
  </div>

  <div class="card">
    <div class="section-header">
      <h2>Keyword Reports</h2>
      <span class="badge badge-green">{{ kw_reports|length }}</span>
    </div>
    <ul class="report-list">
      {% for r in kw_reports %}
      <li>
        <a class="report-item" href="/keywords/{{ r.name }}">
          <span class="icon">&#128269;</span>
          <div>
            <div>{{ r.name | replace('-', ' ') | title }}</div>
            <div style="font-size:12px;color:var(--muted)">{{ r.size_kb }} KB</div>
          </div>
        </a>
      </li>
      {% endfor %}
    </ul>
  </div>
</div>
"""
    return render(tmpl, title="Reports", active="reports",
                  perf_reports=perf_reports, kw_reports=kw_reports)


@app.route("/reports/performance/<report_name>")
def perf_report_view(report_name):
    path = PERFORMANCE_DIR / f"{report_name}.md"
    if not path.exists():
        return redirect(url_for("reports"))
    content_html = render_md(path)
    tmpl = """
<a href="/reports" style="color:var(--muted);font-size:12px">← All Reports</a>
<h1 style="margin-top:6px">{{ report_name }}</h1>
<div class="card md-body" style="margin-top:16px">{{ content_html|safe }}</div>
"""
    return render(tmpl, title=report_name, active="reports",
                  content_html=content_html, report_name=report_name)


@app.route("/cluster-map")
def cluster_map_page():
    tmpl = """
<div class="section-header">
  <div>
    <h1>Cluster Map</h1>
    <p class="subtitle">Interactive force-directed topic cluster visualization</p>
  </div>
  <a href="/cluster-map/fullscreen" class="btn btn-secondary" target="_blank">&#9974; Fullscreen</a>
</div>
<div style="border-radius:8px;overflow:hidden;border:1px solid var(--border);height:600px">
  <iframe src="/cluster-map/embed" style="width:100%;height:100%;border:none"></iframe>
</div>
<div class="alert alert-info" style="margin-top:16px">
  Inject your cluster data: run <code>/blog cluster [topic]</code> then set
  <code>window.CLUSTER_DATA</code> in the cluster-map.html template.
</div>
"""
    return render(tmpl, title="Cluster Map", active="cluster")


@app.route("/cluster-map/embed")
@app.route("/cluster-map/fullscreen")
def cluster_map_embed():
    if not CLUSTER_MAP.exists():
        return "Cluster map not found", 404
    return send_file(CLUSTER_MAP, mimetype="text/html")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/api/stats")
def api_stats():
    return jsonify({
        "keyword_reports": len(list_reports(KEYWORD_DIR)),
        "performance_reports": len(list_reports(PERFORMANCE_DIR)),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"\n  Claude Blog UI → http://localhost:{port}\n")
    app.run(host=host, port=port, debug=True, use_reloader=False)
