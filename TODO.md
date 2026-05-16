# TODO - claude-blog Roadmap

## Phase 4 (Future)
- [ ] MCP integrations (Ahrefs, Semrush) — live keyword difficulty + backlink data
- [ ] blog-sxo: DataForSEO integration for live SERP feature data (current uses WebSearch)
- [ ] blog-ab: GSC integration for real CTR comparison between headline variants
- [ ] blog-keyword-research: integrate with blog-google for verified volume data
- [ ] blog-dashboard: scheduled auto-refresh (cron or GitHub Actions trigger)
- [ ] blog-publisher: Webflow nested reference fields support
- [ ] blog-publisher: Contentful asset upload (images) before entry creation
- [ ] blog-drift: GitHub Actions workflow to run drift check on PR
- [ ] blog-cluster: cluster-map.html auto-inject CLUSTER_DATA from blog-cluster output
- [ ] Multilingual keyword research (blog-keyword-research --locale support)

## Completed

### v1.9.0 (current)
- [x] 3 new skills: blog-keyword-research, blog-drift, blog-dashboard
- [x] `skills/blog-cluster/templates/cluster-map.html` — interactive force-directed cluster map
- [x] `tests/test_new_skills.py` — 60+ assertions covering all 12 Phase 2+3 skills
- [x] `tests/test_new_agents.py` — 50+ assertions covering all 10 new agents
- [x] blog-publisher: Webflow CMS support (REST API v2, Rich Text JSON)
- [x] blog-publisher: Contentful CMS support (Content Management API, publish flow)
- [x] blog-analyst: trend comparison between consecutive monthly reports
- [x] TODO.md updated with Phase 4 roadmap

### v1.8.0
- [x] 9 new skills: blog-ab, blog-decay, blog-style, blog-sxo, blog-email-sequence, blog-quiz, blog-glossary, blog-accessibility, blog-podcast-brief
- [x] 5 new orchestration agents: blog-editor, blog-publisher, blog-strategist, blog-analyst, blog-localizer
- [x] Pre-commit quality gate (scripts/pre_commit_check.py)
- [x] Folder scaffolds: competitors/, outreach/, repurposed/, email-sequences/, personas/, performance/, publish/, translations/
- [x] docs/COMMANDS.md fully updated
- [x] Content decay detection, writing style learning, A/B headline testing

### v1.7.1 (2026-04-27)
- [x] Security audit — 39 findings closed (1 CRITICAL, 5 HIGH, 14 MEDIUM, 11 LOW, 8 INFO)
- [x] VULN-001: Credential at-rest (MCP API key no longer committed)
- [x] Hash-pinned lock files for all 4 pip manifests
- [x] SHA-pinned GitHub Actions

### v1.7.0
- [x] Multi-language content support — blog-multilingual + blog-translate + blog-localize + blog-locale-audit
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
