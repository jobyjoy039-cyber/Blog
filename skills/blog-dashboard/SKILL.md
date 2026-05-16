---
name: blog-dashboard
description: >
  Content performance dashboard. Aggregates quality scores, traffic data,
  decay signals, drift status, and AI citation readiness across all blog posts
  into a single visual summary. Outputs an HTML dashboard or markdown table.
  Use when user says "dashboard", "blog dashboard", "performance overview",
  "blog health", "content overview", "portfolio view", "all posts report".
user-invokable: true
argument-hint: "[directory]"
license: MIT
---

# Blog Dashboard — Content Portfolio Performance View

Aggregates all available data across every blog post into one unified
performance dashboard. Combines local quality scores, decay signals, drift
status, and Google data (if configured) into a sortable, filterable overview.

## Input Handling

- **Directory**: Scan all blog posts (default: current directory)
- **Flags**:
  - `--format [html|markdown|json]` — output format (default: markdown)
  - `--sort [score|traffic|decay|drift|date]` — sort order (default: score)
  - `--filter [healthy|needs-work|critical]` — filter by status band
  - `--gsc` — include Google Search Console data (requires blog-google)
  - `--output <file>` — save dashboard to this file (default: `dashboard.md`)
  - `--open` — open HTML dashboard in browser after generation

## Data Sources (in priority order)

The dashboard pulls from whichever sources are available:

| Source | Required | What it provides |
|--------|---------|-----------------|
| `scripts/analyze_blog.py` | Yes (core) | Quality scores, AI detection, structure |
| `.blog-drift/` directory | Optional | Drift status per post |
| `performance/` directory | Optional | Historical GSC + GA4 data |
| Google Search Console | Optional (--gsc) | Live clicks, impressions, CTR, position |
| `competitors/matrix.md` | Optional | Competitive coverage status |

## Dashboard Metrics Per Post

For each post, collect:

| Metric | Source | Default if missing |
|--------|--------|------------------|
| Quality score (0-100) | analyze_blog.py | Required |
| Content sub-score | analyze_blog.py | Required |
| SEO sub-score | analyze_blog.py | Required |
| E-E-A-T sub-score | analyze_blog.py | Required |
| AI citation sub-score | analyze_blog.py | Required |
| Word count | analyze_blog.py | Required |
| Published date | frontmatter | "unknown" |
| Last updated | frontmatter | "never" |
| Decay status | blog-decay logic | Estimate from age |
| Drift status | .blog-drift/ | "no baseline" |
| Monthly clicks | GSC/performance/ | "—" |
| Avg position | GSC/performance/ | "—" |
| CTR | GSC/performance/ | "—" |

## Status Classification

Assign each post a single status based on quality score + decay + drift:

| Status | Criteria | Color |
|--------|---------|-------|
| Excellent | Score ≥ 85, no decay, no drift | Green |
| Healthy | Score 70-84, low decay, no severe drift | Light green |
| Needs Attention | Score 50-69, or moderate decay/drift | Yellow |
| Needs Work | Score 30-49, or high decay, or moderate drift | Orange |
| Critical | Score < 30, or severe decay/drift | Red |

## Process

### Step 1 — Discover All Posts

```bash
find [directory] -name "*.md" -o -name "*.mdx" | grep -v node_modules | grep -v .blog-drift | grep -v skills/ | grep -v agents/ | grep -v docs/
```

### Step 2 — Score All Posts

```bash
python3 scripts/analyze_blog.py [directory] --batch --format json
```

Parse results for each post.

### Step 3 — Enrich with Available Data

For each post:
1. Check if `.blog-drift/[slug].json` exists → load drift status
2. Check if `performance/` has a recent report → load traffic data
3. If `--gsc` flag: query GSC for each post URL
4. Read frontmatter for dates

### Step 4 — Calculate Portfolio Metrics

Across all posts:
- Average quality score
- Distribution across status bands
- Total monthly clicks (if GSC available)
- Highest and lowest scoring posts
- Most traffic vs lowest quality (opportunity posts)
- Posts with no baseline (drift monitoring gap)

### Step 5 — Generate Output

**Markdown format**: Tables sortable by column header

**HTML format**: Self-contained dashboard with:
- Summary cards (total posts, avg score, total traffic)
- Status distribution bar chart (inline SVG)
- Sortable data table with color-coded status badges
- Filter buttons (All / Excellent / Healthy / Needs Work / Critical)
- No external CDN dependencies (all inline CSS + JS)

## HTML Dashboard Spec

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Blog Dashboard</title>
  <style>
    /* Dark mode, monospace font, clean layout */
    body { background: #0d1117; color: #c9d1d9; font-family: ui-monospace, monospace; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px; }
    .score-green { color: #3fb950; }
    .score-yellow { color: #d29922; }
    .score-orange { color: #f0883e; }
    .score-red { color: #f85149; }
    table { border-collapse: collapse; width: 100%; }
    th, td { padding: 8px 12px; border-bottom: 1px solid #30363d; text-align: left; }
    th { cursor: pointer; user-select: none; }
    th:hover { background: #1f2429; }
    .badge { padding: 2px 8px; border-radius: 12px; font-size: 12px; }
    /* Status badge colors */
    .excellent { background: #1a4731; color: #3fb950; }
    .healthy { background: #1c3a2a; color: #56d364; }
    .attention { background: #3a2d0f; color: #e3b341; }
    .needs-work { background: #3a1f0f; color: #f0883e; }
    .critical { background: #3a0f0f; color: #f85149; }
  </style>
</head>
<body>
  <!-- Summary cards -->
  <div class="cards-row">
    <div class="card">Total Posts: <strong>[N]</strong></div>
    <div class="card">Avg Score: <strong>[N]/100</strong></div>
    <div class="card">Critical: <strong>[N]</strong></div>
    <div class="card">Monthly Clicks: <strong>[N or —]</strong></div>
  </div>

  <!-- Status distribution SVG bar -->
  [inline SVG bar showing status distribution]

  <!-- Filter buttons -->
  <div class="filters">
    <button onclick="filter('all')">All ([N])</button>
    <button onclick="filter('excellent')">Excellent ([N])</button>
    <button onclick="filter('healthy')">Healthy ([N])</button>
    <button onclick="filter('attention')">Attention ([N])</button>
    <button onclick="filter('needs-work')">Needs Work ([N])</button>
    <button onclick="filter('critical')">Critical ([N])</button>
  </div>

  <!-- Data table -->
  <table id="dashboard-table">
    <thead>
      <tr>
        <th onclick="sort('title')">Post</th>
        <th onclick="sort('score')">Score</th>
        <th onclick="sort('status')">Status</th>
        <th onclick="sort('words')">Words</th>
        <th onclick="sort('age')">Age</th>
        <th onclick="sort('drift')">Drift</th>
        <th onclick="sort('clicks')">Clicks/mo</th>
        <th onclick="sort('position')">Avg Pos</th>
        <th onclick="sort('ctr')">CTR</th>
      </tr>
    </thead>
    <tbody>
      [one row per post]
    </tbody>
  </table>

  <script>
    /* Inline sort and filter logic — no external dependencies */
    function sort(col) { /* sort table by column */ }
    function filter(status) { /* show/hide rows by status */ }
  </script>
</body>
</html>
```

## Output Format (Markdown)

```markdown
# Blog Dashboard
**Generated:** YYYY-MM-DD | **Posts:** N | **Avg Score:** N/100

---

## Portfolio Summary

| Metric | Value |
|--------|-------|
| Total posts | N |
| Excellent (85+) | N (N%) |
| Healthy (70-84) | N (N%) |
| Needs Attention (50-69) | N (N%) |
| Needs Work (30-49) | N (N%) |
| Critical (<30) | N (N%) |
| Monthly clicks (total) | N or — |
| Posts with no drift baseline | N |

---

## Post Performance Table

| Post | Score | Status | Words | Age | Decay | Drift | Clicks | Position |
|------|-------|--------|-------|-----|-------|-------|--------|---------|
| [title] | 87 | Excellent | 2,140 | 3mo | Healthy | ✅ No drift | 1,240 | 4.2 |
| [title] | 52 | Attention | 890 | 18mo | Urgent | ⚠️ Moderate | 120 | 28.4 |
...

---

## Action Priorities

**Immediate (Critical posts):**
1. [Post title] — Score: N — `/blog rewrite [file]`

**This Month (Needs Work):**
[list]

**Quick Wins (Needs Attention, high traffic):**
[posts with traffic but low score — highest ROI fixes]

---

**Dashboard saved to:** [output file]
```

## Quality Self-Check

Before returning output, verify:
- [ ] All posts in the directory analyzed (none skipped)
- [ ] Status classification applied consistently
- [ ] Action Priorities section identifies Quick Wins (traffic × improvement gap)
- [ ] HTML output is self-contained (no external CDN)
- [ ] Markdown table sorted by requested sort column
- [ ] Missing data shown as "—" not blank or null
