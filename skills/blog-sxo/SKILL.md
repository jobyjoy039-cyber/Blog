---
name: blog-sxo
description: >
  Search Experience Optimization audit. Evaluates blog posts for SERP feature
  targeting (featured snippets, People Also Ask, knowledge panels), zero-click
  optimization, user intent alignment, and search experience signals that
  influence rankings beyond traditional SEO. Use when user says "sxo",
  "search experience", "featured snippet", "SERP features", "PAA optimization",
  "zero click", "snippet optimization", "sxo audit".
user-invokable: true
argument-hint: "<file-path>"
license: MIT
---

# Blog SXO — Search Experience Optimization Audit

Audits blog posts for Search Experience Optimization (SXO) — the intersection
of SEO and UX signals that determine SERP feature eligibility and zero-click
visibility. Goes beyond traditional on-page SEO to evaluate how Google's
SERP features interact with the post's content structure.

## What SXO Covers

SXO is distinct from standard SEO:
- **SEO**: metadata, keywords, backlinks, technical
- **SXO**: featured snippets, PAA boxes, knowledge panels, rich results,
  user intent match, dwell time signals, and zero-click optimization

## Input Handling

- **File path**: Read and audit a single blog post
- **URL**: Fetch and audit a published post
- **Flags**:
  - `--keyword <kw>` — target keyword for SERP feature research
  - `--format json|markdown`
  - `--serp` — include SERP feature opportunity analysis (uses WebSearch)

## SERP Feature Eligibility Criteria

### Featured Snippet (Position 0)

Google selects featured snippets from pages that:
1. Already rank in positions 1-10 for the target keyword
2. Have a direct, concise answer to the query (40-60 words)
3. Use a format matching the query type:
   - Definition query → paragraph snippet (40-60 words)
   - "How to" query → ordered list snippet (5-8 steps)
   - "Best/Top" query → unordered list snippet (5-8 items)
   - Comparison query → table snippet

**Audit checks:**
- Does the post contain a 40-60 word definition or answer block?
- Is the answer immediately after a heading that mirrors the query?
- For how-to: are steps in a numbered list format?
- For comparisons: is there a markdown table?

### People Also Ask (PAA) Boxes

PAA eligibility requires:
- Questions formatted as H2 or H3 headings
- Concise answers (40-80 words) immediately below each question
- Question phrasing that matches natural language search queries
- FAQ schema markup present

**Audit checks:**
- Count questions in H2/H3 format
- Measure answer length below each question heading
- Check for FAQ schema in the post
- Flag any questions that are statements (not genuine questions)

### Knowledge Panel / Entity Optimization

For posts about a named person, company, product, or place:
- Is the entity named clearly in the first paragraph?
- Is there structured data (Person, Organization, Product schema)?
- Are 3+ authoritative attributes mentioned (founding date, location, etc.)?

### Rich Results (Recipe, How-To, Review)

- For how-to posts: is `HowTo` schema present with step objects?
- For review posts: is `Review` schema with `ratingValue` present?
- For event posts: is `Event` schema present?

### Image Pack Eligibility

- Are images present with descriptive alt text?
- Do image filenames contain the keyword (not `IMG_1234.jpg`)?
- Is there an `ImageObject` schema linking to the post?

## SXO Audit Process

### Step 1 — Intent Classification

Identify the dominant search intent for the post's primary keyword:
- **Informational**: user wants to learn ("what is", "how does", "why")
- **Commercial**: user is comparing before buying ("best", "vs", "review")
- **Navigational**: user wants a specific site/page
- **Transactional**: user wants to act ("buy", "download", "get")

Match the post's content depth and CTA to the intent.
Mismatch = SXO failure (content answers the wrong intent).

### Step 2 — Featured Snippet Audit

1. Locate all H2/H3 headings
2. For each heading, check the first 40-80 words of the section:
   - Does it directly answer the heading's implied question?
   - Is it 40-60 words (paragraph snippet zone)?
3. Check if any section has a numbered or bulleted list following a heading
4. Check for comparison tables

Score: 0-10 (10 = multiple snippet-ready blocks present)

### Step 3 — PAA Audit

1. Count headings phrased as questions (start with What/How/Why/When/Is/Can)
2. For each, measure the answer block length
3. Check FAQ schema presence
4. Compare question phrasing to likely PAA variants of the primary keyword

Score: 0-10 (10 = 3+ PAA-ready Q&A blocks with FAQ schema)

### Step 4 — Zero-Click Optimization Score

Zero-click content satisfies the query on the SERP without requiring a click.
This sounds counterproductive but builds brand visibility and trust.

Evaluate:
- Does the meta description contain the answer to the primary query?
- Is the first paragraph a complete answer that could stand alone?
- Are Key Takeaways / TL;DR boxes present?

Score: 0-10

### Step 5 — Dwell Time Signals

Estimate content signals that extend time-on-page:
- Are there embedded videos, charts, or interactive elements?
- Is content depth sufficient for the topic complexity?
- Does the post have a clear logical flow (short intro → depth → conclusion)?
- Is there a table of contents for long posts (>2,000 words)?

Score: 0-10

### Step 6 — SERP Opportunity Research (if `--serp` flag)

Search for the target keyword and analyze the actual SERP:
1. What SERP features currently appear? (snippet, PAA, image pack, etc.)
2. Which position does the post currently hold (if published)?
3. What format does the current featured snippet use?
4. How many PAA questions appear — and do they match our headings?

Output specific optimization moves based on the live SERP.

## Scoring Summary

| Category | Weight | Score |
|----------|--------|-------|
| Featured Snippet Readiness | 30% | /10 |
| PAA Coverage | 25% | /10 |
| Zero-Click Optimization | 20% | /10 |
| Dwell Time Signals | 15% | /10 |
| Rich Results Schema | 10% | /10 |

**SXO Score** = weighted total × 10 (max 100)

Bands:
- 80-100 = SXO Optimized
- 60-79 = Good — minor improvements
- 40-59 = Needs Work
- Below 40 = SXO Unoptimized

## Output Format

```markdown
## SXO Audit: [Post Title]

**SXO Score:** N/100 — [Band]
**Primary Keyword:** [keyword]
**Search Intent:** [Informational/Commercial/Navigational/Transactional]
**Intent Match:** ✅ Matched / ❌ Mismatched

---

### SERP Feature Eligibility

| Feature | Eligible? | Gap | Priority Fix |
|---------|----------|-----|-------------|
| Featured Snippet | ✅/❌ | [gap] | [fix] |
| PAA Boxes | ✅/❌ | [gap] | [fix] |
| Image Pack | ✅/❌ | [gap] | [fix] |
| Rich Results | ✅/❌ | [gap] | [fix] |

---

### Scoring Breakdown

| Category | Score | Key Finding |
|----------|-------|------------|
| Featured Snippet Readiness | N/10 | [finding] |
| PAA Coverage | N/10 | [finding] |
| Zero-Click Optimization | N/10 | [finding] |
| Dwell Time Signals | N/10 | [finding] |
| Rich Results Schema | N/10 | [finding] |

---

### Prioritized Fixes

#### Critical (implement before next publish)
- [ ] [specific fix with implementation instructions]

#### High (implement within 1 week)
- [ ] [specific fix]

#### Medium (implement at next update)
- [ ] [specific fix]

---

### Snippet-Ready Block Suggestions

For each section that needs a snippet-ready answer block:

**Heading:** [H2 text]
**Suggested block (40-60 words):**
> [Draft answer block ready to paste]
```

## Quality Self-Check

Before returning output, verify:
- [ ] Search intent classified and intent match evaluated
- [ ] All 5 scoring categories have a score and a specific finding
- [ ] Featured snippet gaps include specific word count and format recommendations
- [ ] PAA audit counts actual question headings in the post
- [ ] Snippet-ready block drafts provided for each gap (not just identified)
- [ ] Fixes sorted by priority
