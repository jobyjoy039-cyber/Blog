"""Entry point used by the Android app (embedded Python via Chaquopy).

The Java foreground service calls start() once per process. It runs the same API server and stream worker
as the Linux services, in two background threads, with FFmpeg/ffprobe shipped inside the APK.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import threading
import time
from pathlib import Path

_started = False
_lock = threading.Lock()
_cfg = None

CONFIG_TEMPLATE = """# Replay Studio (Android app). Edit with care; restart the app after changes.
[server]
host = "0.0.0.0"
port = 8787
public_url = "http://localhost:8787"
session_hours = 720

[paths]
data_dir = "{data}"
media_dir = "{movies}"

[limits]
max_upload_gb = 8
library_quota_gb = 30
min_free_disk_gb = 1

[encoder]
mode = "copy"
prepare_preset = "veryfast"
video_bitrate_k = 3000
ingest_protocol = "rtmps"

[worker]
reconnect_give_up_seconds = 0

[ui]
timezone = "Asia/Kolkata"
"""


def start(files_dir: str, native_lib_dir: str, movies_dir: str) -> str:
    """Start API + worker (idempotent). Returns the dashboard URL."""
    global _started, _cfg
    with _lock:
        if _started:
            return "http://127.0.0.1:8787/"
        files = Path(files_dir)
        data = files / "data"
        data.mkdir(parents=True, exist_ok=True)
        cfg_path = files / "config.toml"
        if not cfg_path.exists():
            cfg_path.write_text(CONFIG_TEMPLATE.format(data=data, movies=movies_dir), encoding="utf-8")
        os.environ["REPLAY_STUDIO_CONFIG"] = str(cfg_path)
        os.environ["REPLAY_STUDIO_ENCODER_FFMPEG"] = str(Path(native_lib_dir) / "libffmpeg.so")
        os.environ["REPLAY_STUDIO_ENCODER_FFPROBE"] = str(Path(native_lib_dir) / "libffprobe.so")
        os.environ.setdefault("TMPDIR", str(files / "tmp"))
        Path(os.environ["TMPDIR"]).mkdir(exist_ok=True)

        from .security import RedactingFilter, setup_logging
        setup_logging()
        fh = logging.handlers.RotatingFileHandler(data / "replay-studio.log", maxBytes=2_000_000, backupCount=2)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        fh.addFilter(RedactingFilter())
        logging.getLogger().addHandler(fh)

        from .config import load_config
        _cfg = load_config()
        threading.Thread(target=_run_worker, name="replay-worker", daemon=True).start()
        threading.Thread(target=_run_api, name="replay-api", daemon=True).start()
        _started = True
        logging.getLogger("replay_studio.android").info("Started (ffmpeg %s)", os.environ["REPLAY_STUDIO_ENCODER_FFMPEG"])
        return "http://127.0.0.1:8787/"


def _run_worker() -> None:
    from .worker import Worker
    while True:  # a crash in the loop must never leave the phone without its worker
        try:
            Worker(_cfg).run_forever()
        except Exception:
            logging.getLogger("replay_studio.android").exception("Worker crashed; restarting in 3 s")
        time.sleep(3)


def _run_api() -> None:
    import uvicorn
    from .api import create_app
    while True:
        try:
            server = uvicorn.Server(uvicorn.Config(create_app(_cfg), host=_cfg.server.host, port=_cfg.server.port,
                                                   log_config=None, access_log=False))
            server.run()
        except Exception:
            logging.getLogger("replay_studio.android").exception("API crashed; restarting in 3 s")
        time.sleep(3)


def status() -> str:
    """Short status line for the Android notification (JSON)."""
    if _cfg is None:
        return json.dumps({"text": "Starting…", "live": False})
    try:
        from .db import DB
        s = DB(_cfg.db_path).active_session()
        if not s:
            return json.dumps({"text": "No active stream", "live": False})
        label = {"live": "LIVE", "reconnecting": "Reconnecting…", "end_pending": "Ending…",
                 "scheduled": "Scheduled", "failed": "Recovery failed — open app"}.get(s["state"], s["state"].replace("_", " "))
        dur = s.get("media_duration") or 0
        loops = int((s.get("played_total") or 0) // dur) if dur else 0
        text = f"{label} · {s['title'][:40]}" + (f" · {loops} loops" if s["state"] == "live" else "")
        return json.dumps({"text": text, "live": s["state"] == "live"})
    except Exception as e:  # pragma: no cover
        return json.dumps({"text": f"Status unavailable ({type(e).__name__})", "live": False})
