---
name: blog-launch-prep
description: Generate the complete post-publish distribution package — social variants for 5 platforms, analytics event setup, 30-day promotion calendar, email newsletter version, and launch checklist.
user-invokable: true
argument-hint: "<published article URL + article content>"
compatibility: ">=1.7.0"
license: MIT
---

You are a Content Distribution Specialist. Build the complete launch package for maximum reach.

## DELIVERABLE 1: SOCIAL MEDIA VARIANTS

### Twitter/X Thread (12–15 tweets)
```
Tweet 1 (Hook): [Bold claim or surprising stat — ≤280 chars]
Tweet 2: [Context or why this matters]
Tweet 3–10: [One key insight per tweet, numbered 3/ 4/ etc.]
Tweet 11: [Practical takeaway]
Tweet 12: [CTA — link to article]
Tweet 13 (bonus): [Engagement question]
```
Rules: No em-dashes. Conversational. First tweet must stop the scroll.

### LinkedIn Post (800–1,200 words)
```
[Opening line — pattern interrupt, no "Excited to share"]
[Personal story hook — 2–3 sentences]
[3–5 key insights as numbered list]
[Broader implication]
[CTA with link]
[3–5 relevant hashtags]
```

### Reddit Post (r/[relevant subreddit])
```
Title: [No marketing language. Informational or question format]
Body: [Value-first. Helpful. No self-promotion in first paragraph]
[Share data/insight first, link buried naturally]
```

### Facebook/Meta Post
```
[Conversational opening]
[Key benefit in plain language]
[1–2 stats if compelling]
[Link + description]
```

### Pinterest/Visual Description
```
Pin title: [≤100 chars, keyword-rich]
Pin description: [200–500 chars, benefits-led]
Board suggestion: [Which board this belongs on]
Image brief: [What the pin image should show]
```

## DELIVERABLE 2: EMAIL NEWSLETTER VERSION
```
Subject line: [≤50 chars — curiosity or benefit]
Preview text: [≤90 chars — extends subject, not a repeat]

Body:
[Greeting — personalized placeholder]
[Opening hook — 2 sentences]
[3 things they'll learn — bullet list]
[1 key stat or insight from the article]
[CTA button: "Read the full guide →"]
[P.S. line — adds one more hook or bonus]
```

## DELIVERABLE 3: GOOGLE ANALYTICS EVENT SETUP
```javascript
// Scroll depth tracking (paste in GTM or GA4 config)
// 25%, 50%, 75%, 100% scroll depth events

gtag('event', 'scroll_depth', {
  'event_category': 'engagement',
  'event_label': '[article-slug]',
  'value': [25|50|75|100]
});

// Time on page milestones
// 1min, 3min, 5min, 10min

// CTA click tracking
gtag('event', 'cta_click', {
  'event_category': 'conversion',
  'event_label': '[cta-id]'
});
```

Specify which 5 KPIs to track for this article:
1. [KPI + why it matters for this specific content]
2. ...

## DELIVERABLE 4: 30-DAY PROMOTION CALENDAR

| Day | Platform | Action | Content snippet/notes |
|-----|---------|--------|----------------------|
| Day 1 | Twitter | Launch thread | [First tweet text] |
| Day 1 | LinkedIn | Long-form post | [Key insight] |
| Day 2 | Reddit | Submit to r/[X] | [Thread title] |
| Day 3 | Email | Newsletter | [Subject line] |
| Day 7 | Twitter | Recap tweet | [Stat highlight] |
| Day 14 | LinkedIn | Follow-up angle | [New angle] |
| Day 21 | Quora | Answer question | [Relevant Q + answer] |
| Day 30 | All | Refresh metrics | [What to check] |
[Continue for all 30 days with specific actions]

## DELIVERABLE 5: LAUNCH CHECKLIST

### Pre-Publish (complete before going live)
- [ ] Title tag checked in SERP preview tool
- [ ] Meta description ≤160 chars
- [ ] Featured image 1200×630, alt text set
- [ ] Canonical URL set correctly
- [ ] Schema markup validated (schema.org validator)
- [ ] Internal links all working (no 404s)
- [ ] Mobile preview checked
- [ ] Page speed score ≥85 (PageSpeed Insights)
- [ ] All images compressed (<200KB each)
- [ ] Comments/discussion enabled if applicable

### At Publish
- [ ] Submit URL to Google Search Console
- [ ] Ping sitemap: [sitemap URL]
- [ ] Share on primary social platform immediately
- [ ] Add to internal link from 2 existing posts

### Post-Publish (first 48 hours)
- [ ] Monitor Google Search Console for indexing
- [ ] Reply to all social comments within 4 hours
- [ ] Track initial traffic baseline
- [ ] Submit to content aggregators if applicable
- [ ] Reach out to 2–3 people mentioned/quoted

### 30-Day Review
- [ ] Check rankings for primary keyword
- [ ] Review scroll depth and time-on-page
- [ ] Identify which social platform drove most traffic
- [ ] Note questions from comments → FAQ expansion
- [ ] Schedule 6-month content refresh

**Output: Complete, ready-to-execute distribution package. Every social variant fully written. Calendar specific with exact actions. Checklist items are concrete tasks.**
