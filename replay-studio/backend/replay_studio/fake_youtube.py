"""Local stand-in for the YouTube Live Streaming API, for tests and offline demos.

It mimics the documented resource shapes, lifecycle rules and error format, and it runs a real
RTMP receiver (FFmpeg in listen mode) per ingest stream that records what it receives to FLV files,
so the actual encoder output can be analysed. Control endpoints under /_control simulate outages.

    python -m replay_studio.fake_youtube --port 9100 --rtmp-port 19350 --record-dir ./data/fake-ingest
"""
from __future__ import annotations

import argparse
import secrets
import subprocess
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

CHANNEL = {"id": "UCreplaystudiotest0000a1", "title": "Replay Studio Test Channel", "customUrl": "@replaystudiotest"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def err(code: int, reason: str, message: str = "") -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message or reason,
                                   "errors": [{"reason": reason, "message": message or reason, "domain": "youtube.liveBroadcast"}]}},
                        status_code=code)


class Ingest:
    """One FFmpeg RTMP listener per stream; restarts after each publisher disconnect unless 'down'."""

    def __init__(self, stream_id: str, key: str, port: int, record_dir: Path, ffmpeg: str):
        self.stream_id, self.key, self.port = stream_id, key, port
        self.record_dir, self.ffmpeg = record_dir, ffmpeg
        self.up = True
        self.proc: subprocess.Popen | None = None
        self.segments: list[Path] = []
        self.connections = 0
        self.stopped = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        n = 0
        while not self.stopped:
            if not self.up:
                time.sleep(0.2)
                continue
            n += 1
            out = self.record_dir / f"{self.stream_id}_{n:03d}.flv"
            argv = [self.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-listen", "1",
                    "-i", f"rtmp://127.0.0.1:{self.port}/live2/{self.key}", "-c", "copy", "-f", "flv", str(out)]
            self.proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.segments.append(out)
            self.proc.wait()
            if out.exists() and out.stat().st_size > 0:
                self.connections += 1
            else:
                out.unlink(missing_ok=True)
                self.segments.remove(out)
            time.sleep(0.2)

    def set_up(self, up: bool) -> None:
        self.up = up
        if not up and self.proc and self.proc.poll() is None:
            self.proc.kill()

    def active(self) -> bool:
        if not self.up or not self.segments:
            return False
        p = self.segments[-1]
        try:
            return p.exists() and time.time() - p.stat().st_mtime < 4 and p.stat().st_size > 50_000
        except OSError:
            return False

    def close(self) -> None:
        self.stopped = True
        self.set_up(False)


def create_app(rtmp_port: int, record_dir: Path, ffmpeg: str = "ffmpeg", public_host: str = "127.0.0.1") -> FastAPI:
    app = FastAPI(title="Fake YouTube")
    record_dir.mkdir(parents=True, exist_ok=True)
    st = {"broadcasts": {}, "streams": {}, "ingests": {}, "tokens": set(), "api_down": False,
          "calls": [], "next_port": rtmp_port}
    lock = threading.Lock()
    app.state.fake = st

    def authed(req: Request) -> bool:
        h = req.headers.get("authorization", "")
        return h.startswith("Bearer ") and h[7:] in st["tokens"]

    @app.middleware("http")
    async def gate(req: Request, call_next):
        p = req.url.path
        if not p.startswith("/_control") and not p.startswith("/o/") and p != "/token":
            st["calls"].append({"method": req.method, "path": p, "query": dict(req.query_params), "ts": time.time()})
            if st["api_down"]:
                return err(503, "backendError", "Simulated outage")
            if not authed(req):
                return JSONResponse({"error": {"code": 401, "message": "Invalid Credentials",
                                               "errors": [{"reason": "authError"}]}}, status_code=401)
        return await call_next(req)

    # ---------------- OAuth
    @app.get("/o/oauth2/auth")
    def auth(redirect_uri: str, state: str):
        return RedirectResponse(redirect_uri + "?" + urllib.parse.urlencode({"code": "fake-code", "state": state}))

    @app.post("/token")
    async def token(req: Request):
        form = await req.form()
        if form.get("grant_type") == "refresh_token" and (st.get("revoked") or
                                                          not str(form.get("refresh_token", "")).startswith("1//fake")):
            return JSONResponse({"error": "invalid_grant", "error_description": "Token has been expired or revoked."}, 400)
        if form.get("grant_type") == "authorization_code":
            st["revoked"] = False
        tok = "ya29.fake-" + secrets.token_urlsafe(12)
        st["tokens"].add(tok)
        return {"access_token": tok, "expires_in": 3600, "token_type": "Bearer",
                "refresh_token": "1//fake-refresh-" + secrets.token_urlsafe(12)}

    @app.post("/revoke")
    def revoke():
        return {}

    # ---------------- channels
    @app.get("/channels")
    def channels(req: Request):
        q = req.query_params
        if q.get("forHandle") and q["forHandle"].lower() != CHANNEL["customUrl"]:
            return {"items": []}
        return {"items": [{"id": CHANNEL["id"], "snippet": {
            "title": CHANNEL["title"], "customUrl": CHANNEL["customUrl"],
            "thumbnails": {"default": {"url": "https://yt3.ggpht.com/fake-avatar=s88"}}}}]}

    # ---------------- broadcasts
    def resolve(b: dict) -> dict:
        if b["status"]["lifeCycleStatus"] == "liveStarting" and time.time() >= b["_live_at"]:
            b["status"]["lifeCycleStatus"] = "live"
            b["snippet"]["actualStartTime"] = now_iso()
        return b

    def public(b: dict) -> dict:
        return {k: v for k, v in resolve(b).items() if not k.startswith("_")}

    @app.post("/liveBroadcasts")
    async def insert_broadcast(req: Request):
        body = await req.json()
        bid = secrets.token_urlsafe(8)[:11].replace("-", "x").replace("_", "y")
        b = {"kind": "youtube#liveBroadcast", "id": bid,
             "snippet": {**body["snippet"], "publishedAt": now_iso(), "channelId": CHANNEL["id"]},
             "status": {"privacyStatus": body["status"]["privacyStatus"], "lifeCycleStatus": "created",
                        "selfDeclaredMadeForKids": body["status"].get("selfDeclaredMadeForKids", False)},
             "contentDetails": dict(body.get("contentDetails", {})), "_live_at": 0}
        if b["contentDetails"].get("enableAutoStop") is not False:
            return err(400, "invalidAutoStop", "test harness expects enableAutoStop=false")
        st["broadcasts"][bid] = b
        return public(b)

    @app.get("/liveBroadcasts")
    def list_broadcasts(req: Request):
        q = req.query_params
        items = list(st["broadcasts"].values())
        if q.get("id"):
            ids = q["id"].split(",")
            items = [b for b in items if b["id"] in ids]
        if q.get("broadcastStatus") == "upcoming":
            items = [b for b in items if resolve(b)["status"]["lifeCycleStatus"] in ("created", "ready")]
        return {"items": [public(b) for b in items]}

    @app.delete("/liveBroadcasts")
    def delete_broadcast(id: str):
        if id not in st["broadcasts"]:
            return err(404, "liveBroadcastNotFound")
        del st["broadcasts"][id]
        return JSONResponse(None, status_code=204)

    @app.post("/liveBroadcasts/bind")
    def bind(id: str, streamId: str):
        b = st["broadcasts"].get(id)
        if not b:
            return err(404, "liveBroadcastNotFound")
        if streamId not in st["streams"]:
            return err(404, "liveStreamNotFound")
        b["contentDetails"]["boundStreamId"] = streamId
        if b["status"]["lifeCycleStatus"] == "created":
            b["status"]["lifeCycleStatus"] = "ready"
        return public(b)

    @app.post("/liveBroadcasts/transition")
    def transition(id: str, broadcastStatus: str):
        with lock:
            b = st["broadcasts"].get(id)
            if not b:
                return err(404, "liveBroadcastNotFound")
            life = resolve(b)["status"]["lifeCycleStatus"]
            st.setdefault("transitions", []).append({"id": id, "to": broadcastStatus, "from": life, "ts": time.time()})
            if broadcastStatus == "live":
                if life in ("live", "liveStarting"):
                    return err(403, "redundantTransition")
                if life not in ("ready", "testing"):
                    return err(403, "invalidTransition")
                sid = b["contentDetails"].get("boundStreamId")
                ing = st["ingests"].get(sid)
                if not ing or not ing.active():
                    return err(403, "errorStreamInactive")
                b["status"]["lifeCycleStatus"] = "liveStarting"
                b["_live_at"] = time.time() + 1.5
            elif broadcastStatus == "complete":
                if life == "complete":
                    return err(403, "redundantTransition")
                if life not in ("live", "testing", "liveStarting"):
                    return err(403, "invalidTransition")
                b["status"]["lifeCycleStatus"] = "complete"
                b["snippet"]["actualEndTime"] = now_iso()
            else:
                return err(403, "invalidTransition")
            return public(b)

    # ---------------- streams
    @app.post("/liveStreams")
    async def insert_stream(req: Request):
        body = await req.json()
        sid = secrets.token_urlsafe(10).replace("-", "x").replace("_", "y")
        key = "fake-" + secrets.token_hex(8)
        with lock:
            port = st["next_port"]
            st["next_port"] += 1
        s = {"kind": "youtube#liveStream", "id": sid, "snippet": body["snippet"],
             "cdn": {**body["cdn"], "ingestionInfo": {
                 "streamName": key,
                 "ingestionAddress": f"rtmp://{public_host}:{port}/live2",
                 "rtmpsIngestionAddress": f"rtmp://{public_host}:{port}/live2"}},
             "status": {"streamStatus": "ready", "healthStatus": {"status": "noData"}}}
        st["streams"][sid] = s
        st["ingests"][sid] = Ingest(sid, key, port, record_dir, ffmpeg)
        return s

    def stream_view(s: dict) -> dict:
        ing = st["ingests"].get(s["id"])
        active = ing.active() if ing else False
        s["status"] = {"streamStatus": "active" if active else "ready",
                       "healthStatus": {"status": "good" if active else "noData", "configurationIssues": []}}
        return s

    @app.get("/liveStreams")
    def list_streams(req: Request):
        q = req.query_params
        items = list(st["streams"].values())
        if q.get("id"):
            items = [s for s in items if s["id"] in q["id"].split(",")]
        return {"items": [stream_view(s) for s in items]}

    @app.get("/videos")
    def videos(id: str):
        b = st["broadcasts"].get(id)
        if not b:
            return {"items": []}
        live = resolve(b)["status"]["lifeCycleStatus"] == "live"
        lsd = {"actualStartTime": b["snippet"].get("actualStartTime")}
        if live:
            lsd.update({"concurrentViewers": "0", "activeLiveChatId": "fake-chat-" + id})
        return {"items": [{"id": id, "liveStreamingDetails": lsd, "statistics": {"viewCount": "0", "likeCount": "0"}}]}

    # ---------------- control
    @app.post("/_control/api_down")
    def api_down(down: bool):
        st["api_down"] = down
        return {"api_down": down}

    @app.post("/_control/revoke")
    def revoke_all():
        st["tokens"].clear()
        st["revoked"] = True
        return {}

    @app.post("/_control/ingest")
    def ingest_ctl(up: bool):
        for ing in st["ingests"].values():
            ing.set_up(up)
        return {"up": up}

    @app.post("/_control/end/{bid}")
    def end(bid: str):
        st["broadcasts"][bid]["status"]["lifeCycleStatus"] = "complete"
        return {}

    @app.get("/_control/state")
    def state():
        return {"broadcasts": [public(b) for b in st["broadcasts"].values()],
                "streams": [stream_view(s) for s in st["streams"].values()],
                "segments": {k: [str(p) for p in v.segments] for k, v in st["ingests"].items()},
                "connections": {k: v.connections for k, v in st["ingests"].items()},
                "transitions": st.get("transitions", []),
                "insert_calls": sum(1 for c in st["calls"] if c["method"] == "POST" and c["path"] == "/liveBroadcasts")}

    @app.on_event("shutdown")
    def shutdown():
        for ing in st["ingests"].values():
            ing.close()

    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9100)
    ap.add_argument("--rtmp-port", type=int, default=19350)
    ap.add_argument("--record-dir", default="./data/fake-ingest")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args()
    uvicorn.run(create_app(a.rtmp_port, Path(a.record_dir).resolve(), a.ffmpeg), host="127.0.0.1", port=a.port,
                log_level="warning")


if __name__ == "__main__":
    main()
