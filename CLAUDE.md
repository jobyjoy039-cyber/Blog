# Repository overview

This repository hosts a few independent subprojects:

- `video-pipeline/` — an autonomous AI video editing pipeline, orchestrated
  by Claude Code, that coordinates video-use, Remotion, WhisperX, and
  several audio/asset-generation repos into a modular stage-by-stage
  workflow. See `video-pipeline/ARCHITECTURE.md` for the design and
  `video-pipeline/CLAUDE.md` for run instructions; its director subagents
  live in `.claude/agents/`.
- `package.json` (n8n-on-render) — an n8n instance configuration, unrelated
  to the video pipeline.

When working on the video pipeline, treat `video-pipeline/CLAUDE.md` as the
authoritative run order and `.claude/agents/*.md` as the single-responsibility
stages — don't call the underlying video/audio/image repos directly from a
top-level prompt.
