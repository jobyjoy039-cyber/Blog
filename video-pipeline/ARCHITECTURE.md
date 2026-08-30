# Architecture

## Principle

Claude Code is the **master orchestrator**. It never calls the underlying
repos directly in an unordered way — it runs a fixed pipeline of
single-responsibility **director agents** (`../.claude/agents/*.md`), each
of which owns exactly one stage, reads a JSON file produced by the previous
stage, and writes a JSON file for the next one. `video-use` stays the
editing engine at the center of Video Assembly; every other repo produces
inputs that `video-use` (and Remotion) consume.

```
Transcript
     │
     ▼
Claude Code (Master Orchestrator)
     │
     ├── Script Analysis      (Script Director)
     │      scene detection · emotion · keywords · visual prompts · music mood
     │
     ├── Storyboard            (Storyboard Director)
     │      shot list: zoom, avatar on/off, b-roll need, graphics, transitions
     │
     ├── Asset Generation
     │      ├── Asset Finder      → stock video/images (yt-dlp, stock APIs)
     │      ├── Image Generator   → AI images (ComfyUI)
     │      ├── B-roll Planner    → b-roll assignment per shot
     │      └── Animation Director→ overlays/motion graphics specs
     │
     ├── Video Assembly
     │      ├── Remotion Builder  → composition from shots + animations
     │      ├── video-use         → timeline edit, FFmpeg orchestration
     │      └── Hyperframes       → AI overlays/animated scenes
     │
     ├── Audio Pipeline           (Audio Director, coordinates:)
     │      ├── Music Director    → Video2Music / musiclm-pytorch
     │      ├── Foley Director    → FoleyCrafter / AudioLDM / soundeffects-claude-code
     │      └── Subtitle Director → WhisperX word-level alignment
     │
     ├── QA                       (QA Director: review render, flag issues)
     │
     └── Final Render              (Render Director)
            4K encode · captions burn-in · thumbnail · chapters · SEO metadata
            exports: YouTube cut, Shorts cut, thumbnail, SRT, metadata.json
```

## Data flow, not prompt flow

Each director reads/writes files under `project/`, validated against
`schemas/*.schema.json`. This is the mechanism that keeps the system
"modular pipeline" instead of "Claude Code calling things randomly":

1. **Script Director** — `project/input/transcript.txt` (+ optional
   `narration.wav`) → `project/timeline/scenes.json`
   (`schemas/scene.schema.json`).
2. **Storyboard Director** — `scenes.json` → `project/timeline/shots.json`
   (`schemas/shot.schema.json`). This is where the automatic decisions live:
   b-roll vs. face, camera zoom, background change, titles, charts,
   transitions, color grading.
3. **Asset Finder / Image Generator / B-roll Planner / Animation Director**
   — each reads `shots.json`, writes into
   `project/assets/{stock,ai_images,ai_video,overlays}/` and appends to
   `project/timeline/asset-manifest.json`
   (`schemas/asset-manifest.schema.json`), keyed by `shot_id`.
4. **Audio Director** fans out to **Music Director**, **Foley Director**,
   **Subtitle Director**, each writing into
   `project/assets/{music,sfx,foley}/` and
   `project/output/captions.srt`, then merges into
   `project/timeline/audio-timeline.json`.
5. **Remotion Builder** consumes `shots.json` + `asset-manifest.json` +
   `audio-timeline.json` to produce the Remotion composition in
   `project/timeline/remotion/`.
6. **video-use** takes the composition and asset manifest and performs the
   actual edit/render pass into `project/renders/`.
7. **QA Director** inspects the render (audio sync, missing assets, pacing,
   caption drift) and writes `schemas/qa-report.schema.json` shaped
   `project/logs/qa-report.json`. On failure it names exactly which
   director + shot must re-run; Claude Code loops back to that stage only
   (not the whole pipeline).
8. **Render Director** produces final deliverables into `project/output/`:
   `final.mp4`, a Shorts cut, `thumbnail.png`, chapters, `captions.srt`,
   and `metadata.json` (title/description/tags for SEO).

## Why single-responsibility agents

A single giant prompt asked to "edit the video" has no way to bound its own
mistakes — it re-derives context every step and drifts. Splitting into
13 directors (`Script`, `Storyboard`, `Asset Finder`, `Image Generator`,
`B-roll Planner`, `Animation`, `Remotion Builder`, `Audio`, `Music`,
`Foley`, `Subtitle`, `QA`, `Render`) means:

- Each agent's context is just its input JSON + its own tool wiring, not
  the whole pipeline history.
- Failures are localized: QA Director names the offending stage, and only
  that stage re-runs.
- Repos can be swapped (e.g. musiclm-pytorch → Video2Music) by changing one
  agent's tool wiring, without touching the orchestration order.

## Integration notes

- None of the external repos (`video-use`, `WhisperX`, `FoleyCrafter`,
  `AudioLDM`, `Video2Music`, `musiclm-pytorch`, `ComfyUI`, `Kokoro`/`XTTS-v2`,
  `SAM 2`, `Depth Anything V2`, `Grounding DINO`, `PySceneDetect`, `yt-dlp`,
  `MediaPipe`, `OpenCV`) are vendored here — each director's tool wiring
  should point at its own checkout/venv/API and is expected to be filled in
  per-environment (paths, model weights, API keys).
- Python-based tools (WhisperX, FoleyCrafter, AudioLDM, Video2Music,
  musiclm-pytorch, ComfyUI, SAM 2, Depth Anything V2, Grounding DINO,
  PySceneDetect, MediaPipe, OpenCV) run as separate processes/services
  invoked via CLI or a thin HTTP wrapper — they are not npm dependencies.
- JS/TS-based tools (`video-use`, Remotion, `claude-remotion-skill`,
  `Hyperframes`, `ffmpeg-static`) are listed in `package.json`.
- `project/cache/`, `project/renders/`, `project/assets/`, and
  `project/logs/` hold large binary/generated artifacts and are gitignored;
  only `project/input/` structure and the schemas are meant to be
  version-controlled as templates.
