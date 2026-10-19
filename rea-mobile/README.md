# REA Mobile

Use [REA: Reverse Engineer Anything](https://github.com/morluto/rea) from your phone.

REA needs Node.js 22+ and desktop tools such as Ghidra, Hopper, IDA, JADX or Chrome,
so it can't run on a phone itself. REA Mobile is a small server you run on the
computer that has REA, plus a phone app (an installable web app) that connects to it
over your Wi-Fi.

```
 phone (REA Mobile app)  ── Wi-Fi ──▶  your computer: server.mjs ──▶ rea <command>
```

## What it does

- Run any REA command (`doctor`, `inspect-artifact`, `inspect-android-package`,
  `analyze-javascript-application`, `decompile`, …) with output streamed live to your phone
- Quick-action chips for the common analyses
- **Upload** a file from your phone (an APK, binary, app archive…) to the computer and
  analyze it in one tap
- Per-command `--help`, a choice of output format (Markdown, JSON, YAML, TOON), Stop, Copy and Share
- History of recent runs with saved output, so you can rerun or reread them
- Works from the home screen like a native app; light and dark themes

## Setup

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
| `REA_MOBILE_TOKEN`          | random each start          | A fixed access token, so the phone keeps working across restarts |
| `REA_BIN`                   | `rea` on PATH, else `npx`  | REA executable, or a path to `scripts/rea.mjs`      |
| `REA_MOBILE_UPLOADS`        | `~/rea-mobile-uploads`     | Where files uploaded from the phone are saved       |
| `REA_MOBILE_TIMEOUT_MS`     | `900000` (15 min)          | Maximum run time per command                        |
| `REA_MOBILE_MAX_UPLOAD_MB`  | `2048`                     | Upload size limit                                   |

Tip: set `REA_MOBILE_TOKEN` to a long random value so you don't have to re-pair the
phone each time the server starts.

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
└── public/                 the phone app
    ├── index.html
    ├── app.js
    ├── styles.css
    ├── sw.js               offline app-shell cache (HTTPS or localhost only)
    ├── manifest.webmanifest
    └── icon.svg
```
