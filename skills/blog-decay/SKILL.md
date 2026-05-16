---
name: blog-decay
description: >
  Content decay detection and refresh prioritization. Scans all blog posts,
  identifies posts with declining traffic or aging signals, and outputs a
  prioritized refresh queue with recommended actions. Integrates with Google
  Search Console data when available. Use when user says "blog decay",
  "content decay", "find stale posts", "refresh queue", "blog traffic decline",
  "which posts need updating", "content freshness audit".
user-invokable: true
argument-hint: "[directory]"
license: MIT
---

# Blog Decay — Content Freshness & Refresh Prioritization

Identifies blog posts showing decay signals — traffic decline, aging
statistics, outdated references, or low freshness scores — and produces
a prioritized refresh queue with recommended action per post.

## Input Handling

- **Directory**: Scan all blog post files in the given path (default: current dir)
- **Single file**: Run decay check on one post only
- **Flags**:
  - `--gsc` — use Google Search Console data (requires blog-google configured)
  - `--threshold N` — flag posts older than N months (default: 12)
  - `--format json|markdown|table`
  - `--sort priority|age|score`

## Decay Signal Categories

### Signal 1 — Age (Weight: 30%)

| Age | Score (0-10) |
|-----|-------------|
| Under 6 months | 10 (fresh) |
| 6-12 months | 7 |
| 12-18 months | 5 |
| 18-24 months | 3 |
| Over 24 months | 1 |
| Over 36 months | 0 (critical decay) |

Read from frontmatter `date` or `lastUpdated` field.

### Signal 2 — Statistic Freshness (Weight: 25%)

For each statistic in the post:
- Does it reference a year? Extract the year.
- Is the year 2+ years before the current date? → stale stat
- Count stale stats vs total stats

Score: (fresh stats / total stats) × 10

### Signal 3 — Reference Currency (Weight: 20%)

Scan for:
- Year mentions in text (2020, 2021, etc. that are now outdated)
- References to tools, products, or platforms that may have changed
  significantly (check for pattern: "as of [year]", "[year] update",
  "current version")
- Any `lastUpdated` frontmatter field — if absent, penalize

Score: 10 if `lastUpdated` within 12 months, 5 if 12-24 months, 0 if older

### Signal 4 — GSC Traffic Trend (Weight: 25%, only if `--gsc` flag set)

Pull from blog-google GSC data:
```bash
python3 skills/blog-google/scripts/run.py gsc_query.py performance \
  --url "[post-url]" --start-date "[90-days-ago]" --compare-period 90
```

Calculate quarter-on-quarter click change:
- Growth >10% = 10 (healthy)
- -10% to +10% = 7 (stable)
- -10% to -20% = 5 (mild decay)
- -20% to -30% = 3 (decay)
- Below -30% = 0 (critical decay)

If GSC not available: score this signal as 5 (neutral) for all posts.

## Process

### Step 1 — Discover Posts

```bash
find [directory] -name "*.md" -o -name "*.mdx" | grep -v node_modules
```

For each post, read:
- Frontmatter: title, date, lastUpdated, tags
- Body: extract statistics (any sentence with a number + a claim)
- Year mentions in text

### Step 2 — Score Each Post

Apply all 4 decay signals. Calculate weighted total:
```
decay_score = (age_score × 0.30) + (stat_score × 0.25) + (ref_score × 0.20) + (gsc_score × 0.25)
```

Decay band:
- 8-10 = Healthy (no action needed)
- 6-7.9 = Monitor (review in 3 months)
- 4-5.9 = Refresh Recommended
- 2-3.9 = Refresh Urgent
- 0-1.9 = Critical — refresh before next publish

### Step 3 — Recommend Action Per Post

Based on decay band and score breakdown:

| Band | Action |
|------|--------|
| Healthy | No action |
| Monitor | Schedule review in 90 days |
| Refresh Recommended | Update stats, add `lastUpdated`, republish |
| Refresh Urgent | Full rewrite pass via `/blog rewrite` |
| Critical | Prioritize immediately — run `/blog rewrite` this sprint |

### Step 4 — Build Refresh Queue

Sort all non-Healthy posts by priority score (most decayed first).
Output the queue with estimated effort per post:
- Stat update only = Low effort (30 min)
- Freshness signals + minor rewrites = Medium effort (2 hrs)
- Full rewrite = High effort (4+ hrs)

### Step 5 — GSC Deep Dive (if `--gsc` flag)

For Critical posts, pull additional GSC data:
- Top queries still driving impressions (even if clicks declined)
- Position trends for primary keyword
- Pages that cannibalize this post's keywords

Include in the post's refresh brief.

## Output Format

```markdown
## Content Decay Report
**Date:** YYYY-MM-DD
**Posts Scanned:** N
**Healthy:** N | **Monitor:** N | **Refresh Recommended:** N | **Refresh Urgent:** N | **Critical:** N

---

### Refresh Queue (Prioritized)

#### Critical — Act This Sprint

| Post | Age | Stale Stats | Trend | Score | Action |
|------|-----|------------|-------|-------|--------|
| [title] | 28mo | 6/8 stale | -35% | 1.2/10 | Full rewrite |

#### Refresh Urgent

[same table]

#### Refresh Recommended

[same table]

---

### Post Detail: [Post Title]

**File:** [path]
**Published:** YYYY-MM-DD | **Last Updated:** YYYY-MM-DD (or "never")
**Decay Score:** N.N/10 — [Band]

**Signal Breakdown:**
- Age: N/10 (24 months old)
- Stat Freshness: N/10 (4 of 7 stats reference 2022 or earlier)
- Reference Currency: N/10 (no lastUpdated field, 3 outdated year mentions)
- Traffic Trend: N/10 (-28% QoQ, GSC data)

**Stale Statistics Found:**
1. "[stat text]" — references [year], now [N] years old
2. ...

**Recommended Actions:**
1. Replace stale stats (priority: items 1, 3, 5 above)
2. Update `lastUpdated` in frontmatter after changes
3. Add 2026 data on [specific topic gap]
4. Run `/blog rewrite [file]` for full optimization pass

**Estimated Effort:** Medium (2 hrs)
```

## Quality Self-Check

Before returning output, verify:
- [ ] All 4 signals scored for each post
- [ ] Posts sorted by priority (Critical first)
- [ ] Each post has a specific recommended action, not just a band label
- [ ] Stale statistics listed with the actual text and the outdated year
- [ ] Estimated effort included per post
- [ ] GSC data used if `--gsc` flag set, or neutralized (score 5) if not
