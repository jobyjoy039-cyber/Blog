# Replay Studio

Pick a video you already have, connect your YouTube channel, and press **Start stream**. Replay Studio
plays the file into **one** YouTube live broadcast, starts it again as soon as it ends, and keeps doing that
until you press **Stop stream**. The watch URL and live chat stay the same the whole time.

- The dashboard works on phones (Android Chrome) and desktop browsers.
- The stream runs on a Linux host as two background services. Closing the browser, locking your phone or
  taking your phone off Wi-Fi doesn't affect it. The **host** has to stay powered on, awake and online.
- It uses only the official YouTube Data API v3 / Live Streaming API with Google OAuth, and sends video
  over YouTube's **RTMPS** ingest. You don't need a paid streaming service.

```
Phone / browser ──HTTPS or LAN──► replay-studio-api (FastAPI + React dashboard)
                                        │  SQLite (state, stop intent, schedules, encrypted tokens)
                                        ▼
                                  replay-studio-worker ──► FFmpeg -re -stream_loop -1 ──RTMPS──► YouTube
                                        └──────── YouTube Live Streaming API (OAuth) ────────────►
```

---

## 1. Requirements

* Linux host (Ubuntu 22.04/24.04 or Debian 12 tested commands below), Python ≥ 3.11.
* FFmpeg with RTMPS support (Ubuntu/Debian packages have it): `sudo apt install ffmpeg`
* Node.js ≥ 18 only to build the dashboard once (`sudo apt install nodejs npm`).
* For 720p30: about one modern CPU core for x264 `veryfast`, plus **≥ 6 Mbps upload** for the
  default 4 Mbps video.
* A Google account that owns a YouTube channel **eligible for live streaming** (section 3).

## 2. Quick start (run from this folder)

```bash
cd replay-studio
sudo apt install -y ffmpeg python3-venv nodejs npm fonts-dejavu-core
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
(cd frontend && npm ci && npm run build)          # builds the dashboard into the Python package
cp config.example.toml config.toml                  # then edit: public_url, google client_id/secret
mkdir -p media                                      # optional: drop videos here to pick them on the host
replay-studio set-password                          # dashboard password (≥ 10 characters)
replay-studio check                                 # verifies ffmpeg, RTMPS, OAuth config, password
```

Start the two processes in two terminals. Use systemd (section 6) for real use:

```bash
. .venv/bin/activate && replay-studio worker
. .venv/bin/activate && replay-studio api           # http://<host-ip>:8787
```

### Offline demo (no Google account needed)

`./scripts/demo.sh` runs the dashboard and worker against a built-in **fake YouTube API** that has a real
local RTMP receiver. Open `http://<host-ip>:8790` and log in with `demo-password-123`. Then
**Connect YouTube account** → **Choose from host media folder** → `demo.mp4` → **Start stream**.
Nothing is sent to YouTube.

## 3. YouTube channel eligibility

1. Verify the channel at <https://www.youtube.com/verify> (phone verification).
2. Enable live streaming: YouTube Studio → **Create → Go live**. The **first** activation can take
   **up to 24 hours**.
3. The channel must have no live-streaming restrictions (for example a Community Guidelines strike or a
   recent live-stream ban). Replay Studio shows YouTube's reason when a start is refused
   (`liveStreamingNotEnabled`, `livePermissionBlocked`, `insufficientLivePermissions`, …).
4. Brand-account channels: sign in to Google and pick the brand channel on the consent screen. Then paste
   your `youtube.com/@handle` link into the dashboard's **Verify** box to confirm it's the right channel.

## 4. Google Cloud OAuth setup

1. <https://console.cloud.google.com/> → create a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**. It also covers the Live Streaming
   endpoints.
3. **OAuth consent screen**: User type **External**, app name "Replay Studio", your email. Add the scope
   `https://www.googleapis.com/auth/youtube`. Under **Test users**, add the Google account that owns
   the channel. In *Testing* mode, Google expires refresh tokens after 7 days. To avoid reconnecting every
   week, **publish** the app (*In production*, unverified is fine for your own account; you'll click through
   an "unverified app" warning).
4. **Credentials → Create credentials → OAuth client ID → Web application**.
   Under **Authorized redirect URIs**, add exactly `<server.public_url>/api/youtube/callback`, for example
   `http://localhost:8787/api/youtube/callback` or `https://replay.example.com/api/youtube/callback`.
   Google only allows plain `http://` for `localhost`. On a LAN IP, connect once from a browser on the host
   itself (`public_url = "http://localhost:8787"`), or use the HTTPS setup in section 7.
5. Copy the client ID and secret into `config.toml` → `[google]`, then restart the API.
6. Dashboard → **Connect YouTube account**. The channel name and avatar appear when it succeeds.

**Quota.** The default allocation is 10,000 units/day, and each live call costs 1 unit. While live, the
worker polls every 30 s (broadcast + stream) and fetches metrics every 60 s. That's about 7,200 units/day for
one 24-hour stream. Raise `youtube_poll_seconds` if you also use the quota elsewhere. If quota runs out
while live, **streaming continues**, and the dashboard explains that status checks are paused until quota
resets at midnight Pacific time.

## 5. Using it

1. **Connect YouTube**, then optionally verify your `@handle` / `/channel/UC…` link.
2. **Video**: upload from your phone or pick a file from the host's `media_dir`.
   * Uploads use 8 MB chunks and resume. If the connection drops, the dashboard keeps retrying with
     backoff. If you reload the page, select the same file again and it continues from where it stopped.
   * Every file is checked with ffprobe: duration, resolution, audio, codec. Unreadable, truncated or
     still-copying files are reported as **invalid** with the reason.
   * A **loop-ready copy** is made once. The video is stream-copied (re-encoded only if it has a variable
     frame rate or odd timestamps), and the audio is converted to PCM, trimmed or padded to the **exact**
     video length. A silent video gets a silent track. This is what keeps sync perfect over thousands of
     loops (section 9).
3. **Stream details**: title, description (pre-filled with the disclosure "Prerecorded video playing on
   repeat."), privacy (**Unlisted** by default; **Public** needs an extra confirmation), audience
   (made for kids yes/no, required), and the rights confirmation. Playback is **Loop until I stop**.
   There's no duration limit, no loop count and no automatic end.
4. **Start now** or **Schedule**. Schedule times are entered and shown in **Asia/Kolkata** (`ui.timezone`)
   and stored in UTC. A scheduled stream creates the YouTube event right away, so the watch link exists
   in advance. It starts ingest 90 s before the scheduled time and also loops until you stop it.
5. **While live**, the dashboard shows the watch link (**Copy watch link**, **Open in YouTube Studio**), the
   state (it says **Live** only after YouTube reports `lifeCycleStatus = live`), time live, position in the
   loop, completed loops, YouTube ingest status/health with configuration issues, encoder speed/bitrate/fps,
   and viewer metrics. Metrics YouTube doesn't return are labelled *Unavailable*. The red
   **Stop stream** bar stays at the bottom of the screen on mobile.
6. **Audience tools**: an optional subscribe overlay. You set the text, how often it shows (every N
   minutes), for how long, and top or bottom. **Preview overlay** renders it with the exact FFmpeg filter
   used on air. There are also chat messages and discussion questions to **copy and post yourself**, plus
   share text. Replay Studio never posts, views, likes or subscribes on its own, and has no automated
   engagement of any kind.

## 6. Run as services (systemd)

```bash
sudo ./scripts/install.sh            # installs to /opt/replay-studio, data in /var/lib/replay-studio
sudo nano /etc/replay-studio/config.toml
sudo -u replaystudio env REPLAY_STUDIO_CONFIG=/etc/replay-studio/config.toml \
     /opt/replay-studio/.venv/bin/replay-studio set-password
sudo systemctl enable --now replay-studio-api replay-studio-worker
journalctl -u replay-studio-worker -f            # logs (stream keys / tokens are redacted)
```

Keep the host awake: `sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`.
On a laptop, also set `HandleLidSwitch=ignore` in `/etc/systemd/logind.conf`.
Put videos for the host picker in `/var/lib/replay-studio/media` (owned by `replaystudio`).

## 6b. Run it on an Android phone (Redmi Note 8 Pro and other arm64 phones)

The phone itself becomes the streaming host. It runs Replay Studio inside **Termux**, a Linux
environment for Android. You don't need root. You control it from Chrome on the same phone
(`http://localhost:8787`) or from a computer on the same Wi-Fi.

**What the phone must do for the whole stream:** stay powered on, charging, and connected to the internet
(Wi-Fi or mobile data). The screen can be off and locked, and you can close Chrome. Turning off Wi-Fi
*and* mobile data stops the stream. If the network switches (Wi-Fi ↔ mobile data), the dashboard shows
**Reconnecting** and the stream returns to the same broadcast.

**Low-power mode.** `config.android.toml` sets `encoder.mode = "copy"`. When you add a video, it's encoded
once to YouTube's 720p30 spec. That takes roughly as long as the video, or longer on a phone. After that,
streaming only copies the video and encodes the audio. Measured CPU use is about 11× lower than live
encoding (5% vs 55% of a core on the test machine). This keeps the Helio G90T cool and avoids thermal
throttling. The subscribe overlay isn't available in this mode.

### Install

1. Install **Termux**, **Termux:API** and **Termux:Boot** from **F-Droid** (<https://f-droid.org>). Don't
   use the Play Store version of Termux, which is outdated. Open Termux:Boot once.
2. In Termux:
   ```bash
   pkg install -y git
   git clone <this repository URL> && cd <repo>/replay-studio
   bash scripts/termux-install.sh       # 10-30 min the first time; allow the storage permission popup
   nano config.toml                     # paste Google client_id / client_secret (section 4)
   bash scripts/termux-start.sh
   ```
3. In Google Cloud, the OAuth redirect URI is `http://localhost:8787/api/youtube/callback`. Open
   `http://localhost:8787` in **Chrome on the phone**, log in, and connect YouTube there. Google only
   allows `http://` redirects for `localhost`, so do the Connect step on the phone itself. After that you
   can also control it from a computer at `http://<phone-Wi-Fi-IP>:8787`.
4. Put your video in the phone's **Movies** folder. Then use **Choose from host media folder**, which
   avoids a second copy. Or use **Upload video from this device**.
5. Run `replay-studio check` (with `. .venv/bin/activate`). It must say `RTMPS : supported`. If Termux's
   FFmpeg ever lacks RTMPS, run `pkg upgrade ffmpeg`.

### Keep MIUI from killing it (important on Xiaomi/Redmi)

* Settings → Apps → Manage apps → **Termux** → **Autostart: on**, **Battery saver: No restrictions**.
  Do the same for **Termux:API** and **Termux:Boot**.
* Open recent apps, then long-press (or pull down) the Termux card → **Lock**.
* Settings → Battery & performance → turn **Battery saver** and **Ultra battery saver** off.
* `termux-start.sh` takes a **wake lock**, shown as "wake lock held" in the Termux notification. Leave that
  notification alone.
* Termux:Boot restarts the services after a phone reboot. A live session then resumes into the **same**
  broadcast, and a stopped one never restarts.
* The Redmi Note 8 Pro's official updates end at Android 11, so Android 12's "phantom process killer"
  doesn't apply. On a custom Android 12+ ROM, disable it once over adb:
  `adb shell device_config put activity_manager max_phantom_processes 2147483647`.

### Day-to-day

```bash
bash scripts/termux-start.sh     # start services (idempotent)
bash scripts/termux-stop.sh      # stop services (does NOT end the broadcast; use Stop stream for that)
tail -f ~/replay-studio-data/logs/worker.log
```

Practical tips:
* Keep the phone on a charger, out of its case, somewhere cool.
* Mobile data: 720p at 3 Mbps uses about **1.4 GB per hour** (≈ 33 GB per day). Prefer Wi-Fi.
* If YouTube Studio reports low bitrate, lower `video_bitrate_k`. YouTube's 720p30 minimum is 3000; for a
  weak connection use `width = 854`, `height = 480`, `video_bitrate_k = 1500`. Then tap
  **Prepare again** on the video so it's re-encoded with the new settings.
* Charging 24/7 wears the battery. Unplugging now and then while streaming is fine.

## 7. Accessing the dashboard

**On your local network (simplest).** Keep `host = "0.0.0.0"` and open `http://<host-LAN-IP>:8787` on
your phone. Login is protected by your dashboard password (scrypt-hashed). The session cookie is HttpOnly
and SameSite and expires after `session_hours`. Login is rate-limited. Restrict the port to your LAN:
`sudo ufw allow from 192.168.0.0/16 to any port 8787 && sudo ufw enable`. Plain HTTP on a LAN can be read
by others on the same Wi-Fi, so use HTTPS when that matters.

**Remote control over HTTPS.**
* *Caddy* (automatic Let's Encrypt): point a DNS name at your public IP and forward ports 80/443. Use
  `deploy/Caddyfile`, which adds a second password layer with `basic_auth`. Set `host = "127.0.0.1"`,
  `public_url = "https://replay.example.com"` and `secure_cookies = true`, then add the https redirect URI in
  Google Cloud.
* *nginx + certbot*: `deploy/nginx-replay-studio.conf`.
* *No open ports*: a private overlay network such as Tailscale (`tailscale serve --bg 8787`)
  gives you a `https://<machine>.<tailnet>.ts.net` URL that only your devices can reach.

The stream never depends on the dashboard connection. Losing remote access only means you can't press
Stop until you reconnect. You can always end the event in YouTube Studio as a fallback.

## 8. Reliability behaviour

| Situation | What happens |
|---|---|
| Browser closed / phone locked / phone offline | Nothing changes; the worker is a separate service. Reopen the dashboard to see the current session. |
| Double-tapped **Start**, two tabs | One active session per channel (unique DB index) plus an idempotency key per form. Duplicates get back the existing session. |
| Worker crash / host reboot mid-stream | FFmpeg dies with the worker (PDEATHSIG + systemd cgroup). On restart it checks the broadcast on YouTube **before** doing anything. If it's still live, it resumes the encoder at the saved loop position into the **same** broadcast with no new transition. Resources created right before a crash are found and adopted, not duplicated. |
| Network or encoder failure | Status **Reconnecting**. Retries back off 2 s → 60 s into the same broadcast. It **never creates a new broadcast** during recovery. After `reconnect_give_up_seconds` it shows **Recovery failed** with Retry and Stop. |
| YouTube ends or revokes the event | Status **Ended by YouTube** with the reason. Nothing restarts; you start a new event yourself. |
| YouTube access revoked / quota exhausted while live | Media keeps flowing; the dashboard explains what to fix (reconnect, or wait for quota). |
| **Stop stream** | The stop intent is saved before the request returns. Within ~0.5 s the media stops and all retries are cancelled. Then the worker ends the broadcast (`transition → complete`). If it never went live, the unused upcoming event is deleted instead. If the API is unreachable, the status is **End confirmation pending** and only the end request is retried. **Ended** appears when YouTube confirms. A stopped stream is never resumed, including after restarts. |

## 9. Encoding details (verified against current docs and FFmpeg 6.1)

* One long-running process: `ffmpeg -re -stream_loop -1 -i <loop-ready file> … -f flv rtmps://a.rtmps.youtube.com/live2/<key>`.
  It's built as an argument list and never run through a shell. The ingest URL comes from
  `liveStreams.cdn.ingestionInfo.rtmpsIngestionAddress`.
* 1280×720, 30 fps, H.264 High, CBR 4000 kbps (`nal-hrd=cbr`), keyframe every 2 s (`-g 60`, scene-cut off),
  AAC 128 kbps stereo at 44.1 kHz. This follows YouTube's encoder settings page: 2 s keyframes (never over
  4 s), AAC 128 kbps stereo at 44.1 kHz, CBR. YouTube lists 3 Mbps as the 720p30 H.264 minimum and
  recommends more, so raise `video_bitrate_k` if your upload allows.
* Broadcast settings: `enableAutoStop=false` (YouTube won't end it on its own), `enableAutoStart=false`
  (Replay Studio transitions only after the ingest is `active`), `monitorStream.enableMonitorStream=false`
  (allows ready → live directly), DVR on, latency `normal`.
* **Why the loop-ready copy matters.** AAC audio comes in 1024-sample frames plus encoder priming, so a
  normal MP4's audio is 10–40 ms longer than its video. `-stream_loop` offsets each pass by the longer
  stream. With the raw MP4, I measured A/V drift of about 2–9 ms **per loop**, which would be seconds of
  drift after a day. Also, `aresample=first_pts=0` breaks timestamps at the first loop on FFmpeg 6.1, so
  it isn't used. With the sample-exact PCM copy, the measured loop period is exactly the file length and
  the A/V offset is constant (−3 ms, the AAC encoder's own alignment) at every pass. There's no black
  frame, no silence and no encoder restart at the boundary.

## 10. Long broadcasts and archives

YouTube's help page *"Live stream archives"* (answer 6247592) says it automatically archives streams
**under 12 hours**. Streams **over 12 hours may not be captured at all**. A loop that runs for days will
probably have **no** full replay (VOD) afterwards. The live broadcast itself is unaffected. If you need a
replay, keep the source file; you already have it. DVR (rewind while live) is enabled, but YouTube limits
how far viewers can seek back. Check YouTube's current help, because these limits change.

## 11. Security notes

* OAuth tokens are stored encrypted (Fernet) in SQLite. The key lives in `data_dir/secret.key` (mode 600)
  and stays on the host. Stream keys are never stored or shown; they're fetched from YouTube when needed.
* Logs, FFmpeg output, error messages, the activity log and `/api/diagnostics` all pass through a redactor
  that removes stream keys, bearer/refresh tokens, OAuth codes and the client secret.
* Mutating API calls require the login cookie **and** a custom header, which blocks cross-site requests.
  OAuth uses a one-time `state`.
* Host media selection is limited to `paths.media_dir` (resolved paths only; symlinks out of the folder are
  refused). Uploads only accept video extensions and are bounded by `max_upload_gb`, `library_quota_gb`
  and `min_free_disk_gb`.
* Back up `data_dir`. Losing `secret.key` means you have to reconnect YouTube.

## 12. Tests

```bash
. .venv/bin/activate
pytest -q                                   # ~36 tests, ~5 minutes; needs ffmpeg
pytest -q backend/tests/test_unit.py        # fast unit/API tests only
```

The end-to-end tests start the **fake YouTube API** (real lifecycle rules, real RTMP receiver that records
what it receives), the API and the worker as separate processes. They cover:

* three or more consecutive loops: each pass exactly one file length, A/V offset constant, no timestamp
  gaps, no black frames, no silence;
* dashboard/API closed while the worker keeps streaming, and reopening shows the same session;
* 12 concurrent Start clicks plus a `kill -9` of the worker → 1 broadcast, 1 stream, 1 `live` transition;
* ingest outage → Reconnecting → back to Live in the same broadcast; Stop while reconnecting → Ended,
  never resumes, not even after a worker restart;
* Stop while the YouTube API is down → End confirmation pending → Ended;
* event ended by YouTube; revoked access while live; silent video; scheduled start; Stop before going live.

## 13. Unlisted end-to-end test on real YouTube (requires your account)

These need your Google account, so they can't be automated here. Use **Unlisted** for all of them.

1. Prepare a short (~20–60 s) MP4 so loops come quickly. Start it **Unlisted** and wait for **Live**.
2. Open the watch link on another device. Confirm it plays, and that the dashboard's loop counter goes up
   while the **same URL** and chat keep working across at least 3 loops. Watch the boundary for a smooth
   restart.
3. Close the dashboard and turn off your phone's Wi-Fi for a few minutes. The stream should continue.
4. On the host, briefly drop the network (`sudo ip link set <iface> down; sleep 20; sudo ip link set <iface> up`).
   Expect **Reconnecting** → **Live**, same watch URL.
5. `sudo systemctl restart replay-studio-worker`. Expect the same broadcast, with no new event in YouTube
   Studio → Live → Manage.
6. Press **Stop stream**. Expect **Ended** in the dashboard, and the event shown as ended in YouTube Studio.
7. `sudo systemctl restart replay-studio-worker` again. Nothing should start.

## 14. Limitations

* In low-power `copy` mode (the Android default) there is no subscribe overlay, and changing resolution or bitrate requires **Prepare again** on the video.
* The Android/Termux setup was tested by simulating its scripts on Linux; it has not been run on a physical Redmi yet.
* Overlay changes apply when the next stream starts. The running encoder isn't restarted for cosmetic
  changes.
* Reconnecting after an outage briefly interrupts ingest (as with any encoder). YouTube keeps the event
  open because auto-stop is off, and the worker resumes at the saved loop position.
* The loop-ready copy stores audio as PCM, which takes about 635 MB per hour of video. Re-encoding a
  variable-frame-rate source takes time once, at import.
* Viewer metrics are whatever `videos.list` returns. YouTube hides some values, which show as *Unavailable*.
* YouTube can still end a broadcast for policy or eligibility reasons. Replay Studio reports it and doesn't
  start a new event automatically.
