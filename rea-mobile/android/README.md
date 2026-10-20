# REA Mobile for Android

An Android app that runs [REA (Reverse Engineer Anything)](https://github.com/morluto/rea)
**on the phone itself**, offline. It can also connect to REA on your computer for the
analyses that need desktop engines.

## Install

1. Download `rea-mobile-<version>-arm64-v8a.apk` to your phone.
2. Open it, and allow your browser or file manager to install apps when Android asks.
3. Open **REA Mobile**. The first launch unpacks REA (about 20–60 seconds), then the
   status shows **On phone**.

Requires Android 7.0 or newer on a 64-bit ARM phone (nearly every phone from the last 7
years). Use `--abis arm64-v8a,x86_64` when building for emulators or x86 Chromebooks.

## What works on the phone

REA's built-in analyzers run on the phone, with no internet:

| Quick action      | REA command                       | Use it for                                     |
| ----------------- | --------------------------------- | ---------------------------------------------- |
| Phone app         | `inspect-artifact`                | Any app installed on the phone (pick from a list) |
| Inspect file      | `inspect-artifact`                | Any file: APK, ZIP, ELF, Mach-O, PE…            |
| Flutter app       | `identify-flutter-build`          | Dart snapshot hash and engine build of a Flutter APK |
| SQLite database   | `inspect-sqlite-database`         | Tables, columns, indexes and rows               |
| JS / Electron app | `analyze-javascript-application`  | Modules, imports and routes of a JavaScript app |
| Go / Rust binary  | `inspect-go-binary`, `inspect-rust-binary` | Embedded build and dependency info     |
| .NET assembly     | `inspect-managed-artifact`        | PE/CLI identity and metadata                    |

Any other REA command can be typed in the Command field. Commands that need a desktop
engine (Ghidra, Hopper, IDA, JADX, apktool, Chrome) report that the engine is unavailable;
for those, switch to **My computer** in Settings and paste the link printed by
`node server.mjs` (or the offline bundle) on your computer.

The **Docs** tab has all of REA's documentation, readable offline.

## How it works

```
REA Mobile app
├── WebView ── http://127.0.0.1:<port>/       interface + docs served from the APK
│                   │ /api/…
│                   ▼
└── ReaService ── Node.js 24 (Termux build) ── REA Mobile server ── rea <command>
```

- `lib/arm64-v8a/libnode.so` and `libps.so` are [Termux](https://termux.dev)'s Android
  builds of Node.js and procps `ps`, compiled for Android's own C library. Android only
  lets apps run programs from their native-library folder, hence the `lib*.so` names.
- `assets/rea-runtime.zip` holds REA with its npm dependencies and the REA Mobile server;
  it is unpacked to app storage on first launch and again after an update.
- REA listens on 127.0.0.1 only, so other devices can't reach it, and every request
  carries a per-install random token.
- A foreground service with a notification keeps an analysis running while you switch
  apps. Tap **Stop** in the notification to shut REA down.

Permissions: Internet (local connections), notifications and foreground service (to keep
analyses running), and *query all packages* (to list installed apps for the picker).

## Build it yourself

Needs Node.js 22+, JDK 17+, git, curl, zip/unzip, `ar`, `tar` and `readelf` (binutils).
The Android SDK is downloaded automatically if `ANDROID_HOME` doesn't have build-tools 35.

```bash
cd rea-mobile
# Latest REA from npm, docs from github.com/morluto/rea:
node android/build-apk.mjs
# Or REA built from a source checkout / downloaded zip (also used for the docs):
node android/build-apk.mjs --rea-source /path/to/rea-main
# -> android/dist/rea-mobile-1.0.0-arm64-v8a.apk
```

Options: `--rea <version or .tgz>`, `--abis arm64-v8a,x86_64`, `--sdk <dir>`,
`--keystore <file.jks>` (password from `REA_MOBILE_KEYSTORE_PASSWORD`), `--out <dir>`.

**Signing key:** the first build creates `~/.cache/rea-mobile-android/rea-mobile.jks`.
Android only installs an update signed with the same key as the installed app, so keep
that file (and pass it with `--keystore`) if you want to update without uninstalling.

GitHub Actions can build it too: **Actions → REA Mobile Android app → Run workflow**.
Add a `REA_MOBILE_KEYSTORE_B64` secret (base64 of your `.jks`) and
`REA_MOBILE_KEYSTORE_PASSWORD` to sign CI builds with your own key.
