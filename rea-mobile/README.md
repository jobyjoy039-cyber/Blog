# REA Mobile

Use [REA: Reverse Engineer Anything](https://github.com/morluto/rea) from your phone.

REA needs Node.js 22+ and desktop tools such as Ghidra, Hopper, IDA, JADX or Chrome,
so it can't run on a phone itself. REA Mobile is a small server you run on the
computer that has REA, plus a phone app (an installable web app) that connects to it
over your Wi-Fi.

```
 phone (REA Mobile app)  ── Wi-Fi ──▶  your computer: server.mjs ──▶ rea <command>
```

> **Android app:** [`android/`](android/README.md) has an installable APK build that runs
> REA on the phone itself, offline, and can also connect to a computer running this server.

## What it does

- Run any REA command (`doctor`, `inspect-artifact`, `inspect-android-package`,
  `analyze-javascript-application`, `decompile`, …) with output streamed live to your phone
- Quick-action chips for the common analyses
- **Upload** a file from your phone (an APK, binary, app archive…) to the computer and
  analyze it in one tap
- Per-command `--help`, a choice of output format (Markdown, JSON, YAML, TOON), Stop, Copy and Share
- History of recent runs with saved output, so you can rerun or reread them
- **Docs** tab: all of REA's documentation (108 pages), readable offline
- Works from the home screen like a native app; light and dark themes

## Offline bundle (recommended)

One download with everything combined: a portable Node.js runtime, REA with every
dependency, REA's documentation, and this app. Nothing to install, and no internet
needed once you have it. The phone and computer only need to share a Wi-Fi network,
or the phone can join the computer's hotspot.

| Platform              | Bundle                                    |
| --------------------- | ----------------------------------------- |
| Windows (x64)         | `rea-mobile-offline-windows-x64.zip`      |
| macOS (Apple Silicon) | `rea-mobile-offline-macos-arm64.tar.gz`   |
| macOS (Intel)         | `rea-mobile-offline-macos-x64.tar.gz`     |
| Linux (x64 / arm64)   | `rea-mobile-offline-linux-<arch>.tar.gz`  |

**Get it:** in this repo on GitHub, open **Actions → REA Mobile offline bundles → Run
workflow**, then download your platform from the finished run's *Artifacts*. Pushing a
tag such as `rea-mobile-v1.0.0` publishes all of them as a release instead.

Or build it yourself (needs internet, Node.js 22+, git and tar; Windows targets also need zip/unzip):

```bash
cd rea-mobile
node scripts/build-offline.mjs --target windows-x64   # or linux-x64, linux-arm64, macos-x64, macos-arm64
# -> dist/rea-mobile-offline-windows-x64.zip
```

Options: `--rea-version 6.7.0` (default: latest), `--node-version 22.22.0`, `--out <dir>`, `--no-archive`.

**Run it:** extract the archive and start it:

- Windows: double-click `start.bat`
- macOS: double-click `start.command` (it clears the download quarantine flag so the bundled Node.js can run)
- Linux: `./start.sh`

Then open the printed link on your phone, as in step 3 below.

The bundle contains:

```
rea-mobile-offline-<platform>/
├── node/        portable Node.js
├── rea/         REA (rea-agents) and all npm dependencies, with native parts for that platform
├── rea-docs/    REA's docs, README and license from the morluto/rea repository
├── app/         this server and phone app
└── start.sh | start.command | start.bat
```

Offline means REA itself and its built-in analyzers (APK, .NET, Go, Rust, WASM,
JavaScript/Electron, SQLite, artifacts and more). Analyses that use an outside tool,
such as Ghidra, Hopper, IDA, JADX, adb or Chrome, still need that tool installed on
the computer. They don't need internet either.

## Setup without the bundle

On the computer:

1. Install Node.js 22.19+ and REA:
   ```bash
   npm install --global rea-agents
   rea doctor
   ```
   (Without a global install the server falls back to `npx -y rea-agents@latest` on macOS/Linux.)
2. Start REA Mobile:
   ```bash
   cd rea-mobile
   node server.mjs
   ```
3. It prints a link like `http://192.168.1.20:8787/#token=…`. Open it on your phone
   (the phone must be on the same network).
4. Add it to your home screen: iPhone: Share → **Add to Home Screen**. Android
   (Chrome): ⋮ → **Add to Home screen**.

The token is saved on the phone, so later you just open the home-screen icon while
the server is running.

## Configuration

| Variable                    | Default                    | Purpose                                             |
| --------------------------- | -------------------------- | --------------------------------------------------- |
| `PORT`                      | `8787`                     | Port to listen on                                   |
| `HOST`                      | `0.0.0.0`                  | Interface to bind (`127.0.0.1` for local-only)      |
| `REA_MOBILE_TOKEN`          | saved in `~/.rea-mobile-token` | A fixed access token                            |
| `REA_MOBILE_TOKEN_FILE`     | `~/.rea-mobile-token`      | Where the generated token is kept between restarts  |
| `REA_BIN`                   | bundled REA, else `rea` on PATH, else `npx` | REA executable, or a path to `scripts/rea.mjs` |
| `REA_MOBILE_DOCS`           | bundled `rea-docs/`        | REA docs folder for the Docs tab (needs an `index.json` from the build script) |
| `REA_MOBILE_UPLOADS`        | `~/rea-mobile-uploads`     | Where files uploaded from the phone are saved       |
| `REA_MOBILE_TIMEOUT_MS`     | `900000` (15 min)          | Maximum run time per command                        |
| `REA_MOBILE_MAX_UPLOAD_MB`  | `2048`                     | Upload size limit                                   |

The token is generated on first start and reused afterwards, so a paired phone stays
paired. Delete `~/.rea-mobile-token` to revoke access and get a new link.

## Security

Anyone with the link can run REA commands on your computer, and some REA commands
(debuggers, Frida, Rizin) can run arbitrary code. Treat the token like a password.

- Every API call requires the token. It travels in the link's `#fragment`, which is
  never sent to the server or written to logs.
- Commands run without a shell (no command injection), and only names from
  `rea --help` are accepted. `setup`, `uninstall` and `update` are blocked from the phone.
- Traffic is plain HTTP on your local network. Use it only on networks you trust.
  To reach it from outside your home, put it behind a VPN such as Tailscale or
  WireGuard rather than exposing the port to the internet. Tailscale also gives you
  HTTPS, which enables offline caching and Chrome's full "Install app" option.

## Files

```
rea-mobile/
├── server.mjs              bridge server (no dependencies)
├── scripts/
│   ├── build-offline.mjs   builds the offline bundle
│   └── rea-docs.mjs        copies REA's docs for the Docs tab
├── android/                Android app (see android/README.md)
└── public/                 the phone app
    ├── index.html
    ├── app.js
    ├── docs.js             offline docs reader
    ├── styles.css
    ├── sw.js               offline app-shell cache (HTTPS or localhost only)
    ├── manifest.webmanifest
    └── icon.svg
```
