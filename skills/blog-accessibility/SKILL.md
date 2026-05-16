---
name: blog-accessibility
description: >
  Audit blog posts for web accessibility compliance (WCAG 2.1 AA). Checks
  heading order, image alt text completeness, color contrast readiness,
  link text quality, reading level, table accessibility, and multimedia
  captions. Returns a pass/fail report with specific fixes. Use when user
  says "accessibility audit", "a11y", "wcag", "screen reader", "alt text
  audit", "accessibility check", "accessible blog".
user-invokable: true
argument-hint: "<file-path>"
license: MIT
---

# Blog Accessibility — WCAG 2.1 AA Audit

Audits blog posts for accessibility compliance against WCAG 2.1 AA criteria
relevant to written content. Produces a pass/fail checklist with specific,
actionable fixes. Covers heading structure, alt text, link quality, reading
level, tables, and media.

## Input Handling

- **File path**: Read a local blog post file
- **URL**: Fetch and audit a published post
- **Directory**: Batch audit all posts in the directory
- **Flags**:
  - `--level [A|AA|AAA]` — WCAG level (default: AA)
  - `--format json|markdown`
  - `--fix` — apply automatic fixes for clear violations (alt text, heading order)

## WCAG 2.1 Criteria Audited

### 1. Heading Structure (WCAG 1.3.1 — Level A)

**Rule**: Headings must follow a logical hierarchy without skipping levels.
Navigating by heading is a primary method for screen reader users.

Checks:
- Exactly one H1 per post (the page title)
- H2 appears before H3 (no H3 without a parent H2)
- H3 appears before H4 (no H4 without a parent H3)
- No heading levels skipped (H1 → H3 with no H2 in between)
- Headings are not used for visual styling (short headings that aren't section labels)

Severity: **Fail** for any skipped level | **Warn** for H1 count ≠ 1

### 2. Image Alt Text (WCAG 1.1.1 — Level A)

**Rule**: All non-decorative images must have descriptive alt text.

Checks:
- Every `![...](url)` or `<img>` tag has a non-empty alt attribute
- Alt text is descriptive: at least 10 characters, not just a filename
- Alt text does not start with "image of" or "photo of" (redundant)
- Alt text is under 125 characters
- Decorative images use `alt=""` (empty alt, not missing alt)
- SVG charts have an accessible title or aria-label

Alt text quality scoring:
- 10+ chars, descriptive, under 125 chars = Pass
- Present but too short (<10 chars) or filename-only = Warn
- Missing entirely on non-decorative image = Fail

### 3. Link Text Quality (WCAG 2.4.4 — Level A)

**Rule**: Link text must describe the destination or purpose without
requiring surrounding context.

Checks:
- No links with text: "click here", "here", "read more", "learn more",
  "this", "link", or raw URLs used as display text
- All links have 3+ word descriptive text
- Links that open in a new tab are indicated (e.g., "(opens in new tab)")

Severity: **Fail** for "click here" / "here" | **Warn** for bare URLs

### 4. Color and Contrast Readiness (WCAG 1.4.3 — Level AA)

**Rule**: Text must have a contrast ratio of at least 4.5:1 against its background.

For blog posts in markdown/MDX:
- Cannot audit rendered contrast ratios without knowing the CSS
- Instead, flag content decisions that commonly cause contrast issues:
  - Inline HTML with hardcoded color attributes (`color: #aaa`, `color: gray`)
  - Light gray text callout boxes in common blog CMS defaults
  - SVG chart text with colors that may be low-contrast in dark mode

Flag as **Warn** with a recommendation to verify contrast in the rendered output.

### 5. Reading Level (WCAG 3.1.5 — Level AAA)

**Rule**: Content requiring reading ability beyond lower secondary education
level should have a simplified summary available.

Checks:
- Calculate Flesch-Kincaid Grade Level for the post body
- If Grade > 9: **Warn** — recommend adding a TL;DR / Key Takeaways box
- If Grade > 12: **Fail** — content significantly above accessibility target
- If a Key Takeaways box is present: credit as partial mitigation

### 6. Table Accessibility (WCAG 1.3.1 — Level A)

**Rule**: Data tables must have header cells that identify the column or row.

Checks:
- Any markdown table must have a header row (row 1 separated by `---`)
- Tables must not be used purely for layout purposes
- Complex tables (merged cells) need a `<caption>` element — flag if present
  in HTML without caption

Severity: **Fail** for tables without header rows

### 7. Language Declaration (WCAG 3.1.1 — Level A)

**Rule**: The page language must be declared.

For posts with frontmatter:
- Does frontmatter include a `lang` or `language` field?
- Warn if absent — the CMS/theme must set `<html lang="...">` correctly

### 8. Audio / Video Captions (WCAG 1.2.2 — Level A)

**Rule**: Pre-recorded audio content in video must have captions.

Checks:
- Any embedded YouTube video: note that captions are YouTube's
  responsibility but recommend auto-captions review
- Any `<audio>` elements: flag if no transcript is provided alongside
- Any video embeds without caption notes: **Warn**

## Process

### Step 1 — Parse Content

Read the post and extract:
- All headings with their levels and order
- All images with alt text (or absence of alt text)
- All links with their display text
- All tables
- All inline HTML (color, style attributes)
- All media embeds (YouTube, audio, video tags)
- Full body text for reading level calculation

### Step 2 — Run All 8 Checks

Apply each check independently and assign Pass / Warn / Fail per check.

### Step 3 — Apply Fixes (if `--fix` flag)

Automatically fix clear violations that don't require human judgement:
- Heading hierarchy: insert missing intermediate heading levels
  (H1 → H3 gap → insert placeholder H2 before the H3, marked `[NEEDS HEADING TEXT]`)
- Empty alt text on non-decorative images: insert `alt="[NEEDS DESCRIPTION]"`
  placeholder to prompt manual completion
- "Click here" link text: replace with `[NEEDS DESCRIPTIVE LINK TEXT]` placeholder
- Do NOT auto-fix: alt text content, reading level, contrast

### Step 4 — Score and Report

Overall accessibility score:
- Count checks: Pass = 2 pts, Warn = 1 pt, Fail = 0 pts
- Max score = 16 pts (8 checks × 2)
- 14-16 = Accessible | 10-13 = Minor Issues | 6-9 = Needs Work | Below 6 = Inaccessible

## Output Format

```markdown
## Accessibility Audit: [Post Title]
**WCAG Level:** AA | **Date:** YYYY-MM-DD
**Accessibility Score:** N/16 — [Accessible/Minor Issues/Needs Work/Inaccessible]

---

### Check Results

| # | Check | WCAG Criterion | Status | Issues Found |
|---|-------|---------------|--------|-------------|
| 1 | Heading Structure | 1.3.1 (A) | ✅ Pass | — |
| 2 | Image Alt Text | 1.1.1 (A) | ❌ Fail | 3 images missing alt |
| 3 | Link Text Quality | 2.4.4 (A) | ⚠️ Warn | 2 "click here" links |
...

---

### Failures (fix before publish)

**Image Alt Text — 3 images missing alt text:**
- Line 45: `![](https://example.com/image.jpg)` — add descriptive alt text
- Line 78: `![](https://example.com/chart.png)` — describe the chart data
- Line 102: `<img src="..." alt="">` — empty alt on non-decorative image

**[other failures]**

---

### Warnings (fix recommended)

**Link Text — 2 non-descriptive links:**
- Line 33: `[click here](url)` → change to descriptive text, e.g., "Download the SEO checklist"
- Line 91: `[here](url)` → describe the destination

**[other warnings]**

---

### Passes

- ✅ Heading structure: correct H1 → H2 → H3 hierarchy throughout
- ✅ Tables: all 2 tables have proper header rows
- ✅ [other passes]
```

## Quality Self-Check

Before returning output, verify:
- [ ] All 8 checks run (none skipped)
- [ ] Each failure includes the exact location (line number or heading name)
- [ ] Fix suggestions are specific (not just "add alt text" but the actual sentence to add)
- [ ] Score calculated correctly (Pass=2, Warn=1, Fail=0)
- [ ] Auto-fixes (if `--fix`) use placeholder markers, not invented content
