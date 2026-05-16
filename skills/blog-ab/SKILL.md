---
name: blog-ab
description: >
  Generate headline and meta description variants for A/B testing. Produces
  3-5 title variants per post with predicted CTR scores, emotional angle
  analysis, and keyword placement scoring. Exports a test plan with tracking
  guidance. Use when user says "ab test", "title variants", "headline test",
  "test headlines", "split test titles", "improve click through rate".
user-invokable: true
argument-hint: "<file-path-or-topic>"
license: MIT
---

# Blog A/B — Headline & Meta Variant Generator

Generates testable headline and meta description variants for blog posts,
scored by predicted click-through rate, emotional resonance, and SEO fit.
Outputs a structured test plan ready to plug into any analytics setup.

## Input Handling

- **File path**: Read frontmatter for existing title + meta description
- **Topic string**: Generate variants for a new post concept
- **Flags**: `--variants N` (default 5), `--format json|markdown`, `--platform google|social|email`

## Scoring Model

Each variant is scored on 4 dimensions (1-10 each):

**Keyword placement** — does the primary keyword appear in the first 3 words?  
**Emotional trigger** — does the title use a proven trigger (number, curiosity gap, fear/gain, how-to)?  
**Specificity** — does it promise a concrete outcome rather than a vague benefit?  
**Length fit** — is it 50-60 chars (Google title) or 70-100 chars (social)?

Total: 40 max. Predicted CTR band:
- 32-40 = High (>5% CTR estimated)
- 22-31 = Medium (2-5% CTR estimated)
- Below 22 = Low (<2% CTR estimated)

## Process

### Step 1 — Extract Source Material

1. Read the post (or accept topic as input)
2. Extract: current title, current meta description, primary keyword, post type
   (how-to, listicle, comparison, case study, thought leadership)
3. Identify the core value proposition: what does the reader gain?

### Step 2 — Generate Headline Variants

For each of 5 headline angles, write one variant:

**Angle 1 — Number/List**: Lead with a specific number
- Pattern: `[N] [things/ways/steps] to [outcome]`
- Example: "7 Ways to Double Blog Traffic Without Paid Ads"

**Angle 2 — Curiosity Gap**: Withhold the answer, create tension
- Pattern: `[Surprising claim] — [partial reveal]`
- Example: "Most Blogs Fail at SEO for One Overlooked Reason"

**Angle 3 — How-To / Direct Benefit**: Promise a clear method
- Pattern: `How to [achieve outcome] [without pain/in time frame]`
- Example: "How to Write a Blog Post That Ranks in 30 Days"

**Angle 4 — Question**: Mirrors search intent directly
- Pattern: `[Question the reader is asking]?`
- Example: "Why Does My Blog Get Traffic But No Conversions?"

**Angle 5 — Contrarian / Counterintuitive**: Challenge the common assumption
- Pattern: `[Common belief] Is [Wrong/Overrated/Costing You]`
- Example: "Long-Form Content Is Overrated — Here's What Actually Ranks"

Score each variant on the 4-dimension model above.

### Step 3 — Generate Meta Description Variants

For the top 2 headline variants, generate a paired meta description:
- 150-160 characters exactly
- Contains primary keyword in first half
- Ends with an implicit or explicit CTA
- Includes one specific stat or benefit

### Step 4 — Platform Adaptation

If `--platform social` or `--platform email` flag is set, also generate:

**Social headline** (70-100 chars): more emotional, can break grammar rules  
**Email subject line** (40-50 chars): curiosity gap or personal benefit, no spam words

### Step 5 — Build Test Plan

Output a test plan with:
- Which 2 variants to test first (highest + second-highest score)
- Recommended test duration: 2 weeks minimum, 200+ clicks per variant
- Primary metric: organic CTR (from Google Search Console)
- Secondary metric: time on page (engagement signal)
- How to implement: swap title tag and OG title, monitor separately

## Output Format

```markdown
## A/B Test Plan: [Post Title / Topic]

**Primary Keyword:** [keyword]
**Post Type:** [how-to/listicle/etc.]
**Current CTR Band:** [High/Medium/Low] (if existing post)

---

### Headline Variants

| # | Variant | Angle | Score | CTR Band | Chars |
|---|---------|-------|-------|----------|-------|
| 1 | [title] | Number | 34/40 | High | 54 |
| 2 | [title] | Curiosity | 31/40 | Medium | 58 |
...

**Score Breakdown — Variant 1:**
- Keyword placement: N/10
- Emotional trigger: N/10
- Specificity: N/10
- Length fit: N/10

---

### Meta Description Variants (for top 2 headlines)

**Paired with Variant 1:**
> [meta description — 150-160 chars]

**Paired with Variant 2:**
> [meta description — 150-160 chars]

---

### Recommended Test

**Test Variant 1 vs Variant 2**
- Duration: 2 weeks minimum
- Target clicks per variant: 200+
- Primary metric: Google Search Console CTR
- Secondary metric: Average time on page

**Implementation:**
1. Set title tag to Variant 1, og:title to same
2. After 2 weeks, swap to Variant 2
3. Compare CTR from GSC > Performance > [post URL]

---

### Social / Email Variants (if requested)
[social headline + email subject line for top variant]
```

## Quality Self-Check

Before returning output, verify:
- [ ] 5 variants generated, each using a different angle
- [ ] Every variant scored on all 4 dimensions
- [ ] Top 2 variants identified as the recommended test pair
- [ ] Meta descriptions are exactly 150-160 characters
- [ ] Test plan includes duration, metric, and implementation steps
- [ ] No two variants use the same opening word
