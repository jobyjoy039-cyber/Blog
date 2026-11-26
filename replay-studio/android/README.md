# Replay Studio for Android (APK)

A standalone app: install the APK, open it, and the phone becomes the streaming host. You don't need
Termux, a PC or root. It runs the same engine as the Linux version:

* **Foreground service** ("Replay Studio" notification) with a CPU wake lock and a Wi-Fi lock. Streaming
  continues with the screen off, the phone locked, or the app swiped away. It restarts after a reboot.
* **Embedded Python** (Chaquopy) running the same API server and stream worker that the Linux test suite
  covers.
* **FFmpeg 7.1.1 for arm64**, cross-compiled with x264 and OpenSSL (RTMPS), shipped inside the APK.
* The dashboard opens inside the app. Google sign-in opens in Chrome, because Google blocks sign-in inside
  app WebViews. Then you switch back to the app.
* **Low-power copy mode**: each video is encoded once when you add it, and live streaming only copies it.

Target: arm64 phones on Android 7.0+ (API 24). The Redmi Note 8 Pro (Helio G90T, arm64) qualifies.

## Install on the phone

1. Copy `ReplayStudio-<version>.apk` to the phone and open it. Allow **Install unknown apps** for your
   file manager or browser when Android asks.
2. Open **Replay Studio** and allow notifications and video access. Then allow **ignore battery
   optimisation**.
3. On Xiaomi/Redmi, the app shows the MIUI steps:
   * **Autostart: on**
   * App info → **Battery saver → No restrictions**
   * Lock the app in **Recent apps**
4. **Create a dashboard password** (first-run screen).
5. **Google OAuth client** (one time): in Google Cloud Console, enable the *YouTube Data API v3*. Create an
   OAuth client of type **Web application** with the redirect URI
   `http://localhost:8787/api/youtube/callback`. Add your Google account as a test user, or publish the
   app (see the main README, section 4). Paste the client ID and secret into the app.
6. **Connect YouTube account**. Chrome opens; approve; you see "YouTube connected". Switch back to Replay
   Studio.
7. Pick a video: **Upload video from this device** copies it into the app. Or put it in the phone's
   **Movies** folder and use **Choose from host media folder**, which avoids a copy. Wait for **Ready**.
   The one-time encode takes roughly as long as the video, or longer.
8. Fill in the title etc. (Unlisted by default) → **Start stream**. Press **Stop stream** to end.

To control it from a computer on the same Wi-Fi, open `http://<phone-IP>:8787` and log in with your
password.

## Build the APK yourself (Linux x86-64)

Requirements: JDK 17+, Python **3.13** on PATH as `python3.13` (Chaquopy uses it at build time),
Node 18+, and the Android SDK (platform 34, build-tools 34). Building FFmpeg also needs NDK r27c.

```bash
cd replay-studio
(cd frontend && npm ci && npm run build)            # dashboard into the Python package

# 1) FFmpeg for arm64 (about 10 minutes). SRC must contain ffmpeg.tar.xz (7.1.1), x264.tar.gz, openssl.tar.gz
NDK=$HOME/android-ndk-r27c SRC=$HOME/ffmpeg-src OUT=$HOME/ffout \
  android/ffmpeg/build-ffmpeg.sh dynamic
mkdir -p android/ffmpeg/prebuilt/arm64-v8a
cp $HOME/ffout/dynamic/bin/ffmpeg $HOME/ffout/dynamic/bin/ffprobe android/ffmpeg/prebuilt/arm64-v8a/

# 2) The APK
cd android
echo "sdk.dir=$HOME/Android/Sdk" > local.properties
./gradlew assembleRelease
ls app/build/outputs/apk/release/            # app-release.apk
```

Source downloads used for the shipped build:
* <https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz>
* <https://code.videolan.org/videolan/x264/-/archive/stable/x264-stable.tar.gz>
* <https://github.com/openssl/openssl/releases/download/openssl-3.0.15/openssl-3.0.15.tar.gz>

The APK is signed with the build machine's Android **debug key**, so it can be sideloaded. An APK built on
another machine has a different signature. To switch, uninstall the old app first, which deletes its
library and settings.

## How it is put together

| Piece | Where |
|---|---|
| Foreground service, wake/Wi-Fi locks, notification, Python start | `app/src/main/java/com/replaystudio/app/StreamService.java` |
| Dashboard WebView, file picker, Chrome hand-off for Google sign-in, permissions, MIUI prompt | `MainActivity.java` |
| Restart after reboot/update | `BootReceiver.java` |
| Python entry (config, threads, notification text) | `backend/replay_studio/android_app.py` |
| FFmpeg cross-compile | `ffmpeg/build-ffmpeg.sh` |

FFmpeg and ffprobe are packaged as `libffmpeg.so` / `libffprobe.so`, because the app's native library
directory is the only place Android 10+ lets an app execute files. They link Android's own libc, so DNS
and networking behave like any app.

## Licences

The bundled FFmpeg is built with `--enable-gpl --enable-version3` (libx264 is GPL, OpenSSL 3 is
Apache-2.0), so **the FFmpeg binary in the APK is GPLv3**. If you give the APK to other people, you
must also offer them the corresponding source: the three tarballs above plus `build-ffmpeg.sh`.
Chaquopy is MIT-licensed.
