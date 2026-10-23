# Video Transcriber (Android)

An Android app that transcribes videos **on the phone itself**, offline, using
[whisper.cpp](https://github.com/ggml-org/whisper.cpp) (OpenAI's Whisper model in C/C++).
No server and no API key are needed. Internet is used only once, to download a model.

## Features

- Pick any video (or audio) file, or share one to the app from your gallery or file manager
- Pulls out the audio track with Android's built-in decoders (MP4, MKV, WebM, 3GP, …)
- Runs Whisper on the phone, with progress shown and lines appearing as they are recognised
- Can be cancelled at any time
- Detects the language automatically, or you can pick it, and can translate the speech to English
- Choose a model size and download it inside the app, or import your own `ggml-*.bin`
- Copy or share the transcript, or save it as `.txt`, `.srt` or `.vtt` subtitles

## Models

| Model | Size | Notes |
|---|---|---|
| Tiny (q5_1) | 31 MB | Fastest, lowest accuracy |
| Base (q5_1) | 57 MB | Fast, good for clear speech |
| **Small (q5_1)** | 181 MB | Recommended balance |
| Medium (q5_0) | 514 MB | Accurate, slow on phones |
| Large v3 Turbo (q5_0) | 547 MB | Most accurate, needs a recent flagship |
| Base (English only) | 142 MB | Better for English-only audio |

Models download from `huggingface.co/ggerganov/whisper.cpp` into the app's private storage.

## Build

Requirements: Android Studio (Ladybug or newer), or the command line with:

- Android SDK 35
- NDK `27.2.12479018` and CMake `3.22.1` (install them from *SDK Manager → SDK Tools*)
- JDK 17+
- `git` on your PATH (CMake uses it to fetch whisper.cpp v1.9.4 the first time you build)

```bash
cd VideoTranscriber
./gradlew assembleRelease        # or assembleDebug
# APK: app/build/outputs/apk/release/app-release.apk
```

To build without network access, point the build at a local whisper.cpp checkout:

```bash
git clone --branch v1.9.4 https://github.com/ggml-org/whisper.cpp
./gradlew assembleRelease -PwhisperCppDir=/absolute/path/to/whisper.cpp
```

The release build is signed with the debug key so you can install it directly.
Set up your own signing config in `app/build.gradle.kts` before publishing to the Play Store.

## How it works

```
Video file ──MediaExtractor + MediaCodec──▶ PCM audio
          ──downmix + resample──▶ 16 kHz mono float  (AudioDecoder.kt)
          ──JNI──▶ whisper_full()                     (whisper_jni.cpp)
          ──segment callbacks──▶ live transcript      (TranscribeViewModel.kt)
```

| File | Purpose |
|---|---|
| `app/src/main/cpp/CMakeLists.txt` | Fetches and builds whisper.cpp (CPU, Release, `-O3`) |
| `app/src/main/cpp/whisper_jni.cpp` | JNI bridge: load model, transcribe, progress, segments, cancel |
| `WhisperLib.kt` | Kotlin side of the bridge, plus picking the number of fast CPU cores |
| `AudioDecoder.kt` | Video → 16 kHz mono PCM |
| `ModelManager.kt` | Model download, import and deletion |
| `Transcript.kt` | TXT / SRT / VTT formatting, language list |
| `TranscribeViewModel.kt` | App state and the transcription pipeline |
| `ui/TranscribeScreen.kt` | Jetpack Compose UI |

## Tips and limitations

- Speed depends heavily on the phone. On a recent mid-range phone, Base runs several times
  faster than real time and Small runs at roughly real time.
- The native code is always compiled in Release mode, because a debug build of whisper.cpp is
  far too slow to use.
- The whole audio track is held in memory (about 230 MB per hour of audio). Very long videos
  on low-memory phones may fail; use a shorter clip or split the video.
- Transcription runs while the app is open, and the screen is kept on. If you switch apps, Android
  may stop it. Moving the work into a foreground service is the next step if you need background runs.
- English-only (`.en`) models and Large v3 Turbo cannot translate.
