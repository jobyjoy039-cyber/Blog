# Ritvaya Carousels (Android)

An Android app that makes Ritvayalife Instagram carousels on your phone. You type
the slide text, the app draws each slide in the brand style (cream background,
green headlines, Inter fonts, leaf and rhythm-line design), and saves the slides
as 1080 × 1350 PNGs in your gallery, ready to post.

## Features

- Three carousels already included: Introduction to Ayurveda, Warm water after
  meals, Dinacharya daily routine.
- **New carousel** gives you an 8-slide outline for any topic.
- Swipe through live previews while you edit. Each slide type has its own fields.
- Add, move and delete slides. There are 8 slide types: hook, text, rows,
  cause → effect, numbered steps, insight, call to action, and save/share/follow.
- **Save** writes `Pictures/Ritvaya/<carousel>/…_01.png`, `…_02.png`, and so on.
- **Share** sends all slides to Instagram (or any other app) and copies the
  caption to the clipboard.

Text formatting: press Enter for a new line, wrap a phrase in `[[gold]]` to make
it gold, and use `<i>word</i>` for italics.

## Open in Android Studio

1. Clone the repository and open the **`android`** folder in Android Studio
   (Ladybug or newer).
2. Let Gradle sync. Android Studio installs the SDK pieces it needs.
3. Connect your phone (with USB debugging on) or start an emulator, then press **Run ▶**.

Requires Android 10 or newer.

The example carousels come from `../carousel/carousels/*.json`, the same files the
web renderer uses. Keep the `android` and `carousel` folders side by side.

## Get an APK without Android Studio

Each push builds a debug APK on GitHub Actions. On GitHub, open **Actions →
Android APK**, choose the latest run, and download **ritvaya-carousel-apk**.
Unzip it, copy `app-debug.apk` to your phone and open it. You'll need to allow
"install unknown apps" for your file manager.
