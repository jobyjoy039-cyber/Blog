# Product Video Studio (Android)

Turns product photos into a finished vertical ad: 1080×1920 H.264 MP4 at 30 or 60 fps, with
camera moves, transitions, animated captions, an original score, sound effects, optional
voice-over and color grading. It's ready for Reels, TikTok, Shorts, Facebook and ads without
further editing.

The user adds 1–20 photos and, optionally, a name, description, price, discount, URL, logo,
brand colors, music and voice-over. Everything else is decided by the app.

## How it works

```
photos ─► analysis ─► creative director ─► storyboard ─► GPU renderer ─► MP4
             │                │                              ▲
             │                └─► copy, sound design ─► audio composer (music, SFX, voice)
             └─ colors, subject, cut-out, detail, angle, labels, packaging text
```

| Package | Responsibility |
|---|---|
| `analysis` | `ImageAnalyzer` (palette, plain-background detection, subject box, detail spot, sharpness, shape, view angle), `Segmenter` (cut-out from plain backgrounds), `VisionLabeler` (ML Kit labels and packaging text, bundled models, offline), `ProductInsights` (mood, materials, brand), `UrlMetadata` (product page). |
| `director` | `CreativeDirector` picks the scene sequence (hero reveal → views → close-up/macro → lifestyle → features → benefits → CTA), fits it to the beat grid and chooses image, layout, angle, camera move, effects, transition, text, SFX and voice lines per scene. `CopyWriter` writes the on-screen copy and the post caption. Seedable, so "Try another direction" gives a new cut. |
| `render` | `CameraRig` turns 23 named moves into per-frame poses. `Compositor` draws scenes in OpenGL ES 2.0: studio backdrop, glow, shadow, reflection, perspective product, blur, motion blur, light sweep. It also blends 11 transitions, grades with 10 looks and animates text. `VideoRenderer` feeds the hardware H.264 encoder's input surface and muxes AAC audio. |
| `audio` | `MusicGenerator` composes a tempo-locked score per mood. `SfxSynth` synthesizes whooshes, pops, clicks, shimmers, impacts and ambience. `VoiceOver` narrates with on-device text-to-speech. `BeatDetector` syncs cuts to the user's own track. `AudioComposer` handles mixing and ducking. |
| `service` | `Pipeline` (analysis + direction), `RenderService` (foreground service, progress notification), `GallerySaver`. |
| `storage` | `ProjectStore`: autosaved projects, each in its own folder with copies of every asset. |
| `ui` | Projects, editor, storyboard ("director's cut"), render/preview/share. Built in code, no XML layouts. |

Rendering runs fully offline. The network is only used when you ask it to read a product URL.

## Limits worth knowing

- Camera angles and 3D moves are simulated from 2D photos with perspective, parallax and
  focus, so a "side view" shows a photo's side only if you supplied one.
- The cut-out needs a plain, fairly uniform background. Otherwise the photo is shown as a
  card or full-bleed.
- The voice-over uses the phone's installed text-to-speech voice.

## Build

GitHub Actions (`.github/workflows/product-video-studio.yml`) builds the APK and renders a
sample video on an emulator as an end-to-end test. Both are published to the
`product-video-studio-latest` release. Locally: `gradle assembleRelease` in this folder
(Android SDK required).

To run the self-test on a device:

```
adb shell am start -n com.productvideostudio/.ui.MainActivity --ez selftest true
```

It writes `selftest.mp4` to `Android/data/com.productvideostudio/files/`.
