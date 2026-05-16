---
name: blog-style
description: >
  Extract and learn a writing style profile from existing blog posts, then
  apply it consistently to new content. Analyzes sentence rhythm, vocabulary
  tier, tone dimensions, contraction frequency, structural patterns, and
  signature phrases. Saves the profile as a reusable persona. Use when user
  says "learn my style", "style learn", "writing style", "match my voice",
  "write like me", "extract voice profile", "brand voice", "author voice".
user-invokable: true
argument-hint: "[directory-or-files] [--apply <file>]"
license: MIT
---

# Blog Style — Author Voice Extraction & Application

Analyzes 5-10 existing blog posts to extract a precise, reproducible writing
style profile. Saves the profile as a persona file and can apply it to new
or existing content via blog-writer.

## Input Handling

- **Directory**: Scan and analyze all blog posts found
- **File list**: Analyze specific files (space-separated paths)
- **Flags**:
  - `--apply <file>` — after learning, apply the style to this file
  - `--save-as <name>` — persona name (default: "author-default")
  - `--min-posts N` — minimum posts needed (default: 5, warn if fewer)
  - `--compare <file>` — score how closely a draft matches the learned style

## What Gets Measured

### Dimension 1 — Sentence Rhythm

- Average sentence length (words per sentence)
- Standard deviation (high SD = varied rhythm, low = monotone)
- Short sentence frequency: % of sentences under 10 words
- Long sentence frequency: % of sentences over 25 words
- Preferred sentence openers: most frequent first words (after stop words)

### Dimension 2 — Vocabulary Tier

Count word frequency across Tier levels:
- **Tier A** (everyday): common words, Flesch-Kincaid Grade 6 and below
- **Tier B** (professional): domain terms, Grade 7-10 vocabulary
- **Tier C** (technical): jargon, Grade 11+ vocabulary, acronyms

Ratio: Tier A% / Tier B% / Tier C%

### Dimension 3 — NNGroup Tone Dimensions (4-axis)

Score each axis 1-10 based on frequency markers:

**Funny ↔ Serious** (1=funny, 10=serious)
- Humor markers: exclamations, self-deprecation, informal comparisons
- Serious markers: formal citations, measured hedging, no exclamations

**Formal ↔ Casual** (1=formal, 10=casual)
- Formal: passive voice, no contractions, third person
- Casual: contractions, direct address ("you"), colloquialisms

**Respectful ↔ Irreverent** (1=respectful, 10=irreverent)
- Irreverent: challenges conventional wisdom, sarcastic asides, blunt claims
- Respectful: hedging language, acknowledges counterarguments

**Enthusiastic ↔ Matter-of-fact** (1=enthusiastic, 10=matter-of-fact)
- Enthusiastic: exclamation marks, superlatives, emotional language
- Matter-of-fact: declarative statements, dry delivery, no hype words

### Dimension 4 — Structural Patterns

- Opening pattern: does the author start with a stat, anecdote, question, or bold claim?
- Paragraph length: average words per paragraph
- H2 style: question-form %, imperative form %, statement form %
- FAQ presence: always / sometimes / never
- Closing pattern: CTA, summary, call-to-action, or open question?

### Dimension 5 — Signature Elements

- Contraction frequency: contractions per 100 words
- First-person frequency: "I", "we", "my" per 100 words
- Rhetorical question frequency: per 500 words
- Filler words to avoid (identified from the author's non-use)
- Signature phrases: 3-5 phrases that appear repeatedly across posts
- Words never used: identify words the author consistently avoids

## Process

### Step 1 — Collect Posts

1. Read all blog post files in the input directory or file list
2. Strip frontmatter, code blocks, and image tags — analyze prose only
3. Warn if fewer than 5 posts found ("Style profiles are more accurate with 5+ posts")

### Step 2 — Measure All Dimensions

For each post, calculate all 5 dimension scores.
Then average across all posts to build the profile.
Note any dimensions with high variance (inconsistent = don't hard-code).

### Step 3 — Build the Style Profile

Produce a structured profile object with:
- All dimension scores and ranges
- Signature phrases list
- Avoid words list
- Structural pattern preferences
- Example sentences (one per dimension, drawn from the actual posts)

### Step 4 — Save as Persona File

Save to `personas/[name].md` in the repo:

```markdown
---
name: [save-as name]
source-posts: N
generated: YYYY-MM-DD
---

# Writing Style Profile: [name]

## Tone Axes (NNGroup 4-Dimension)
- Funny ↔ Serious: N/10
- Formal ↔ Casual: N/10
- Respectful ↔ Irreverent: N/10
- Enthusiastic ↔ Matter-of-fact: N/10

## Sentence Rhythm
- Average length: N words
- Rhythm variety (SD): N (high/medium/low)
- Short sentence rate: N%
- Long sentence rate: N%

## Vocabulary
- Tier mix: A: N% / B: N% / C: N%
- Readability target: Flesch-Kincaid Grade N-N

## Structural Patterns
- Opening style: [stat/anecdote/question/bold claim]
- H2 style: [question N% / imperative N% / statement N%]
- Avg paragraph length: N words
- Contraction rate: N per 100 words
- First-person rate: N per 100 words
- Rhetorical question rate: N per 500 words

## Signature Phrases
- "[phrase 1]"
- "[phrase 2]"
...

## Avoid These Words/Patterns
- [word or phrase the author never uses]
...

## Example Sentences (Reference)
- Short: "[actual sentence from posts]"
- Long: "[actual sentence from posts]"
- Opener style: "[actual opener from posts]"
```

### Step 5 — Apply to File (if `--apply` flag)

Pass the persona to blog-writer agent with the target file.
The agent will rewrite the content to match the extracted style
without changing the information or facts.

### Step 6 — Compare Mode (if `--compare` flag)

Score the given draft against the extracted profile:
- Measure all 5 dimensions on the draft
- Calculate deviation from the profile per dimension
- Return a style match score (0-100%) with specific deviation notes

## Output Format

```markdown
## Style Profile: [name]

**Posts Analyzed:** N
**Generated:** YYYY-MM-DD

### Tone Summary
[NNGroup 4-axis scores with one-line interpretation each]

### Rhythm & Vocabulary
[sentence stats + tier mix]

### Structural Patterns
[opening, paragraph, H2, closing patterns]

### Signature Elements
[signature phrases, contraction rate, first-person rate]

### What to Avoid
[words/patterns from avoid list]

---

**Profile saved to:** `personas/[name].md`
**To apply:** `/blog style apply [name] [file]`
**To compare a draft:** `/blog style compare [name] [draft-file]`
```

## Quality Self-Check

Before returning output, verify:
- [ ] All 5 dimensions measured and averaged across all posts
- [ ] Minimum post count warning shown if fewer than 5 posts
- [ ] NNGroup 4-axis scores all present
- [ ] Signature phrases drawn from actual post text (not invented)
- [ ] Persona file saved to `personas/[name].md`
- [ ] High-variance dimensions flagged (not hard-coded in profile)
