# video-pipeline — orchestrator instructions

This directory is driven by Claude Code acting as the **master orchestrator**
of the AI video pipeline described in `ARCHITECTURE.md`. Read that file for
the full design and JSON contracts before running the pipeline.

## Run order

Given `project/input/transcript.txt` (+ optional `narration.wav`,
`face.jpg`), invoke the director subagents (`../.claude/agents/*.md`) via
the Agent tool in this order. Pass no free-form context between them beyond
"run against `project/timeline/...`" — each director reads its own input
file(s) per its definition. Don't call the underlying repos (video-use,
WhisperX, ComfyUI, etc.) directly yourself; always go through the
responsible director so the JSON contracts stay the source of truth.

1. `script-director` → `project/timeline/scenes.json`
2. `storyboard-director` → `project/timeline/shots.json`
3. In parallel: `asset-finder`, `image-generator`, `animation-director`,
   `audio-director` (which itself sequences `music-director`,
   `foley-director`, `subtitle-director`)
4. `broll-planner` — reconciles Asset Finder + Image Generator output
5. `remotion-builder` — assembles the composition, then hands off to
   `video-use` for the actual edit/render into `project/renders/`
6. `qa-director` — reviews the render

   - `pass: true` → continue to step 7
   - `pass: false` → re-run only the specific director(s) named in each
     issue's `agent` field, then re-render (step 5) and re-run QA. Don't
     restart the whole pipeline.
7. `render-director` → final deliverables in `project/output/`

## Ground rules

- Every handoff between directors is a file under `project/timeline/` or
  `project/assets/`, validated against `schemas/*.schema.json`. If a
  director's output doesn't match its schema, that's a bug in that stage —
  fix the stage, don't hand-patch the JSON downstream.
- A director that can't resolve something (missing asset, ambiguous
  decision) should say so and stop, not guess silently into the manifest.
- External repos are not vendored here; each director's Bash-invoked tool
  calls assume that repo/service is available in this environment. If it
  isn't, say so rather than fabricating output.
- Re-runs are scoped to the stage QA Director names — this is the whole
  point of the modular design over a single do-everything prompt.
