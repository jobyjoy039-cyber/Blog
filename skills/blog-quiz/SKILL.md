---
name: blog-quiz
description: >
  Generate interactive quiz content from a blog post to boost engagement,
  dwell time, and lead capture. Produces 5-10 questions with answer options,
  explanations, score logic, and embeddable HTML output. Use when user says
  "blog quiz", "add quiz", "quiz from post", "interactive quiz", "knowledge
  check", "engagement quiz", "quiz content", "generate quiz".
user-invokable: true
argument-hint: "<file-path>"
license: MIT
---

# Blog Quiz — Interactive Engagement Content Generator

Generates quiz content from a blog post's key concepts and facts.
Outputs question sets with answer options, explanations, and scoring logic,
plus embeddable HTML/JavaScript for direct CMS use.

## Input Handling

- **File path**: Read and extract quiz-able facts from the post
- **Flags**:
  - `--questions N` — number of questions (default: 7, range: 5-10)
  - `--type [knowledge|assessment|personality]` — default: knowledge
  - `--difficulty [beginner|intermediate|advanced|mixed]` — default: mixed
  - `--format [html|markdown|json]` — default: markdown
  - `--lead-capture` — add an email capture gate before showing results

## Quiz Types

### Knowledge Quiz
Tests recall and comprehension of post content.
- Questions drawn from the post's statistics, definitions, and key claims
- 4 answer options (1 correct, 3 plausible distractors)
- Each question tied to a specific section of the post
- Wrong answers link back to the relevant section for re-reading

### Assessment Quiz
Evaluates the reader's current situation or skill level.
- Questions are diagnostic ("How often do you...?", "Which describes your...?")
- No right/wrong answers — responses map to outcome profiles
- Results segment readers: Beginner / Intermediate / Advanced
- Each result tier gets a personalized recommendation (which posts to read next)

### Personality Quiz
Categorizes readers into archetypes related to the post topic.
- "What type of blogger are you?" style
- Light, shareable format optimized for social sharing
- 4 result types, each with a descriptor and a recommended next step

## Question Construction Rules

### For Knowledge Questions
- Stem: a direct question or incomplete statement about a fact from the post
- Correct answer: exact or paraphrased from the post
- Distractors: plausible alternatives from the same topic domain (not obviously wrong)
- Explanation (shown after answer): 1-2 sentences with the correct reasoning
- Difficulty tagging: Beginner / Intermediate / Advanced per question

### Question Stem Rules
- Start with: What / How / Which / When / Why / True or False
- Under 20 words in the stem
- One concept per question — no compound questions
- Avoid: "According to the article..." (relies on memory, not understanding)

### Answer Option Rules
- All 4 options approximately the same length
- No "All of the above" or "None of the above"
- Correct answer randomly placed (not always A)
- Distractors must be factually wrong, not just less correct

## Process

### Step 1 — Extract Quiz-able Facts

Read the post and identify:
- Statistics (any number + claim = potential question)
- Definitions (any "X is..." or "X means..." statement)
- Process steps (numbered or ordered lists)
- Comparisons (any "X vs Y" or "better/worse than" statement)
- Key terminology (domain-specific words defined in the post)

Minimum: extract 15+ fact candidates, then select the best N for the quiz.

### Step 2 — Select and Balance Questions

Select questions to cover:
- At least 3 different H2 sections of the post
- At least 1 stat-based question
- At least 1 definition or concept question
- At least 1 process or how-to question
- A difficulty mix matching the `--difficulty` flag

### Step 3 — Write Questions and Answers

For each selected fact:
1. Write the question stem
2. Write the correct answer (20-40 words)
3. Write 3 distractors (same length as correct answer)
4. Write the explanation (shown after submission)
5. Tag difficulty and source section

### Step 4 — Build Scoring Logic

For Knowledge quizzes:
- 7 correct = "Expert — you've mastered this topic"
- 5-6 correct = "Advanced — strong understanding with a few gaps"
- 3-4 correct = "Intermediate — good foundation, some areas to review"
- 0-2 correct = "Beginner — read the full post to build your knowledge"

Each score band includes: label, 1-sentence encouragement, and a CTA
(read post again / read related post / subscribe for more).

### Step 5 — Generate Output

**Markdown format**: question-and-answer blocks for manual embed  
**JSON format**: structured data for quiz plugins (WP Quiz, Typeform import)  
**HTML format**: self-contained `<div>` with inline JavaScript — no dependencies

For HTML format, generate a clean, dark-mode-compatible quiz widget:
- Progress bar (Question N of N)
- One question visible at a time
- Answer selection highlights correct/incorrect immediately
- Explanation appears after answer
- Final score screen with band label and CTA
- No external CDN dependencies (all inline)

### Step 6 — Lead Capture Gate (if `--lead-capture`)

Add an email input screen before showing the final score:
- "Enter your email to see your results and get [topic] tips weekly"
- Input: email field + submit button
- If skipped: still shows results (don't gate the UX punitively)
- On submit: show results + trigger a confirmation message
- Note: actual email collection requires connecting to a form backend

## Output Format

```markdown
## Quiz: [Post Title]

**Type:** Knowledge | **Questions:** N | **Difficulty:** Mixed

---

### Question 1 (Beginner)

[Question stem]

A) [option]
B) [option — correct]
C) [option]
D) [option]

**Correct Answer:** B  
**Explanation:** [1-2 sentence explanation with source reference]  
**Source Section:** [H2 heading in the post]

---

[repeat for all questions]

---

### Scoring Guide

| Score | Band | Message | CTA |
|-------|------|---------|-----|
| 7/7 | Expert | [message] | [CTA] |
...

---

### Embeddable HTML

\`\`\`html
[self-contained quiz widget HTML]
\`\`\`
```

## Quality Self-Check

Before returning output, verify:
- [ ] Questions cover at least 3 different H2 sections
- [ ] No two questions test the exact same fact
- [ ] All distractors are plausible (not obviously wrong)
- [ ] Correct answers are randomly distributed across A/B/C/D
- [ ] Every question has an explanation
- [ ] Scoring bands have a label, message, and CTA
- [ ] HTML output is self-contained with no external CDN dependencies
