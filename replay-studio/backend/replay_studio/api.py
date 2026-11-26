"""Dashboard HTTP API (Starlette via .web). The stream itself runs in the separate worker service."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from starlette.responses import HTMLResponse

from .web import (App, F, FileResponse, HTTPException, JSONResponse, Model, RedirectResponse, Request, Response,
                  StaticFiles)

from . import db as S
from . import media as M
from .config import Config, load_config
from .db import DB
from .encoder import Overlay, overlay_filter
from .security import SecretBox, hash_password, redact, setup_logging, verify_password
from .youtube import YouTubeClient, YouTubeError, studio_url, watch_url

log = logging.getLogger("replay_studio.api")

COOKIE = "rs_session"
CSRF_HEADER = "x-replay-studio"
DEFAULT_DESCRIPTION = ("Prerecorded video playing on repeat.\n\n"
                       "If you enjoy it, consider subscribing to the channel.")
STATE_LABELS = {
    S.SCHEDULED: "Scheduled", S.PENDING: "Starting", S.CREATING: "Creating broadcast",
    S.STARTING_ENCODER: "Starting encoder", S.WAITING_INGEST: "Waiting for YouTube to receive video",
    S.GOING_LIVE: "Going live (waiting for YouTube)", S.LIVE: "Live", S.RECONNECTING: "Reconnecting",
    S.FAILED: "Recovery failed", S.STOPPING: "Stopping", S.END_PENDING: "End confirmation pending",
    S.ENDED: "Ended", S.CANCELLED: "Cancelled", S.ENDED_BY_YOUTUBE: "Ended by YouTube", S.ERROR: "Could not start",
}
TITLE_BAD = re.compile(r"[<>]")


class LoginBody(Model):
    password: str


class ChannelBody(Model):
    url: str


class ImportBody(Model):
    path: str


class UploadCreate(Model):
    filename: str = F(min_length=1, max_length=255)
    size: int = F(gt=0)


class OverlayBody(Model):
    enabled: bool = False
    text: str = F("Enjoying the stream? Subscribe!", max_length=120)
    every_minutes: float = F(10, ge=1, le=1440)
    show_seconds: float = F(8, ge=2, le=600)
    position: Literal["top", "bottom"] = "bottom"


class SessionCreate(Model):
    media_id: str
    title: str = F(min_length=1, max_length=100)
    description: str = F(DEFAULT_DESCRIPTION, max_length=5000)
    privacy: Literal["private", "unlisted", "public"] = "unlisted"
    made_for_kids: bool
    confirm_rights: bool = False
    confirm_public: bool = False
    scheduled_start: str | None = None   # ISO 8601; naive values are read in the UI time zone
    idempotency_key: str | None = F(None, max_length=80)
    overlay: OverlayBody | None = None

    def validate(self) -> None:
        if TITLE_BAD.search(self.title) or TITLE_BAD.search(self.description):
            raise ValueError("YouTube does not allow < or > in titles and descriptions")


class SetupBody(Model):
    password: str = F(min_length=10, max_length=200)


class GoogleBody(Model):
    client_id: str = F(min_length=10, max_length=300)
    client_secret: str = F(min_length=6, max_length=300)


class ChatBody(Model):
    messages: list[str] = F(default_factory=list, max_length=50)


def create_app(cfg: Config | None = None, yt: YouTubeClient | None = None) -> App:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    db = DB(cfg.db_path)
    box = SecretBox(cfg.data_dir)
    yt = yt or YouTubeClient(cfg, db, box)
    app = App()
    app.state.cfg, app.state.db, app.state.yt = cfg, db, yt
    failures: dict[str, list[float]] = {}
    upload_locks: dict[str, threading.Lock] = {}

    # Google OAuth client can be entered in the dashboard (needed in the Android app, handy on Linux).
    def apply_google_settings() -> None:
        g = db.get_setting("google_client")
        ct = db.get_secret("google_client_secret")
        if g and ct:
            cfg.google.client_id = g["client_id"]
            cfg.google.client_secret = box.decrypt(ct)
    apply_google_settings()

    # ------------------------------------------------------------ auth
    def password_hash() -> str | None:
        return db.get_setting("password_hash")

    def pw_version() -> str:
        return (password_hash() or "")[-16:]

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        # /api/youtube/callback is checked by its one-time OAuth `state` instead of the cookie: on Android the
        # Google sign-in has to happen in Chrome (Google blocks sign-in inside app WebViews), and Chrome does
        # not share the app's login cookie.
        if path.startswith("/api/") and path not in ("/api/login", "/api/health", "/api/setup",
                                                     "/api/setup-status", "/api/youtube/callback"):
            if not box.check_session(request.cookies.get(COOKIE), pw_version()):
                return JSONResponse({"detail": "Your dashboard session has expired. Please log in again.",
                                     "code": "auth_required"}, status_code=401)
            if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != "1":
                return JSONResponse({"detail": "Missing request header"}, status_code=403)
        try:
            resp = await call_next(request)
        except YouTubeError as e:
            return yt_error_response(e)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    def yt_error_response(e: YouTubeError) -> JSONResponse:
        code = {"auth": 401, "quota": 429, "eligibility": 403}.get(e.kind, 502)
        return JSONResponse({"detail": e.friendly, "code": f"youtube_{e.kind}", "reason": e.reason},
                            status_code=409 if code == 401 else code)

    @app.exception_handler(YouTubeError)
    async def _yt_exc(request: Request, e: YouTubeError):
        return yt_error_response(e)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    def is_local(request: Request) -> bool:
        return (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost")

    @app.get("/api/setup-status")
    def setup_status():
        return {"needs_password": not password_hash()}

    @app.post("/api/setup")
    def setup(body: SetupBody, request: Request, response: Response):
        """First run without a command line (Android app): set the password from the device itself."""
        if password_hash():
            raise HTTPException(409, "A password is already set.")
        if not is_local(request):
            raise HTTPException(403, "Set the first password on the host device itself.")
        db.set_setting("password_hash", hash_password(body.password))
        token = box.make_session(cfg.server.session_hours, pw_version())
        response.set_cookie(COOKIE, token, max_age=cfg.server.session_hours * 3600, httponly=True,
                            samesite="lax", secure=cfg.server.secure_cookies, path="/")
        return {"ok": True}

    @app.post("/api/login")
    def login(body: LoginBody, request: Request, response: Response):
        ip = request.client.host if request.client else "?"
        recent = [t for t in failures.get(ip, []) if time.time() - t < 300]
        failures[ip] = recent
        if len(recent) >= 10:
            raise HTTPException(429, "Too many failed attempts. Wait 5 minutes.")
        stored = password_hash()
        if not stored:
            raise HTTPException(503, "No dashboard password is set yet. Open the dashboard on the host device "
                                     "itself to create one (or run: replay-studio set-password).")
        if not verify_password(body.password, stored):
            failures[ip].append(time.time())
            time.sleep(0.5)
            raise HTTPException(401, "Wrong password.")
        token = box.make_session(cfg.server.session_hours, pw_version())
        response.set_cookie(COOKIE, token, max_age=cfg.server.session_hours * 3600, httponly=True,
                            samesite="lax", secure=cfg.server.secure_cookies, path="/")
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    # ------------------------------------------------------------ session view
    def view(s: dict | None) -> dict | None:
        if not s:
            return None
        now = time.time()
        dur = s.get("media_duration") or 0
        played = s.get("played_total") or 0
        live_since = s.get("actual_start_utc") or s.get("live_confirmed_at")
        end = s.get("ended_at") or now
        media = db.get_media(s["media_id"])
        bid = s.get("broadcast_id")
        return {
            "id": s["id"], "state": s["state"], "state_label": STATE_LABELS.get(s["state"], s["state"]),
            "active": bool(s["active"]), "stop_requested": bool(s["stop_requested_at"]),
            "title": s["title"], "description": s["description"], "privacy": s["privacy"],
            "made_for_kids": bool(s["made_for_kids"]), "media_id": s["media_id"],
            "media_name": media["name"] if media else "(deleted)",
            "scheduled_start_utc": s["scheduled_start_utc"],
            "broadcast_id": bid, "watch_url": watch_url(bid) if bid else None,
            "studio_url": studio_url(bid) if bid else None,
            "live_confirmed_at": s["live_confirmed_at"], "live_since": live_since,
            "time_live_seconds": (end - live_since) if live_since else 0,
            "media_duration": dur, "played_total": played,
            "loop_position": (played % dur) if dur else 0,
            "loops_completed": math.floor(played / dur) if dur else 0,
            "encoder": s.get("encoder"), "ingest": s.get("ingest"), "metrics": s.get("metrics"),
            "overlay": s.get("overlay"),
            "error": s.get("error"), "error_kind": s.get("error_kind"), "youtube_reason": s.get("youtube_reason"),
            "reconnect_attempts": s.get("reconnect_attempts"),
            "created_at": s["created_at"], "ended_at": s.get("ended_at"),
        }

    def worker_status() -> dict:
        hb = db.get_setting("worker_heartbeat") or {}
        age = time.time() - hb.get("ts", 0)
        return {"online": age < 10, "last_seen_seconds": round(age, 1) if hb else None}

    @app.get("/api/status")
    def status():
        channel = db.get_setting("channel")
        return {
            "connected": yt.connected(), "channel": channel,
            "oauth_configured": bool(cfg.google.client_id and cfg.google.client_secret),
            "oauth_redirect_uri": cfg.oauth_redirect_uri,
            "session": view(db.active_session()),
            "recent": [view(s) for s in db.recent_sessions(10)],
            "worker": worker_status(), "timezone": cfg.ui.timezone, "server_time": time.time(),
            "encoder_mode": cfg.encoder.mode,
        }

    @app.get("/api/defaults")
    def defaults():
        return {"description": DEFAULT_DESCRIPTION, "privacy": "unlisted", "timezone": cfg.ui.timezone,
                "overlay": db.get_setting("overlay", OverlayBody().model_dump()),
                "chat": db.get_setting("chat", {"messages": [
                    "Welcome! This is a prerecorded video playing on repeat. What brought you here today?",
                    "Question for chat: which part of the video should I make a follow-up about?"]}),
                "upload_chunk_bytes": cfg.limits.upload_chunk_mb * 1024 * 1024}

    # ------------------------------------------------------------ YouTube account
    @app.get("/api/youtube/connect")
    def yt_connect():
        if not (cfg.google.client_id and cfg.google.client_secret):
            raise HTTPException(400, "Google OAuth is not configured. Enter the client ID and secret in the dashboard "
                                     "or config.toml (see README: Google Cloud OAuth).")
        return {"url": yt.auth_url()}

    @app.put("/api/settings/google")
    def google_save(body: GoogleBody):
        if db.active_session():
            raise HTTPException(409, "Stop the active stream before changing the Google OAuth client.")
        if not body.client_id.strip().endswith(".apps.googleusercontent.com"):
            raise HTTPException(400, "The client ID should end with .apps.googleusercontent.com")
        db.set_setting("google_client", {"client_id": body.client_id.strip()})
        db.put_secret("google_client_secret", box.encrypt(body.client_secret.strip()))
        apply_google_settings()
        return {"ok": True, "redirect_uri": cfg.oauth_redirect_uri}

    def callback_page(ok: bool, message: str, request: Request):
        """Plain page for the OAuth return. In the app's own browser it bounces back to the dashboard."""
        import html
        same_browser = box.check_session(request.cookies.get(COOKIE), pw_version())
        if same_browser:
            return RedirectResponse("/?connected=1" if ok else "/?error=" + re.sub(r"[^A-Za-z_ ]", "", message)[:60])
        title = "YouTube connected" if ok else "YouTube connection failed"
        body = (f"<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><title>{title}</title>"
                f"<body style='font:18px system-ui;padding:24px;max-width:520px;margin:auto'>"
                f"<h2>{'✅' if ok else '⚠️'} {title}</h2><p>{html.escape(message)}</p>"
                f"<p>Switch back to <b>Replay Studio</b>. This tab can be closed.</p></body>")
        return HTMLResponse(body, status_code=200 if ok else 400)

    @app.get("/api/youtube/callback")
    def yt_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if error:
            return callback_page(False, f"Google returned: {error[:60]}", request)
        try:
            yt.exchange_code(code, state)       # the one-time state proves this flow was started from the dashboard
            ch = yt.my_channel()
        except YouTubeError as e:
            log.warning("OAuth callback failed: %s", e.friendly)
            return callback_page(False, e.friendly, request)
        return callback_page(True, f"Channel: {ch.get('title', '')}", request)

    @app.post("/api/youtube/disconnect")
    def yt_disconnect():
        if db.active_session():
            raise HTTPException(409, "Stop the active stream before disconnecting YouTube.")
        yt.disconnect()
        return {"ok": True}

    @app.post("/api/youtube/refresh")
    def yt_refresh():
        return {"channel": yt.my_channel()}

    @app.post("/api/youtube/verify-channel")
    def yt_verify(body: ChannelBody):
        try:
            r = yt.channel_matches(body.url)
        except ValueError as e:
            raise HTTPException(400, str(e))
        db.set_setting("channel_url", {"url": body.url.strip(), "matches": r["matches"]})
        return r

    # ------------------------------------------------------------ media library
    def media_view(m: dict) -> dict:
        return {k: m[k] for k in ("id", "name", "source", "size", "status", "error", "created_at")} | {
            "probe": m.get("probe"), "loop_ready": bool(m.get("play_path")),
            "in_use": any(s["media_id"] == m["id"] for s in db.active_sessions())}

    def process_media(mid: str) -> None:
        m = db.get_media(mid)
        try:
            info = M.probe(cfg, Path(m["path"]))
            db.update_media(mid, probe=info, status="preparing")
            dest = cfg.library_dir / f"{mid}.loop.mov"
            how = M.prepare_loop_file(cfg, Path(m["path"]), info, dest)
            ninfo = M.probe(cfg, dest)
            if ninfo["audio_duration"] is None or abs(ninfo["audio_duration"] - ninfo["video_duration"]) > 0.01:
                raise M.MediaError("Could not align audio and video lengths for seamless looping.")
            info = {**info, "loop_ready": how, "duration": ninfo["video_duration"]}
            db.update_media(mid, play_path=str(dest), probe=info)
            M.thumbnail(cfg, Path(m["path"]), cfg.library_dir / f"{mid}.jpg", min(2.0, info["duration"] / 2))
            db.update_media(mid, status="ok", error=None)
        except M.MediaError as e:
            db.update_media(mid, status="invalid", error=str(e))
        except Exception as e:  # pragma: no cover
            log.exception("Processing media failed")
            db.update_media(mid, status="invalid", error=f"Processing failed: {redact(str(e))}")

    def spawn_process(mid: str) -> None:
        threading.Thread(target=process_media, args=(mid,), daemon=True).start()

    app.state.process_media = process_media

    @app.get("/api/media")
    def list_media():
        used = M.library_usage(cfg)
        return {"items": [media_view(m) for m in db.list_media()],
                "usage_bytes": used, "quota_bytes": int(cfg.limits.library_quota_gb * 1024 ** 3),
                "free_bytes": M.disk_free(cfg.data_dir), "max_upload_bytes": int(cfg.limits.max_upload_gb * 1024 ** 3),
                "pending_uploads": [{"id": u["id"], "filename": u["filename"], "size": u["size"],
                                     "received": u["received"]} for u in db.list_uploads()]}

    @app.get("/api/media/folder")
    def media_folder():
        return {"root": str(cfg.media_dir), "exists": cfg.media_dir.is_dir(), "files": M.list_media_folder(cfg)}

    @app.post("/api/media/import")
    def media_import(body: ImportBody):
        try:
            p = M.safe_media_path(cfg, body.path)
        except M.MediaError as e:
            raise HTTPException(400, str(e))
        existing = db.find_media_by_path(str(p))
        if existing:
            return media_view(existing)
        m = db.add_media(p.name, str(p), "folder", p.stat().st_size)
        spawn_process(m["id"])
        return media_view(m)

    def get_media_or_404(mid: str) -> dict:
        m = db.get_media(mid)
        if not m:
            raise HTTPException(404, "Video not found in library.")
        return m

    @app.get("/api/media/{mid}")
    def media_get(mid: str):
        return media_view(get_media_or_404(mid))

    @app.post("/api/media/{mid}/reprobe")
    def media_reprobe(mid: str):
        get_media_or_404(mid)
        db.update_media(mid, status="probing", error=None)
        spawn_process(mid)
        return {"ok": True}

    @app.delete("/api/media/{mid}")
    def media_delete(mid: str):
        m = get_media_or_404(mid)
        if any(s["media_id"] == mid for s in db.active_sessions()):
            raise HTTPException(409, "This video is used by the active stream.")
        if m["source"] == "upload":
            Path(m["path"]).unlink(missing_ok=True)
        for extra in (m.get("play_path"), str(cfg.library_dir / f"{mid}.jpg")):
            if extra:
                Path(extra).unlink(missing_ok=True)
        db.delete_media(mid)
        return {"ok": True}

    @app.get("/api/media/{mid}/file")
    def media_file(mid: str):
        m = get_media_or_404(mid)
        return FileResponse(m["path"], media_type="video/mp4")  # Starlette serves HTTP Range requests

    @app.get("/api/media/{mid}/thumb")
    def media_thumb(mid: str):
        get_media_or_404(mid)
        p = cfg.library_dir / f"{mid}.jpg"
        if not p.exists():
            raise HTTPException(404, "No thumbnail yet.")
        return FileResponse(p, media_type="image/jpeg")

    # ------------------------------------------------------------ resumable uploads
    def check_space(extra: int) -> None:
        if extra > cfg.limits.max_upload_gb * 1024 ** 3:
            raise HTTPException(413, f"File is larger than the {cfg.limits.max_upload_gb:g} GB upload limit.")
        if M.library_usage(cfg) + extra > cfg.limits.library_quota_gb * 1024 ** 3:
            raise HTTPException(507, "The media library quota would be exceeded. Delete unused videos first.")
        if M.disk_free(cfg.data_dir) - extra < cfg.limits.min_free_disk_gb * 1024 ** 3:
            raise HTTPException(507, "Not enough free disk space on the host for this upload.")

    @app.post("/api/uploads")
    def upload_create(body: UploadCreate):
        name = Path(body.filename).name
        if Path(name).suffix.lower() not in M.VIDEO_EXTS:
            raise HTTPException(400, "Only video files (MP4 recommended) can be uploaded.")
        for u in db.list_uploads():  # resume an identical unfinished upload
            if u["filename"] == name and u["size"] == body.size and Path(u["tmp_path"]).exists():
                return {"id": u["id"], "received": u["received"], "size": u["size"],
                        "chunk_bytes": cfg.limits.upload_chunk_mb * 1024 * 1024}
        check_space(body.size)
        tmp = cfg.uploads_dir / f"{uuid.uuid4().hex}.part"
        tmp.touch(mode=0o600)
        u = db.create_upload(name, body.size, str(tmp))
        return {"id": u["id"], "received": 0, "size": body.size,
                "chunk_bytes": cfg.limits.upload_chunk_mb * 1024 * 1024}

    @app.get("/api/uploads/{uid}")
    def upload_status(uid: str):
        u = db.get_upload(uid)
        if not u:
            raise HTTPException(404, "Upload not found (it may have finished or been cancelled).")
        return {"id": uid, "received": u["received"], "size": u["size"], "media_id": u["media_id"]}

    @app.put("/api/uploads/{uid}")
    async def upload_chunk(uid: str, request: Request, offset: int):
        lock = upload_locks.setdefault(uid, threading.Lock())
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "Another chunk for this upload is in progress.")
        try:
            u = db.get_upload(uid)
            if not u:
                raise HTTPException(404, "Upload not found.")
            if u["media_id"]:
                return {"received": u["size"], "complete": True, "media": media_view(db.get_media(u["media_id"]))}
            if offset != u["received"]:
                return JSONResponse({"detail": "offset mismatch", "received": u["received"]}, status_code=409)
            max_chunk = cfg.limits.upload_chunk_mb * 1024 * 1024 * 2
            if M.disk_free(cfg.data_dir) < cfg.limits.min_free_disk_gb * 1024 ** 3:
                raise HTTPException(507, "The host is running out of disk space.")
            written = 0
            with open(u["tmp_path"], "r+b") as fh:
                fh.seek(offset)
                async for part in request.stream():
                    written += len(part)
                    if written > max_chunk or offset + written > u["size"]:
                        raise HTTPException(413, "Chunk too large.")
                    fh.write(part)
                fh.flush()
                os.fsync(fh.fileno())
            received = offset + written
            db.update_upload(uid, received=received)
            if received < u["size"]:
                return {"received": received, "complete": False}
            ext = Path(u["filename"]).suffix.lower()
            mid_path = cfg.library_dir / f"{uuid.uuid4().hex[:12]}{ext}"
            os.replace(u["tmp_path"], mid_path)
            m = db.add_media(u["filename"], str(mid_path), "upload", received)
            db.update_upload(uid, media_id=m["id"])
            spawn_process(m["id"])
            return {"received": received, "complete": True, "media": media_view(m)}
        finally:
            lock.release()

    @app.delete("/api/uploads/{uid}")
    def upload_cancel(uid: str):
        u = db.get_upload(uid)
        if u:
            Path(u["tmp_path"]).unlink(missing_ok=True)
            db.delete_upload(uid)
        return {"ok": True}

    # ------------------------------------------------------------ sessions
    def parse_schedule(value: str) -> float:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Invalid schedule time.")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(cfg.ui.timezone))
        ts = dt.astimezone(timezone.utc).timestamp()
        if ts < time.time() + 60:
            raise HTTPException(400, "Schedule a time at least one minute in the future.")
        if ts > time.time() + 365 * 86400:
            raise HTTPException(400, "Schedule a time within the next year.")
        return ts

    @app.post("/api/sessions")
    def session_create(body: SessionCreate):
        if not yt.connected():
            raise HTTPException(400, "Connect your YouTube account first.")
        channel = db.get_setting("channel") or yt.my_channel()
        if not body.confirm_rights:
            raise HTTPException(400, "Confirm that you have the rights to rebroadcast this video and its audio.")
        if body.privacy == "public" and not body.confirm_public:
            raise HTTPException(400, "Public streams need explicit confirmation.")
        m = db.get_media(body.media_id)
        if not m:
            raise HTTPException(404, "Video not found.")
        if m["status"] != "ok":
            raise HTTPException(400, m["error"] or "The video is still being checked. Wait until it shows Ready.")
        if not Path(m.get("play_path") or m["path"]).exists():
            raise HTTPException(400, "The video file is missing on the host.")
        lr = (m.get("probe") or {}).get("loop_ready") or {}
        e = cfg.encoder
        if e.mode == "copy" and lr.get("spec") != f"{e.width}x{e.height}@{e.fps}/{e.video_bitrate_k}k":
            raise HTTPException(400, "This video was prepared for different encoder settings. Tap “Prepare again” "
                                     "in the library, wait until it shows Ready, then start.")
        sched = parse_schedule(body.scheduled_start) if body.scheduled_start else None
        key = body.idempotency_key or None
        overlay = Overlay.from_dict((body.overlay or OverlayBody(**db.get_setting("overlay", {}))).model_dump()).__dict__
        now = time.time()
        sid = uuid.uuid4().hex
        dup_key_id = conflict_id = None
        try:
            with db.tx() as c:
                r = c.execute("SELECT id FROM sessions WHERE idempotency_key=?", (key,)).fetchone() if key else None
                if r:
                    dup_key_id = r["id"]
                else:
                    r = c.execute("SELECT id FROM sessions WHERE active=1 AND channel_id=?",
                                  (channel["id"],)).fetchone()
                    if r:
                        conflict_id = r["id"]
                    else:
                        c.execute(
                            "INSERT INTO sessions(id,channel_id,media_id,title,description,privacy,made_for_kids,"
                            "scheduled_start_utc,state,active,idempotency_key,overlay,media_duration,created_at,"
                            "updated_at) VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?,?)",
                            (sid, channel["id"], m["id"], body.title.strip(), body.description, body.privacy,
                             int(body.made_for_kids), sched, S.SCHEDULED if sched else S.PENDING, key,
                             json.dumps(overlay), (m.get("probe") or {}).get("duration"), now, now))
        except sqlite3.IntegrityError:
            existing = db.active_session(channel["id"])
            conflict_id = existing["id"] if existing else None
        if dup_key_id:  # same click delivered twice: return the session it already created
            return {"session": view(db.get_session(dup_key_id)), "duplicate": True}
        if conflict_id:
            return JSONResponse({"detail": "A stream is already active on this channel. Stop it before starting "
                                           "another.", "existing_id": conflict_id, "duplicate": True},
                                status_code=409)
        db.log_event(sid, f"Session created ({body.privacy}{', scheduled' if sched else ''}).")
        return {"session": view(db.get_session(sid)), "duplicate": False}

    def get_session_or_404(sid: str) -> dict:
        s = db.get_session(sid)
        if not s:
            raise HTTPException(404, "Session not found.")
        return s

    @app.get("/api/sessions/{sid}")
    def session_get(sid: str):
        return {"session": view(get_session_or_404(sid)), "events": db.events(sid, 40)}

    @app.post("/api/sessions/{sid}/stop")
    def session_stop(sid: str):
        s = get_session_or_404(sid)
        s = db.request_stop(sid)  # persisted before we return; the worker kills media within ~0.5 s
        if s["active"]:
            db.log_event(sid, "Stop stream pressed.")
        return {"session": view(s)}

    @app.post("/api/sessions/{sid}/retry")
    def session_retry(sid: str):
        s = get_session_or_404(sid)
        if s["state"] != S.FAILED or s["stop_requested_at"]:
            raise HTTPException(409, "Retry is only possible after recovery failed.")
        db.update_session(sid, state=S.RECONNECTING, error="Retry requested", reconnect_attempts=0)
        db.log_event(sid, "Retry pressed.")
        return {"session": view(db.get_session(sid))}

    # ------------------------------------------------------------ audience tools
    @app.put("/api/settings/overlay")
    def overlay_save(body: OverlayBody):
        db.set_setting("overlay", body.model_dump())
        return body.model_dump()

    @app.post("/api/overlay/preview")
    def overlay_preview(body: OverlayBody, media_id: str | None = None):
        ov = Overlay.from_dict(body.model_dump())
        ov.enabled, ov.every_minutes, ov.show_seconds = True, 1, 60
        e = cfg.encoder
        with tempfile.TemporaryDirectory(dir=cfg.data_dir / "run") as td:
            tf = Path(td) / "text.txt"
            tf.write_text(ov.text, encoding="utf-8")
            out = Path(td) / "preview.png"
            m = db.get_media(media_id) if media_id else None
            if m and m["status"] == "ok":
                src = ["-ss", f"{min(2.0, (m['probe'] or {}).get('duration', 4) / 2):.2f}", "-i", str(Path(m["path"]).resolve())]
            else:
                src = ["-f", "lavfi", "-i", f"testsrc2=size={e.width}x{e.height}:rate=1"]
            vf = (f"scale={e.width}:{e.height}:force_original_aspect_ratio=decrease,"
                  f"pad={e.width}:{e.height}:(ow-iw)/2:(oh-ih)/2,setsar=1," + overlay_filter(cfg, ov, tf))
            argv = [e.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *src,
                    "-frames:v", "1", "-vf", vf, str(out)]
            cp = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            if cp.returncode != 0 or not out.exists():
                raise HTTPException(500, "Preview failed: " + redact(cp.stderr[-300:]))
            return Response(out.read_bytes(), media_type="image/png")

    @app.put("/api/settings/chat")
    def chat_save(body: ChatBody):
        msgs = [m.strip()[:200] for m in body.messages if m.strip()]
        db.set_setting("chat", {"messages": msgs})
        return {"messages": msgs}

    @app.get("/api/diagnostics")
    def diagnostics():
        try:
            ver = subprocess.run([cfg.encoder.ffmpeg, "-version"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
        except Exception as e:  # pragma: no cover
            ver = f"ffmpeg not available: {e}"
        s = db.active_session() or (db.recent_sessions(1) or [None])[0]
        return {"config": cfg.redacted(), "ffmpeg": ver, "worker": worker_status(),
                "disk_free_bytes": M.disk_free(cfg.data_dir),
                "youtube_connected": yt.connected(),
                "events": [dict(e, message=redact(e["message"])) for e in (db.events(s["id"], 100) if s else [])]}

    # ------------------------------------------------------------ static dashboard
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str = ""):
            if full_path.startswith("api/"):
                raise HTTPException(404)
            f = (static_dir / full_path).resolve()
            if full_path and f.is_file() and static_dir in f.parents:
                return FileResponse(f)
            return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-cache"})
    return app


def main() -> None:
    import uvicorn
    setup_logging()
    cfg = load_config()
    uvicorn.run(create_app(cfg), host=cfg.server.host, port=cfg.server.port, log_config=None,
                proxy_headers=True, forwarded_allow_ips="127.0.0.1")


if __name__ == "__main__":
    main()
