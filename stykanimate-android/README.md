# StykAnimate AI (Android)

An Android app built from [StykAnimate](https://github.com/filippocalippo/StykAnimate-App) (GPL-3.0-or-later).
It has two parts:

- **AI Studio** (home screen). Describe a concept and Claude or OpenAI writes the animation:
  stick-figure characters, poses, movement, camera moves, speech bubbles, effects, sound effects
  and music. You can then revise it ("make the jump higher"), edit the sound cues, import your own
  music or sound files, and export an MP4/WebM video with sound to `Downloads/StykAnimate`.
- **Full editor**. The complete StykAnimate web editor, bundled offline. Tap *Full editor* at the
  top; Android's back button returns to the studio.

## Using it

1. Install `StykAnimate-AI-debug.apk` (allow "install unknown apps" for your browser or file manager).
2. Tap ⚙ and pick **Claude** or **OpenAI**, paste your API key, and optionally change the model
   (defaults: `claude-opus-5-5`, `gpt-5`). The key is stored only on the device and sent only to
   that provider; requests are billed to your account.
3. Type a concept, pick a length, tap **Animate with AI**.

A demo animation ("Sunset Duel") is preloaded so playback, sounds and export can be tried without a key.

### Sound
- 33 built-in sound effects (punch, kick, whoosh, explosion, laser, coin, magic, cheer, thunder, …)
  synthesized on the device, plus procedural music in 10 moods (epic, happy, tense, calm, funny,
  sad, action, spooky, heroic, chill) with an adjustable tempo.
- **Sound & music** tab: add a sound at the playhead, retime, replace or delete cues, set volumes.
- **Import music or sound file**: imported files are kept on the device, appear in every sound list,
  can replace the generated music, and are offered to the AI as `custom:<name>` sounds.

## Building

```sh
./build.sh                                   # clones StykAnimate-App at the pinned commit
STYK_SRC=/path/to/StykAnimate-App ./build.sh # or use a local checkout
```

Needs Node.js 22+, JDK 17+ and the Android SDK (`ANDROID_HOME`, or `sdk.dir` in
`android/local.properties`). Output: `dist/StykAnimate-AI-debug.apk`. The GitHub Actions workflow
`.github/workflows/android-apk.yml` builds the same APK and uploads it as an artifact.

## Layout

- `studio/`: AI Studio (plain ES modules, no bundler)
  - `js/scene.js`: scene format, pose library, validation of AI output
  - `js/renderer.js`: draws a scene at any time t (Canvas 2D)
  - `js/audio.js`: WebAudio sound effects, mood music, imported audio
  - `js/ai.js`: prompt and Claude/OpenAI requests
  - `android-bridge.js`: file saving and service-worker opt-out inside the app (shared with the editor)
- `android/`: WebView shell. Assets are served from `https://appassets.androidplatform.net/assets/www/`;
  AI requests go through a native HTTP bridge restricted to `api.anthropic.com` and `api.openai.com`.
