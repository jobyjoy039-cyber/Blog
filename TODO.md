# TODO - claude-blog Roadmap

## Phase 3 (Next)
- [ ] MCP integrations (Ahrefs, Semrush)
- [ ] Automated A/B title testing via analytics integration (connect blog-ab to GSC data)
- [ ] Content performance dashboard (aggregate scores, traffic, citations)
- [ ] `blog-sxo` skill — DataForSEO decoupling for live SERP data (current version uses WebSearch)
- [ ] `blog-drift` skill (clean-room baseline + diff for blog content over time; original submission rejected for hardcoded API key)
- [ ] `skills/blog-cluster/templates/cluster-map.html` reference template (skill currently generates from spec each invocation)
- [ ] Tests for new skills (blog-ab, blog-decay, blog-style, blog-sxo, blog-email-sequence, blog-quiz, blog-glossary, blog-accessibility, blog-podcast-brief)
- [ ] Tests for new agents (blog-editor, blog-publisher, blog-strategist, blog-analyst, blog-localizer)
- [ ] blog-ab integration with GSC (live CTR data for variant comparison)
- [ ] blog-analyst trend comparison (compare consecutive monthly reports)
- [ ] blog-publisher Webflow and Contentful CMS support

## Completed

### v1.8.0 (current)
- [x] 9 new skills: blog-ab, blog-decay, blog-style, blog-sxo, blog-email-sequence, blog-quiz, blog-glossary, blog-accessibility, blog-podcast-brief
- [x] 5 new orchestration agents: blog-editor, blog-publisher, blog-strategist, blog-analyst, blog-localizer
- [x] Pre-commit quality gate (`scripts/pre_commit_check.py`)
- [x] Folder scaffolds: competitors/, outreach/, repurposed/, email-sequences/, personas/, performance/, publish/, translations/
- [x] `docs/COMMANDS.md` fully updated with all commands including v1.7.0 additions and new v1.8.0 commands
- [x] Content decay detection (`/blog decay` - age, stat freshness, reference currency, GSC trend)
- [x] Writing style learning (`/blog style learn` - NNGroup 4-axis, sentence rhythm, vocabulary tier)
- [x] A/B title testing variants (`/blog ab` - 5 headline angles, CTR scoring, meta pairs)

### v1.7.1 (2026-04-27)
- [x] Security audit — 39 findings closed (1 CRITICAL, 5 HIGH, 14 MEDIUM, 11 LOW, 8 INFO)
- [x] VULN-001: Credential at-rest (MCP API key no longer committed)
- [x] Hash-pinned lock files for all 4 pip manifests
- [x] SHA-pinned GitHub Actions

### v1.7.0
- [x] Multi-language content support (i18n, hreflang generation) — blog-multilingual + blog-translate + blog-localize + blog-locale-audit
- [x] FLOW framework integration (blog-flow + scripts/sync_flow.py)
- [x] Semantic topic-cluster planning + execution (blog-cluster)
- [x] Mechanical security guardrails (tests/test_security_guardrails.py)
- [x] 5 new capability agents: blog-outreach, blog-repurposer, blog-monetizer, blog-competitor, blog-qa

### v1.6.x
- [x] CI/CD workflows (.github/workflows/ci.yml)
- [x] Google Search Console and PageSpeed Insights (blog-google)
- [x] Plugin marketplace submission (marketplace.json)
- [x] Image generation via AI (blog-image with Gemini)
- [x] Podcast/audio repurposing (blog-audio with Gemini TTS)
