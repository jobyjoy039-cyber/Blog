---
name: blog-glossary
description: >
  Build a topic glossary from terminology used across all blog posts.
  Extracts domain-specific terms, generates definitions, groups by topic
  cluster, and outputs a linkable glossary page. Boosts E-E-A-T and topical
  authority. Use when user says "glossary", "build glossary", "term
  definitions", "topic glossary", "terminology page", "jargon guide",
  "knowledge base terms", "define terms".
user-invokable: true
argument-hint: "[directory]"
license: MIT
---

# Blog Glossary — Topic Terminology Extractor & Definition Generator

Scans all blog posts to extract domain-specific terminology, generates
clear definitions for each term, groups by topic cluster, and outputs a
complete, linkable glossary page. Strengthens E-E-A-T signals and internal
linking opportunities.

## Input Handling

- **Directory**: Scan all blog post files (default: current directory)
- **Single file**: Extract terms from one post only
- **Flags**:
  - `--min-frequency N` — only include terms appearing in N+ posts (default: 2)
  - `--clusters` — group terms by topic cluster
  - `--format markdown|html|json`
  - `--output <file>` — save glossary to this file (default: `glossary.md`)
  - `--link` — add `[term](#term)` anchors and back-link the terms in all posts

## What Gets Extracted

### Term Types

1. **Domain jargon**: field-specific terms unlikely to appear in general text
   (e.g., "E-E-A-T", "topical authority", "featured snippet", "dwell time")

2. **Acronyms and initialisms**: any all-caps word 2-6 characters long
   that appears in context (e.g., GSC, CWV, CTR, SXO, GEO, AEO)

3. **Defined terms**: any phrase that appears after "is", "refers to",
   "means", "is defined as", or in quotation marks as a label

4. **Technical concepts**: multi-word noun phrases that appear repeatedly
   and are specific to the niche (e.g., "content decay", "semantic cluster",
   "citation capsule", "answer-first formatting")

### What to Skip

- Common English words (even if used in a technical sense — context filters these)
- Proper nouns that are just brand names without a definition
- Terms that appear in only 1 post and `--min-frequency` is 2+
- Pure stop words, prepositions, and auxiliary verbs

## Process

### Step 1 — Scan Posts and Extract Candidates

For each blog post file:
1. Read the body (strip frontmatter, code blocks, URLs)
2. Extract: all-caps acronyms, domain noun phrases, in-context definitions
3. Track frequency: how many posts each term appears in
4. Track context: record 1-2 sentences of context per term per post

### Step 2 — Filter and Deduplicate

1. Remove terms below `--min-frequency` threshold
2. Merge variations: "featured snippet" and "Featured Snippet" → one entry
3. Group acronyms with their expansions (detect "Search Console (GSC)" patterns)
4. Flag terms where the author provided an inline definition — use that definition

### Step 3 — Generate Definitions

For each term:

1. Check if the author defined it inline anywhere — use that definition verbatim
2. If no inline definition exists, write a concise definition:
   - 20-50 words
   - Plain English, accessible to a reader new to the topic
   - Include what it is, why it matters, and one example if space allows
   - Add a "Related terms:" line with 2-3 linked cross-references

### Step 4 — Group by Topic Cluster (if `--clusters`)

Map terms to topic clusters based on which posts they appear in.
If blog-cluster or blog-strategy has been run and cluster definitions exist
in `competitors/matrix.md` or `cluster.json`, use those definitions.
Otherwise, group by shared co-occurrence across posts.

### Step 5 — Build the Glossary Page

Alphabetical index at the top:
`A | B | C | D | E | F | G | H | I | J | K | L | M | N | O | P | Q | R | S | T | U | V | W | X | Y | Z`

For each letter section, list terms alphabetically with:
- Term as an anchor-linked H3 (`### term {#term}`)
- Definition paragraph
- "Used in: [post title links]" — back-references to source posts
- "Related: [cross-linked terms]"

### Step 6 — Back-Link Terms in Posts (if `--link`)

For each term in the glossary:
1. Scan all blog post files for the first occurrence of the term per post
2. Wrap the first occurrence with a link to `glossary.md#term`
3. Do not link subsequent occurrences in the same post (one link per term per post)
4. Write modified post files (ask for confirmation before writing)

### Step 7 — Generate Schema Markup

Produce a `DefinedTermSet` JSON-LD block for the glossary page:

```json
{
  "@context": "https://schema.org",
  "@type": "DefinedTermSet",
  "name": "[Blog Name] Glossary",
  "description": "Definitions of key terms used in [Blog Name]",
  "hasDefinedTerm": [
    {
      "@type": "DefinedTerm",
      "name": "[term]",
      "description": "[definition]",
      "inDefinedTermSet": "[glossary-url]"
    }
  ]
}
```

## Output Format

```markdown
## Glossary Build Report

**Posts Scanned:** N
**Terms Extracted:** N (before frequency filter)
**Terms in Glossary:** N (after filter: min-frequency N+)
**Glossary File:** [output path]

---

### Term Frequency Table (Top 20)

| Term | Posts | Cluster | Has Inline Def |
|------|-------|---------|----------------|
| [term] | N | [cluster] | Yes/No |

---

### Glossary Preview (first 5 entries)

[A-Z index preview]

---

**Full glossary saved to:** `[output file]`
**Schema markup:** included in glossary file footer
**Back-links added:** N links across N posts (if --link flag)
```

## Glossary File Format

```markdown
# [Blog Name] Glossary

A complete reference of terms used across [Blog Name] content.

[A](#a) | [B](#b) | ... | [Z](#z)

---

## A {#a}

### Answer-First Formatting {#answer-first-formatting}

A content structure where each major section (H2) opens with a 40-60 word
paragraph that directly answers the heading's implied question and includes
at least one sourced statistic. Improves featured snippet eligibility and
AI citation readiness.

**Related:** [Featured Snippet](#featured-snippet), [Citation Capsule](#citation-capsule)  
**Used in:** [Post Title 1](../path/post1.md), [Post Title 2](../path/post2.md)

---
[continues alphabetically]
```

## Quality Self-Check

Before returning output, verify:
- [ ] Terms below minimum frequency filtered out
- [ ] All acronyms expanded (e.g., GSC → Google Search Console)
- [ ] Author inline definitions used where they exist
- [ ] Every definition is 20-50 words
- [ ] Alphabetical index links work (anchor format matches headers)
- [ ] "Used in" links reference real posts that contain the term
- [ ] DefinedTermSet JSON-LD schema block included
- [ ] Back-link modifications confirmed with user before writing if `--link`
