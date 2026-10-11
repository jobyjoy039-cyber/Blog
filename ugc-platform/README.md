# UGC Ad Studio Platform

Paste or share a product link on Android and get back a platform-ready UGC-style video ad: script, voiceover, word-by-word captions, motion and music, sized for TikTok, Reels, Shorts, Facebook, Pinterest, YouTube, Amazon or Flipkart.

```
 Android app (Kotlin, Compose, MVVM + Clean Architecture, Hilt)
     │  REST + API key
     ▼
 Orchestrator API (Python, FastAPI) ── SQLite job store + worker queue + step cache
     │  asks the Plugin Registry for each capability's chain (preferred → fallbacks)
     ├── ingest   web (JSON-LD/OpenGraph/Shopify) · manual brief + uploads
     ├── analyze  claude · local rules
     ├── script   claude · framework templates (PAS, AIDA, BAB, …)
     ├── voice    VoiceStudio server (KittenTTS, cloning engines…) · silent
     ├── align    proportional (WhisperX planned)
     └── render   FFmpeg (Ken Burns, crossfades, ASS captions, ducking, −14 LUFS)
```

**Every open-source project is one plugin behind one interface.** The orchestrator never imports a model directly: it asks the registry for a capability's chain, tries the preferred plugin with retries, and falls back to the next one if it fails. Swapping a model at runtime is a single API call (`PUT /plugins/voice {"name": "…"}`), which the app's Settings screen exposes.

## What works today

Verified in this repository (see *Testing*):

| Step | What happens |
|---|---|
| Product link | Reads schema.org JSON-LD and OpenGraph data, or Shopify's public `products/<handle>.json`. Downloads up to 6 product images. Obeys `robots.txt`. |
| Manual brief | Name, price, features and reviews, plus photos picked on the phone. |
| Analysis | Audience, pain points (taken from real review text), USPs, objections, hooks, **proof points copied only from the data**, and risky-claim warnings. |
| Script | 8 frameworks: PAS, AIDA, BAB, Problem→Solution, Unboxing, Founder, Educational, Comparison. Scenes get a voice line, an on-screen headline and a product image. |
| Voice | Each scene is voiced separately, so visuals cut exactly on line boundaries. Edge silence is trimmed. If the real audio overruns the target length, supporting scenes are dropped and the hook, solution, proof and CTA always stay. |
| Render | The product shot sits over a blurred fill of itself (any image fits any aspect), with a Ken Burns push, 0.3s crossfades, word-highlighted captions above the platform UI area, scene headlines, an "Ad" disclosure label, optional music ducked under the voice, and loudness normalised to −14 LUFS. Output is H.264/AAC MP4 with faststart, plus a thumbnail. |
| Platforms | 9:16 (TikTok, Reels, Shorts, Snapchat) · 4:5 (Facebook) · 2:3 (Pinterest) · 16:9 (YouTube, Amazon) · 1:1 (Flipkart), each at 720p, 1080p or 4K. |
| Android | Create (link or manual + photo picker), share-to-app from any browser or store app, live progress, in-app player, share/save, library, settings (server URL, API key encrypted with an Android Keystore key, AI module picker). |
| Ops | Durable job queue that resumes after a restart, content-hash step cache (retries skip finished work), API-key auth, SSRF guard on product links (private/loopback/metadata addresses refused on every hop), upload type/size limits, path-traversal checks, Docker image, docker-compose with VoiceStudio, GitHub Actions CI. |

## Quick start

```bash
# 1. Backend (needs ffmpeg and a font; Inter is the default)
cd ugc-platform/backend
uv venv --python 3.11 && uv pip install -e '.[claude,dev]'
export UGC_API_KEY=$(openssl rand -hex 24)
export ANTHROPIC_API_KEY=...          # optional: Claude writes the copy; without it the offline templates run
.venv/bin/uvicorn ugc_studio.app:create_app --factory --port 8080

# 2. Voice (optional; without it the ad renders with captions only)
#    Run VoiceStudio (github.com/debpalash/VoiceStudio) on :3900 and install KittenTTS:
curl -X POST localhost:3900/models/install -H 'content-type: application/json' \
     -d '{"repo_id":"KittenML/kitten-tts-mini-0.8"}'

# 3. Make an ad from the command line
curl -X POST localhost:8080/jobs -H "X-API-Key: $UGC_API_KEY" -H 'content-type: application/json' \
     -d '{"url":"https://your-store.com/products/thing","platform":"tiktok","framework":"PAS","target_seconds":25}'
curl localhost:8080/jobs/<id> -H "X-API-Key: $UGC_API_KEY"          # poll
curl -o ad.mp4 localhost:8080/jobs/<id>/video -H "X-API-Key: $UGC_API_KEY"

# 4. Android
cd ../android && ./gradlew assembleDebug    # app/build/outputs/apk/debug/app-debug.apk
#    In the app: Settings → server URL (emulator: http://10.0.2.2:8080/) + API key
```

Or run both services with Docker: `docker compose up -d` from `ugc-platform/` (see `docker-compose.yml`).

Settings are environment variables prefixed `UGC_`: `UGC_DATA_DIR`, `UGC_API_KEY`, `UGC_WORKERS`, `UGC_STEP_RETRIES`, `UGC_PREFERRED` (JSON, e.g. `{"voice":"voicestudio"}`), `UGC_ANTHROPIC_MODEL`, `UGC_VOICESTUDIO_URL`, `UGC_VOICESTUDIO_ENGINE`, `UGC_VOICE_SPEED`, `UGC_FONT`, `UGC_ALLOW_PRIVATE_URLS` (dev only: allow product links on localhost/LAN, which are blocked by default).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness (no auth) |
| GET | `/options` | Platforms, frameworks, resolutions |
| POST | `/uploads` | Image or music file (multipart, ≤50 MB) → `{id}` |
| POST | `/jobs` | `JobRequest` → job (202). Needs `url` or `brief`. |
| GET | `/jobs`, `/jobs/{id}` | Job list / status, progress, script, trace |
| POST | `/jobs/{id}/retry` | Re-run; cached steps are skipped |
| GET | `/jobs/{id}/video`, `/jobs/{id}/thumbnail` | Outputs |
| GET | `/plugins` | Every module: availability, licence, commercial flag |
| PUT | `/plugins/{capability}` | Hot-swap the preferred module |

Each job's `trace` records which plugin ran each step, whether it came from cache, and which plugins failed before it.

## Adding a module

1. Subclass the capability's base class in `backend/ugc_studio/plugins/base.py` (`VoicePlugin`, `RenderPlugin`, …).
2. Implement `available()` (cheap check: is the model installed? is the server up?) and the one capability method.
3. Set `license` and `commercial_ok` truthfully. The app shows a "(non-commercial)" badge.
4. Register it in `plugins/__init__.py`. It now appears in the app's AI module picker and works as a fallback.

Heavy models belong in their own service (like VoiceStudio) behind HTTP, so GPU work scales separately from the API.

## Licensing and legal: read before commercial use

- **Model weights carry their own licences.** Many popular models are **non-commercial**, which matters because ads are commercial use. The default voice is KittenTTS (Apache-2.0). VoiceStudio's default OmniVoice engine is CC-BY-NC, so don't select it for client work.
- **VoiceStudio is AGPL-3.0.** It runs as a separate network service and isn't linked into this code. If you modify it and offer it to users over a network, AGPL obligations apply to those changes.
- **Product data.** The web ingestor reads what stores publish for sharing (structured data), respects `robots.txt` and doesn't bypass bot protection. Amazon, Flipkart, Myntra, Meesho and AliExpress block or forbid scraping in their terms. Add their official APIs as ingest plugins (for example Amazon's Product Advertising API) or use the manual brief.
- **Honesty is enforced in the pipeline.** Prompts forbid invented numbers, fake testimonials and posing as a real customer. Proof points must come from the data. Risky claims are flagged. Every render carries an "Ad" label (FTC and ASCI require disclosure of paid endorsements).
- **Voice cloning and avatars** need written consent from the person being cloned (VoiceStudio records consent per profile).

## Roadmap: the full spec, honestly mapped

Status: ✅ built and tested · 🟡 partial · ⬜ not started. Candidate projects are suggestions; **verify each licence yourself before shipping**, because licences change.

| Module from the spec | Status | Notes / candidate open-source projects |
|---|---|---|
| Product intelligence (title, images, price, specs, rating, reviews) | ✅ | JSON-LD, OpenGraph, Shopify. ⬜ Official marketplace APIs, CSV batch import, PDF/video inputs |
| AI product analyzer | ✅ | Claude (structured output) + offline rules |
| Review mining (clustering thousands of reviews) | 🟡 | Uses reviews present on the page. ⬜ Embedding clustering (sentence-transformers, Apache-2.0) over API/CSV-sourced reviews |
| Competitor intelligence | ⬜ | Same ingestors pointed at competitor listings, then a Claude comparison step. Ad-library data via Meta's Ad Library API |
| Marketing brain / script generator | ✅ | 8 frameworks, caption and hashtags. ⬜ SEO titles/descriptions for listings |
| Voice engine | ✅ | VoiceStudio server. Commercial-friendly: Kokoro-82M (Apache-2.0), OpenVoice V2 (MIT). ⚠️ XTTS-v2 (Coqui licence) and F5-TTS weights (CC-BY-NC) are non-commercial |
| Emotion / delivery control | 🟡 | Speed is configurable. ⬜ Per-scene emotion via engines that support instructions (VoiceStudio `instruct`) |
| Subtitles | ✅ | Word-highlight ASS captions. ⬜ WhisperX (BSD-2) aligner plugin for exact timing; caption style presets; emoji |
| Video generator | 🟡 | Ken Burns + crossfades. ⬜ Image-to-video service plugin: Wan 2.x (Apache-2.0); check LTX-Video and HunyuanVideo licences |
| Avatar / talking head | ⬜ | Separate GPU service. MuseTalk (MIT), EchoMimic (Apache-2.0). ⚠️ Wav2Lip and InsightFace-based models are non-commercial |
| Audio studio | 🟡 | Ducking + −14 LUFS. ⬜ Denoise/EQ chain (FFmpeg `afftdn`, `equalizer`); ⚠️ MusicGen weights are non-commercial, so use licensed stock music |
| Motion graphics | 🟡 | Headlines, captions, "Ad" label. ⬜ Remotion templates (⚠️ Remotion needs a paid company licence above 3 employees) or MoviePy (MIT) |
| Image tools | ⬜ | rembg (MIT) background removal, Real-ESRGAN (BSD-3) upscaling, LaMa (Apache-2.0) object removal |
| AI designer (static creatives, infographics) | ⬜ | Pillow/HTML templates rendered with Playwright, sized per platform |
| AI editor / viral optimisation | ⬜ | Rules first (hook ≤2s, product on screen by 3s, scene length); retention prediction needs real performance data |
| Multi-language | 🟡 | `language` passes through to Claude and voice. ⬜ Caption translation (Claude, or Argos Translate, MIT) |
| Export | 🟡 | MP4 in every aspect ratio at 720p/1080p/4K. ⬜ MOV/WebM/GIF/PNG-sequence presets (FFmpeg) |
| Agents + master orchestrator | ✅ | Each "agent" in the spec is a capability step. The orchestrator handles selection, fallback, retries, caching and the queue. ⬜ Distributed workers (move the queue to Redis/Celery when one box isn't enough) |
| Production (DI, MVVM, tests, CI, Docker, encrypted keys) | ✅ | ⬜ Crash reporting / analytics (opt-in), Compose UI tests, offline drafts on the phone |

## Testing

```bash
cd backend && .venv/bin/pytest -q                  # 27 tests: ingest, brain, registry, orchestrator, real FFmpeg render, API
cd android && ./gradlew testDebugUnitTest          # 11 tests: use cases, polling, repository against real server JSON
```

The Android repository test parses JSON captured from a live backend run, so a server/app contract break fails the build.
