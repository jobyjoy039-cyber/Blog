---
name: blog-drift
description: >
  Content drift detection. Captures a quality baseline snapshot of a blog post
  and detects how it has drifted over time from that baseline — catching
  unintended score regressions, stat removals, structure changes, or link rot.
  Use when user says "blog drift", "content drift", "detect drift",
  "baseline check", "content regression", "what changed in my posts",
  "quality regression".
user-invokable: true
argument-hint: "<file-path> [--baseline|--check|--diff]"
license: MIT
---

# Blog Drift — Content Quality Baseline & Regression Detection

Captures quality snapshots of blog posts and detects regressions over time.
Prevents unintended quality decay from edits, CMS migrations, or contributor
changes. All baselines stored locally — no external API required.

## Input Handling

- **File path**: Target blog post file
- **Directory**: Baseline or check all posts in directory
- **Modes**:
  - `--baseline` — capture the current state as the reference snapshot
  - `--check` — compare current state against stored baseline
  - `--diff` — show what changed since baseline (detailed line-by-line)
  - `--reset` — delete stored baseline and start fresh
- **Flags**:
  - `--threshold N` — score drop that triggers a Drift Alert (default: 5 points)
  - `--format json|markdown`

## Baseline Data Captured

A baseline snapshot records these dimensions of the post at a point in time:

### Quality Metrics
- Total quality score (0-100)
- Category scores: content, SEO, E-E-A-T, technical, AI citation
- Word count
- Paragraph count
- Average paragraph length

### Structure Signals
- H1 count, H2 count, H3 count
- H2 question ratio
- Heading hierarchy (clean/dirty)
- FAQ section present: yes/no
- Key Takeaways box present: yes/no

### Content Signals
- Total statistics count
- Sourced statistics count (with named source)
- Unsourced statistics count
- Unique source domains
- Image count
- Alt text coverage (% of images with alt text)
- Internal link count
- External link count

### Schema Signals
- Schema types present (BlogPosting, FAQPage, etc.)
- datePublished value
- dateModified value
- Author field present: yes/no

### SEO Signals
- Title tag character count
- Meta description character count
- Primary keyword (from frontmatter or H1)
- Canonical URL set: yes/no
- OG tags present: yes/no

### Freshness Signals
- `lastUpdated` frontmatter value
- Oldest statistic year referenced in text
- Snapshot timestamp

## Baseline Storage

Baselines stored at `.blog-drift/[post-slug].json` in the repo root:

```json
{
  "file": "posts/my-post.md",
  "slug": "my-post",
  "captured_at": "2026-05-16T10:30:00Z",
  "git_commit": "abc1234",
  "scores": {
    "total": 82,
    "content": 24,
    "seo": 21,
    "eeat": 13,
    "technical": 13,
    "ai_citation": 11
  },
  "structure": {
    "word_count": 2140,
    "h1_count": 1,
    "h2_count": 7,
    "h3_count": 4,
    "h2_question_ratio": 0.71,
    "hierarchy_clean": true,
    "has_faq": true,
    "has_key_takeaways": true
  },
  "content": {
    "stat_count": 9,
    "sourced_stat_count": 9,
    "unsourced_stat_count": 0,
    "unique_sources": 7,
    "image_count": 4,
    "alt_text_coverage": 1.0,
    "internal_links": 3,
    "external_links": 6
  },
  "schema": {
    "types": ["BlogPosting", "FAQPage"],
    "has_author": true,
    "has_date_published": true,
    "has_date_modified": true
  },
  "seo": {
    "title_chars": 56,
    "meta_chars": 157,
    "has_canonical": true,
    "has_og_tags": true
  },
  "freshness": {
    "last_updated": "2026-02-10",
    "oldest_stat_year": 2024
  }
}
```

## Drift Detection Logic

### Step 1 — Run analyze_blog.py on current file

```bash
python3 scripts/analyze_blog.py [file] --format json
```

### Step 2 — Load stored baseline

Read `.blog-drift/[post-slug].json`

If no baseline exists:
- `--check` mode: warn "No baseline found. Run with --baseline first."
- `--baseline` mode: create the baseline now.

### Step 3 — Compare Dimensions

For each dimension, calculate the delta (current - baseline).

Flag rules:
- **Score drop ≥ threshold (default 5)** → Drift Alert
- **Sourced stats decreased** → Drift Alert (stats may have been removed)
- **Word count dropped > 15%** → Drift Alert (content may have been truncated)
- **H2 count changed** → Drift Warning (structure changed)
- **Schema types reduced** → Drift Alert (schema removed)
- **FAQ removed** → Drift Warning
- **Alt text coverage dropped** → Drift Warning
- **External links decreased > 2** → Drift Warning (link rot or removal)
- **Score improved ≥ 5** → Positive Drift (log but don't alert)

### Step 4 — Generate Diff Report

For each flagged dimension, show: baseline value → current value → delta → severity

## Process

### Baseline Mode (`--baseline`)

1. Run quality analysis on the current file
2. Extract all baseline dimensions
3. Get current git commit hash: `git rev-parse --short HEAD`
4. Write snapshot to `.blog-drift/[post-slug].json`
5. Also write a human-readable `.blog-drift/[post-slug].md` summary
6. Confirm: "Baseline captured for [post]. Run `/blog drift [file] --check` to detect future drift."

### Check Mode (`--check`)

1. Load the stored baseline
2. Run quality analysis on the current file
3. Compare all dimensions
4. Calculate overall drift score: sum of negative deltas across all metrics
5. Classify: No Drift / Minor Drift / Moderate Drift / Severe Drift
6. Output the drift report

### Diff Mode (`--diff`)

1. Run check mode first
2. Additionally: compare the actual text diff using the git history
   ```bash
   git diff [baseline-commit] -- [file]
   ```
3. Identify which sections changed (by heading)
4. Flag which changes correlate with metric regressions

### Batch Mode (directory input)

Run check mode on all posts with a baseline. Output a summary table sorted
by drift severity.

## Drift Classification

| Classification | Condition |
|----------------|-----------|
| No Drift | Total score delta ≥ -4, no Drift Alerts |
| Minor Drift | Total score delta -5 to -9, or 1 Drift Warning |
| Moderate Drift | Total score delta -10 to -19, or 1-2 Drift Alerts |
| Severe Drift | Total score delta ≤ -20, or 3+ Drift Alerts |

## Output Format

### Check Report

```markdown
## Drift Report: [Post Title]
**Baseline captured:** YYYY-MM-DD (commit: abc1234)
**Checked:** YYYY-MM-DD
**Classification:** No Drift / Minor / Moderate / Severe

---

### Score Delta

| Category | Baseline | Current | Delta | Status |
|----------|---------|---------|-------|--------|
| Total | 82 | 74 | -8 | ⚠️ Moderate Drift |
| Content | 24 | 21 | -3 | ⚠️ |
| SEO | 21 | 19 | -2 | ⚠️ |
| E-E-A-T | 13 | 13 | 0 | ✅ |
| Technical | 13 | 11 | -2 | ⚠️ |
| AI Citation | 11 | 10 | -1 | ✅ |

---

### Drift Alerts (must investigate)

- ❌ **Sourced stats dropped:** 9 → 6 (3 statistics lost their source attribution)
- ❌ **Schema reduced:** BlogPosting + FAQPage → BlogPosting only (FAQPage schema removed)

### Drift Warnings (review recommended)

- ⚠️ **Word count dropped:** 2,140 → 1,890 (-12%) — content may have been truncated
- ⚠️ **External links:** 6 → 4 — 2 links removed or rotted

---

### Stable Dimensions (no drift)

- ✅ Heading structure (H1: 1, H2: 7, H3: 4)
- ✅ H2 question ratio (0.71)
- ✅ Image count (4)
- ✅ Alt text coverage (100%)

---

### Recommended Actions

1. Restore the 3 sourced statistics (check git history for which were removed)
2. Re-add FAQPage schema markup
3. Investigate removed external links — replace or remove dead refs
4. Run `/blog rewrite [file]` if manual fixes don't recover the score

**Command:** `/blog rewrite [file]` — estimated score recovery: +6 to +10 points
```

### Batch Summary

```markdown
## Drift Scan: [Directory]
**Date:** YYYY-MM-DD | **Posts scanned:** N | **With baselines:** N

| Post | Baseline Score | Current Score | Delta | Classification |
|------|---------------|--------------|-------|----------------|
| [title] | 82 | 74 | -8 | ⚠️ Moderate |
| [title] | 91 | 90 | -1 | ✅ No Drift |
```

## .gitignore Integration

Add to `.gitignore` if baselines should not be committed (recommended for
team repos where each developer has their own baseline):

```
# Uncomment to exclude drift baselines from git:
# .blog-drift/
```

Or commit `.blog-drift/` if you want team-wide baseline tracking.

## Quality Self-Check

Before returning output, verify:
- [ ] Baseline file written to `.blog-drift/[slug].json` in baseline mode
- [ ] Git commit hash captured in baseline
- [ ] All drift alerts have a specific value comparison (not just "changed")
- [ ] Recommended actions include the specific `/blog` command to fix
- [ ] Batch mode output sorted by drift severity (Severe first)
