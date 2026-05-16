---
name: blog-email-sequence
description: >
  Convert a blog post or topic cluster into a multi-part email drip sequence.
  Generates 5-7 email episodes with subject lines, preview text, full body
  copy, and CTAs. Each email stands alone but builds on the previous one.
  Use when user says "email sequence", "email drip", "email campaign",
  "blog to email", "nurture sequence", "email series", "convert blog to email".
user-invokable: true
argument-hint: "<file-path-or-cluster-directory>"
license: MIT
---

# Blog Email Sequence — Blog-to-Drip Converter

Transforms a blog post or topic cluster into a 5-7 part email drip sequence.
Each email is platform-ready with subject line, preview text, body copy, and
a single CTA. The sequence builds narrative momentum across episodes.

## Input Handling

- **Single blog post**: Extract core insights and build a 5-email sequence
- **Cluster directory**: Map multiple posts to a longer 7-email sequence
- **Topic string**: Generate a sequence from scratch on a given topic
- **Flags**:
  - `--emails N` — number of emails (default: 5, max: 7)
  - `--interval [daily|every-2-days|weekly]` — send cadence (default: every-2-days)
  - `--tone [educational|conversational|direct]` — default: educational
  - `--goal [nurture|convert|re-engage]` — default: nurture

## Sequence Architecture

### For a Single Post (5 emails)

| Email | Name | Purpose | Source Content |
|-------|------|---------|----------------|
| 1 | The Hook | Tease the problem, earn trust | Post intro + key stat |
| 2 | The Problem | Deepen the pain point | Post's first 2 H2 sections |
| 3 | The Insight | The core lesson or finding | Post's middle sections |
| 4 | The Method | Actionable steps | Post's how-to / tactical sections |
| 5 | The CTA | Drive action | Post's conclusion + CTA |

### For a Cluster (7 emails)

| Email | Name | Purpose | Source |
|-------|------|---------|--------|
| 1 | The Hook | Big picture problem statement | Pillar post intro |
| 2 | Why It Matters | Stakes and consequences | Pillar post section |
| 3 | Deep Dive 1 | First cluster subtopic | Cluster post 1 |
| 4 | Deep Dive 2 | Second cluster subtopic | Cluster post 2 |
| 5 | Deep Dive 3 | Third cluster subtopic | Cluster post 3 |
| 6 | Synthesis | Bring it all together | Pillar post conclusion |
| 7 | The CTA | Drive conversion or re-engagement | Offer or next step |

## Email Construction Rules

### Subject Lines
- Under 50 characters
- Must pass the "inbox curiosity" test: does it earn an open without the body?
- No spam trigger words: "free", "guarantee", "click here", "limited time"
- Styles: benefit-driven, curiosity gap, question, number-led

### Preview Text
- 80-100 characters
- Extends the subject line — does not repeat it
- Completes the thought or adds a secondary hook

### Body Copy Structure
1. **Opening hook** (1-2 sentences): pull from the subject line tension
2. **Bridge** (1-2 sentences): connect to the reader's situation
3. **Core value block** (3-5 short paragraphs or a bulleted list): the actual content
4. **Transition** (1 sentence): hint at the next email to build anticipation
5. **CTA** (1 sentence + link): single, specific ask
6. **P.S.** (optional): a stat, quote, or curiosity hook for low-engagement readers

### Body Copy Rules
- Plain text that also renders well as HTML
- Short paragraphs: 2-4 lines maximum
- No images in first 2 emails (deliverability)
- One CTA per email — never two
- Under 300 words per email (sweet spot for open-to-click ratio)
- Use "you" not "readers" — write to one person

### CTA Types by Goal

| Goal | CTA Type | Example |
|------|---------|---------|
| Nurture | Read the full post | "Read the full breakdown →" |
| Convert | Start / sign up / buy | "Start your free trial →" |
| Re-engage | Reply / take a quick action | "Reply with your biggest challenge" |

## Process

### Step 1 — Extract Content Map

1. Read the source post(s)
2. Build a content map: list of insights, stats, and takeaways in order
3. Identify the single most compelling stat (use in Email 1)
4. Identify the most actionable section (use in Email 4)
5. Identify the strongest CTA from the post (use in Email 5)

### Step 2 — Write Each Email

Follow the sequence architecture above. Write each email in order — earlier
emails inform the framing of later ones.

For each email:
1. Draft subject line (5 variants, pick the best)
2. Write preview text (paired with chosen subject)
3. Write body copy following the 6-part structure
4. Write or confirm the CTA
5. Add optional P.S. if email is < 200 words (fill the value gap)

### Step 3 — Build Delivery Schedule

Based on `--interval` flag, generate a send schedule table:

```
Email 1 → Day 0 (immediate after signup)
Email 2 → Day 2
Email 3 → Day 4
...
```

### Step 4 — Export

Save each email to `email-sequences/[post-slug]/email-N.md`

## Output Format

```markdown
## Email Sequence: [Post Title / Topic]
**Emails:** N | **Cadence:** every N days | **Goal:** [nurture/convert/re-engage]

### Delivery Schedule
| Email | Name | Send Day | Subject Line |
|-------|------|---------|-------------|
| 1 | The Hook | Day 0 | [subject] |
...

---

## Email 1 — The Hook

**Subject:** [subject line]
**Preview:** [preview text]
**Send Day:** 0 (immediate)

---

[email body]

---
**CTA:** [CTA text] → [url or placeholder]

**P.S.** [optional P.S. line]

---

## Email 2 — The Problem
...
```

## Quality Self-Check

Before returning output, verify:
- [ ] All emails under 300 words
- [ ] Each subject line under 50 characters
- [ ] Preview text does not repeat the subject line
- [ ] Each email has exactly one CTA
- [ ] Transition sentence at end of emails 1-4 teases the next email
- [ ] No spam trigger words in any subject line
- [ ] Files saved to `email-sequences/[post-slug]/`
- [ ] Delivery schedule table complete
