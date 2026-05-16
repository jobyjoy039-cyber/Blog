---
name: blog-podcast-brief
description: >
  Generate a full podcast episode brief from a blog post. Produces a complete
  production-ready brief including episode summary, guest talking points,
  chapter timestamps, host questions, show notes, and promotional copy.
  Distinct from blog-audio (which generates audio narration). Use when user
  says "podcast brief", "podcast episode", "podcast from blog", "episode
  brief", "podcast outline", "podcast show notes", "turn blog into podcast".
user-invokable: true
argument-hint: "<file-path>"
license: MIT
---

# Blog Podcast Brief — Episode Production Brief Generator

Transforms a blog post into a production-ready podcast episode brief.
Covers everything a host and producer need: narrative arc, chapter map,
host questions, guest talking points, and show notes — ready to hand to
a podcast team or record solo.

## Input Handling

- **File path**: Read a blog post and build a full episode brief
- **Flags**:
  - `--format [solo|interview|panel]` — episode format (default: solo)
  - `--duration [15|30|45|60]` — target runtime in minutes (default: 30)
  - `--style [educational|conversational|debate|storytelling]` — default: educational
  - `--guest-angle <topic>` — specific guest expertise to frame around (for interview format)

## Episode Formats

### Solo Format
Host reads and discusses the blog post content with commentary.
- Narrative arc: hook → problem → insight → method → takeaway
- No guest questions needed
- 30-minute target = 5,000 words of spoken content at 150 words/min

### Interview Format
Host interviews a guest expert on the blog post topic.
- Host needs: intro script, 8-12 questions, transition lines, closing script
- Guest needs: talking points brief (1-pager) — what to cover, what to avoid
- The blog post's data is the guest's primary reference material

### Panel Format
Host facilitates discussion between 2-3 guests.
- Host needs: intro, 6-8 discussion questions, conflict/debate prompts, wrap script
- Each guest gets a different angle/position brief
- Designed for 45-60 minutes

## Duration-to-Content Mapping

| Duration | Spoken Words | Chapters | Questions |
|----------|-------------|---------|----------|
| 15 min | ~2,250 words | 3-4 | 5-6 |
| 30 min | ~4,500 words | 5-6 | 8-10 |
| 45 min | ~6,750 words | 7-8 | 10-12 |
| 60 min | ~9,000 words | 8-10 | 12-15 |

## Process

### Step 1 — Map Blog Post to Episode Structure

1. Read the post fully
2. Extract: key claim, 3 core insights, 3-5 statistics, primary example or case study
3. Identify the narrative arc:
   - What's the tension or problem? (Episode hook)
   - What's the key insight that resolves it? (Episode spine)
   - What should a listener do differently after listening? (Takeaway)
4. Map each H2 section to a chapter slot

### Step 2 — Write the Episode Brief

#### Hook Script (first 60 seconds)
Write the exact words the host opens with. Formula:
1. One sentence stating the surprising claim or problem (from post intro)
2. One sentence on why it matters now
3. One sentence previewing what the listener will learn
4. "Let's get into it." or natural equivalent

#### Chapter Map with Timestamps

Based on `--duration`, divide the episode into chapters:

```
Chapter 1: [title] — [start timestamp] to [end timestamp] (~N min)
Summary: [2-sentence description of what this chapter covers]
Key point: [the one thing to land in this chapter]
Source stat: [stat from the blog post to cite]
```

#### Host Questions (for interview/panel format)

Write 2 question categories:

**Opening questions** (build context, warm up guest):
- "Tell us how you first came across this problem..."
- "For listeners who aren't familiar with [term], how would you explain it?"

**Depth questions** (drawn directly from H2 sections):
- One question per major section of the blog post
- Phrased to elicit a specific story or data point, not a yes/no
- Include a follow-up prompt per question: "And what surprised you most about that?"

**Challenge questions** (create productive tension for panel format):
- "Some people argue the opposite — that [counterargument]. How do you respond?"
- "Is there a scenario where your approach doesn't work?"

#### Guest Talking Points Brief (for interview/panel format)

A 1-page brief the guest receives before recording:

```markdown
# Guest Brief: [Episode Title]
Host: [host name] | Show: [show name] | Recording: [date/TBD]

## Episode Focus
[2-sentence summary of what the episode is about]

## Your Angle
[1-sentence description of the specific perspective you bring]

## Key Points to Cover
- [point 1 from the blog post the host wants you to address]
- [point 2]
- [point 3]

## Stats You May Be Asked About
- [stat from post] — Source: [source name]
- [stat from post] — Source: [source name]

## What to Avoid
- [anything outside the episode scope]
- [competitor mentions if applicable]

## Prep Questions (for your thinking, not asked on air)
- What's your most surprising experience with [topic]?
- What's the biggest mistake you see people make with [topic]?
```

#### Closing Script (last 60-90 seconds)

Host closing formula:
1. One-sentence recap of the core takeaway
2. One actionable step the listener can take today
3. Where to find the show notes (with blog post link)
4. Subscribe / review ask (natural, not pushy)
5. Sign-off

### Step 3 — Write Show Notes

Show notes are published alongside the episode (blog post or podcast platform):

Structure:
1. **Episode summary** (150-200 words): standalone description for non-listeners
2. **Key takeaways** (3-5 bullet points)
3. **Resources mentioned** (links to stats sources, tools mentioned)
4. **Chapters** (timestamp links)
5. **Guest bio** (2-3 sentences, for interview/panel format)
6. **Full blog post link**

### Step 4 — Write Promotional Copy

**Twitter/X thread**: 5-tweet thread announcing the episode  
**LinkedIn post**: 500-word post with the episode's core insight  
**Email newsletter blurb**: 100-word episode intro for subscriber digest

## Output Format

```markdown
## Podcast Episode Brief: [Post Title]

**Format:** Solo / Interview / Panel  
**Target Duration:** N minutes  
**Style:** Educational / Conversational / etc.

---

### Hook Script (0:00–1:00)
[exact host words]

---

### Chapter Map

| Chapter | Title | Timestamp | Duration | Key Point |
|---------|-------|-----------|----------|----------|
| 1 | [title] | 0:00–N:00 | N min | [key point] |
...

---

### Host Questions ([N] total)

**Opening (2)**
1. [question]
2. [question]

**Depth (N)**
[one per chapter/H2 section]

**Challenge (2, panel format)**
[challenge questions]

---

### Guest Brief
[1-page guest brief]

---

### Closing Script
[exact host words]

---

### Show Notes
[full show notes]

---

### Promotional Copy

**Twitter/X Thread:**
[5 tweets]

**LinkedIn Post:**
[500-word post]

**Email Blurb:**
[100-word blurb]
```

## Quality Self-Check

Before returning output, verify:
- [ ] Chapter timestamps add up to the target duration
- [ ] Each chapter has a key point that maps to a specific H2 in the post
- [ ] All depth questions are open-ended (not yes/no)
- [ ] Guest brief is 1 page or under
- [ ] Show notes include all resource links from the blog post
- [ ] Hook and closing scripts are complete word-for-word, not summaries
- [ ] Promotional copy covers all 3 channels
