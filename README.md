# StickAI

An Android app for stick figure animation. You type a concept, **Claude** or **OpenAI** directs it as a keyframed animation, and you can fine-tune poses, add **sound effects** and **music**, then export a video with sound.

## Features

- **AI animation.** Describe a scene ("a ninja and a robot have a dance battle on a rooftop") and the AI returns a full animation: figures, poses, movement, speech bubbles, props, effects (POW!, impacts, dust, screen shake), captions, timed sound effects and a music mood. A second box changes the current animation ("make the jump higher, add an explosion").
- **Claude or OpenAI.** Pick the provider on the Create tab. Keys and model names are set in Settings (⚙) and stored only on the device. Defaults: `claude-opus-5-5` and `gpt-5`.
- **Pose editor.** On the Edit tab, drag the coloured joints to pose a figure; each drag sets a keyframe at the playhead. It also has 28 pose presets, expressions, flip, speech bubbles, onion skin, keyframe navigation, multiple figures, colours, scenery and scene length.
- **Sound.** 20 synthesized sound effects (punch, whoosh, explosion, boing, laser…) placed on the timeline, plus your own imported audio files. Generated music in 7 moods with adjustable BPM, or an imported music track. Volume controls for both.
- **Export.** Records an MP4/WebM video with all audio and opens the Android share sheet. Projects save and open as `.stick.json` files.
- Works without an API key through the built-in demo and the manual editor.

## Install on a phone

Download `app-debug.apk` (from the GitHub Actions run named **Android APK**, under Artifacts), open it on the phone and allow installing from that source.

## Develop

Requires Node 22+. Building the APK also needs JDK 21 and the Android SDK (platform 36).

```bash
npm install
npm run dev            # http://localhost:5173 with live rebuild
npm test               # build + headless browser smoke test (AI calls are mocked)
npm run android:apk    # build web bundle, sync Capacitor, assemble debug APK
```

The APK is written to `android/app/build/outputs/apk/debug/app-debug.apk`.

## How it works

| File | Role |
|---|---|
| `src/scene.js` | Scene format, pose presets, validation/normalization of AI output, keyframe interpolation |
| `src/renderer.js` | Canvas drawing: skeleton, faces, speech bubbles, scenery, props, effects, captions |
| `src/audio.js` | Web Audio engine: synthesized SFX, procedural music, imported audio (kept in IndexedDB) |
| `src/ai.js` | Prompt and calls to Claude (`@anthropic-ai/sdk`) and OpenAI (`openai`) |
| `src/exporter.js` | MediaRecorder video export, saving through Capacitor Filesystem and Share |
| `src/main.js` | UI, playback loop, joint dragging |

The AI is asked for a JSON scene (schema in `src/ai.js`). Whatever comes back is passed through `normalizeScene`, which clamps every value and drops anything unknown, so a malformed reply can't break the app.

API calls go straight from the device to the provider using your own key. That is fine for personal testing. For a public release, route requests through your own backend so keys aren't shipped to users.
