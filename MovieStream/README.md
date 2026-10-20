# MovieStream (Android)

A movie streaming app for Android, built with Kotlin, Jetpack Compose and Media3 (ExoPlayer).

## Features

- **Home**: a featured hero banner, a "Continue watching" row, and rows for each genre
- **Search** by title, genre or description
- **My List**: save movies for later (stored on the device)
- **Detail page** with Play / Resume / Start over
- **Full-screen player**: landscape, immersive, ±10 s seek, subtitle track picker
- Plays **MP4/MOV/MKV/WebM** files and **HLS (.m3u8)** / **DASH (.mpd)** adaptive streams
- **Resume**: remembers where you stopped in each movie
- **Play a stream URL**: the link icon on Home plays any URL you paste

The bundled catalog holds open-licensed Blender Foundation films (CC BY), so the app works
out of the box.

## Build & run

Requirements: JDK 17+ and the Android SDK (API 35). In Android Studio, open the `MovieStream`
folder and press Run. From the command line:

```bash
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

Minimum Android version: 8.0 (API 26).

## Adding your own movies

Edit `app/src/main/assets/catalog.json`:

```json
{
  "id": "unique-id",
  "title": "My Movie",
  "year": 2024,
  "durationMinutes": 95,
  "rating": "PG",
  "genres": ["Drama"],
  "featured": false,
  "description": "…",
  "poster": "https://example.com/poster.jpg",
  "stream": "https://example.com/movie/master.m3u8",
  "credit": "Licensing / attribution text"
}
```

`poster` may be `null`; the app then draws title art for the movie. To update the catalog without
shipping a new build, host the JSON somewhere and set `CATALOG_URL` in `app/build.gradle.kts`.
If that fetch fails, the app falls back to the bundled copy.

Only add content you own or are licensed to distribute.

## Project layout

```
app/src/main/java/com/example/moviestream/
├── MainActivity.kt          navigation + bottom bar
├── data/                    Movie model, catalog loading, My List / progress storage
├── player/PlayerActivity.kt ExoPlayer full-screen playback
└── ui/                      ViewModel, theme, components, screens
```

## Ideas for next steps

- Chromecast (`androidx.media3:media3-cast`)
- Background audio / picture-in-picture via `MediaSessionService`
- Offline downloads (`androidx.media3:media3-exoplayer` `DownloadManager`)
- DRM (Widevine) for licensed premium content, via `MediaItem.DrmConfiguration`
- User accounts and a backend catalog API
