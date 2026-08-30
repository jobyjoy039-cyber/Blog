# AI Video Pipeline

An autonomous video editor built on Claude Code as the **master orchestrator**,
coordinating a set of best-in-class open-source repos through a modular
pipeline instead of ad hoc, random tool calls.

`video-use` remains the main editing engine (timeline management, subtitles,
FFmpeg/Remotion orchestration). Everything else in this pipeline *extends*
it — generating the assets and decisions `video-use` then assembles — rather
than replacing it.

See `ARCHITECTURE.md` for the full design, `CLAUDE.md` for the orchestrator's
run instructions, and `schemas/` for the JSON contracts passed between
stages. Stage responsibilities live as individual Claude Code subagents in
`../.claude/agents/`.

## Repository roles

| Repository | Purpose | Stage |
|---|---|---|
| `browser-use/video-use` | Main editing engine, timeline management, subtitle generation, FFmpeg orchestration, Remotion integration | Video Assembly |
| `claude-remotion-skill` | Motion graphics, lower thirds, animated text, intros, charts | Video Assembly |
| `Hyperframes` | AI-generated overlays and animated scenes | Video Assembly |
| `WhisperX` | Accurate transcription, speaker diarization, word-level timestamps | Audio Pipeline |
| `soundeffects-claude-code` | Intelligent placement of sound effects | Audio Pipeline |
| `FoleyCrafter` | Realistic environmental sounds | Audio Pipeline |
| `AudioLDM` | Ambient audio from text prompts | Audio Pipeline |
| `Video2Music` | Background music matching video content | Audio Pipeline |
| `musiclm-pytorch` | Original music tracks from prompts | Audio Pipeline |
| `ComfyUI` | AI image workflows | Asset Generation |
| `Kokoro TTS` / `XTTS-v2` | Voice synthesis / voice cloning | Asset Generation |
| `SAM 2` / `Grounding DINO` | Segmentation / object detection | Asset Generation |
| `Depth Anything V2` | Depth estimation | Asset Generation |
| `PySceneDetect` | Scene detection (cross-checks Script Director) | Script Analysis |
| `FFmpeg` | Core rendering | Final Render |
| `yt-dlp` | Reference/stock asset download | Asset Generation |
| `MediaPipe` / `OpenCV` | Face tracking / video analysis | QA / Asset Generation |

None of these external projects are vendored into this repo. Each is wired
in as a callable tool from its own checkout/environment; the pipeline here
only defines *when* each is invoked and *what JSON* flows between stages.

## Quick start

```
project/
  input/            transcript.txt, narration.wav, face.jpg
  assets/           stock/ ai_images/ ai_video/ music/ sfx/ foley/ overlays/
  timeline/         scenes.json, shots.json, remotion composition
  renders/          intermediate renders
  cache/
  logs/
  output/           final.mp4, captions.srt, thumbnail.png, metadata.json
```

Drop inputs into `project/input/`, then run the pipeline described in
`CLAUDE.md` — Claude Code invokes each director agent in order, reading and
writing the JSON files under `project/timeline/` and `project/assets/` so
every stage hands off structured data instead of a giant prompt.
