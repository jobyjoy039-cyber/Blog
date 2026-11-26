"""YouTube Data API / Live Streaming API client (official REST endpoints, OAuth 2.0).

Only the documented endpoints are used:
  channels.list, liveBroadcasts.insert/list/bind/transition/delete,
  liveStreams.insert/list, videos.list.
"""
from __future__ import annotations

import json
import logging
import re
import secrets as pysecrets
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Config
from .db import DB
from .security import SecretBox, redact, register_secret

log = logging.getLogger("replay_studio.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_SECRET = "oauth_tokens"


# ------------------------------------------------------------------ errors

FRIENDLY = {
    "liveStreamingNotEnabled": "Live streaming is not enabled for this channel. Verify the channel at "
                               "youtube.com/verify and enable live streaming in YouTube Studio (first-time "
                               "activation can take up to 24 hours).",
    "insufficientLivePermissions": "This account is not allowed to live stream on this channel.",
    "livePermissionBlocked": "YouTube has blocked live streaming for this channel (for example a "
                             "Community Guidelines strike or live restriction). Check YouTube Studio.",
    "quotaExceeded": "The Google Cloud project has used its daily YouTube API quota. Quota resets at "
                     "midnight Pacific time; you can request more quota in Google Cloud Console.",
    "dailyLimitExceeded": "The daily YouTube API limit was reached. Try again after midnight Pacific time.",
    "rateLimitExceeded": "YouTube is rate-limiting requests. Retrying shortly.",
    "userRequestsExceedRateLimit": "YouTube is rate-limiting requests. Retrying shortly.",
    "userBroadcastsExceedLimit": "This channel has too many scheduled/active broadcasts. Delete unused "
                                 "upcoming broadcasts in YouTube Studio.",
    "concurrentBroadcastsExceedLimit": "This channel already has the maximum number of concurrent live broadcasts.",
    "errorStreamInactive": "YouTube is not receiving video on the ingest stream yet.",
    "invalidTransition": "YouTube refused that state change for the broadcast in its current state.",
    "redundantTransition": "The broadcast is already in that state.",
    "liveBroadcastNotFound": "The broadcast no longer exists on YouTube (deleted in Studio?).",
    "invalid_grant": "YouTube access was revoked or the authorization expired. Reconnect your YouTube account.",
    "unauthorized": "YouTube rejected the stored credentials. Reconnect your YouTube account.",
    "not_connected": "No YouTube account is connected yet.",
    "network": "YouTube could not be reached (network problem).",
}

TRANSIENT_REASONS = {"rateLimitExceeded", "userRequestsExceedRateLimit", "backendError", "errorExecutingTransition",
                     "internalError", "network", "serverError"}


class YouTubeError(Exception):
    def __init__(self, reason: str, message: str = "", status: int = 0, transient: bool | None = None):
        self.reason = reason or "unknown"
        self.status = status
        self.raw_message = redact(message or "")
        self.transient = (reason in TRANSIENT_REASONS or status >= 500) if transient is None else transient
        super().__init__(self.friendly)

    @property
    def friendly(self) -> str:
        base = FRIENDLY.get(self.reason)
        if base and self.raw_message and self.raw_message not in base:
            return f"{base} (YouTube: {self.raw_message})"
        return base or f"YouTube API error {self.status} {self.reason}: {self.raw_message}"

    @property
    def kind(self) -> str:
        if self.reason in ("invalid_grant", "unauthorized", "not_connected"):
            return "auth"
        if self.reason in ("quotaExceeded", "dailyLimitExceeded"):
            return "quota"
        if self.reason in ("liveStreamingNotEnabled", "insufficientLivePermissions", "livePermissionBlocked"):
            return "eligibility"
        return "transient" if self.transient else "youtube"


def _parse_error(resp: httpx.Response) -> YouTubeError:
    reason, message = "", ""
    try:
        body = resp.json()
        err = body.get("error")
        if isinstance(err, dict):
            message = err.get("message", "")
            errs = err.get("errors") or []
            if errs:
                reason = errs[0].get("reason", "")
            if not reason:
                for d in err.get("details", []) or []:
                    reason = d.get("reason", "") or reason
            if not reason and resp.status_code == 401:
                reason = "unauthorized"
        elif isinstance(err, str):  # OAuth token endpoint
            reason = err
            message = body.get("error_description", "")
    except (ValueError, json.JSONDecodeError):
        message = resp.text[:300]
    return YouTubeError(reason or f"http{resp.status_code}", message, resp.status_code)


# ------------------------------------------------------------------ helpers

def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def studio_url(video_id: str) -> str:
    return f"https://studio.youtube.com/video/{video_id}/livestreaming"


def parse_rfc3339(s: str | None) -> float | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def to_rfc3339(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


CHANNEL_URL_RE = [
    (re.compile(r"^(?:https?://)?(?:www\.|m\.)?youtube\.com/(@[A-Za-z0-9._\-]{3,30})/?(?:[/?#].*)?$"), "handle"),
    (re.compile(r"^(@[A-Za-z0-9._\-]{3,30})$"), "handle"),
    (re.compile(r"^(?:https?://)?(?:www\.|m\.)?youtube\.com/channel/(UC[A-Za-z0-9_\-]{22})/?(?:[/?#].*)?$"), "id"),
    (re.compile(r"^(UC[A-Za-z0-9_\-]{22})$"), "id"),
]


def parse_channel_url(url: str) -> tuple[str, str]:
    """Return ("handle", "@name") or ("id", "UC...") or raise ValueError."""
    url = url.strip()
    for rx, kind in CHANNEL_URL_RE:
        m = rx.match(url)
        if m:
            return kind, m.group(1)
    raise ValueError("Paste a channel link like https://www.youtube.com/@yourhandle or "
                     "https://www.youtube.com/channel/UC...")


# ------------------------------------------------------------------ client

@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: float


class YouTubeClient:
    def __init__(self, cfg: Config, db: DB, box: SecretBox, timeout: float = 20.0):
        self.cfg = cfg
        self.db = db
        self.box = box
        self.http = httpx.Client(timeout=timeout)
        self._lock = threading.Lock()

    # ----- OAuth
    def auth_url(self) -> str:
        state = pysecrets.token_urlsafe(24)
        self.db.set_setting("oauth_state", {"state": state, "ts": time.time()})
        q = {
            "client_id": self.cfg.google.client_id,
            "redirect_uri": self.cfg.oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return self.cfg.google.auth_uri + "?" + urllib.parse.urlencode(q)

    def exchange_code(self, code: str, state: str) -> None:
        saved = self.db.get_setting("oauth_state") or {}
        self.db.delete_setting("oauth_state")
        if not saved or not pysecrets.compare_digest(saved.get("state", ""), state or "") \
                or time.time() - saved.get("ts", 0) > 900:
            raise YouTubeError("invalid_state", "OAuth state mismatch or expired. Start the connection again.",
                               400, transient=False)
        resp = self._post_token({
            "code": code,
            "client_id": self.cfg.google.client_id,
            "client_secret": self.cfg.google.client_secret,
            "redirect_uri": self.cfg.oauth_redirect_uri,
            "grant_type": "authorization_code",
        })
        if not resp.get("refresh_token"):
            raise YouTubeError("no_refresh_token", "Google did not return a refresh token. Remove the app at "
                               "myaccount.google.com/permissions and connect again.", 400, transient=False)
        self._save_tokens(Tokens(resp["access_token"], resp["refresh_token"],
                                 time.time() + int(resp.get("expires_in", 3600))))

    def _post_token(self, data: dict) -> dict:
        try:
            r = self.http.post(self.cfg.google.token_uri, data=data)
        except httpx.HTTPError as e:
            raise YouTubeError("network", str(e), 0, transient=True) from None
        if r.status_code != 200:
            raise _parse_error(r)
        return r.json()

    def _save_tokens(self, t: Tokens) -> None:
        register_secret(t.access_token)
        register_secret(t.refresh_token)
        self.db.put_secret(TOKEN_SECRET, self.box.encrypt(json.dumps(t.__dict__)))

    def _load_tokens(self) -> Tokens | None:
        ct = self.db.get_secret(TOKEN_SECRET)
        if not ct:
            return None
        t = Tokens(**json.loads(self.box.decrypt(ct)))
        register_secret(t.access_token)
        register_secret(t.refresh_token)
        return t

    def connected(self) -> bool:
        return self.db.get_secret(TOKEN_SECRET) is not None

    def disconnect(self, revoke: bool = True) -> None:
        t = self._load_tokens()
        if t and revoke:
            try:
                self.http.post(self.cfg.google.revoke_uri, data={"token": t.refresh_token})
            except httpx.HTTPError:
                pass
        self.db.delete_secret(TOKEN_SECRET)
        self.db.delete_setting("channel")

    def _access_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            t = self._load_tokens()
            if t is None:
                raise YouTubeError("not_connected", "", 401, transient=False)
            if force_refresh or t.expires_at - time.time() < 120:
                resp = self._post_token({
                    "client_id": self.cfg.google.client_id,
                    "client_secret": self.cfg.google.client_secret,
                    "refresh_token": t.refresh_token,
                    "grant_type": "refresh_token",
                })
                t = Tokens(resp["access_token"], resp.get("refresh_token", t.refresh_token),
                           time.time() + int(resp.get("expires_in", 3600)))
                self._save_tokens(t)
            return t.access_token

    # ----- generic request
    def request(self, method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
        url = self.cfg.google.api_base.rstrip("/") + path
        for attempt in (1, 2):
            token = self._access_token(force_refresh=attempt == 2)
            try:
                r = self.http.request(method, url, params=params, json=body,
                                      headers={"Authorization": f"Bearer {token}"})
            except httpx.HTTPError as e:
                raise YouTubeError("network", f"{type(e).__name__}: {e}", 0, transient=True) from None
            if r.status_code == 401 and attempt == 1:
                continue
            if r.status_code >= 400:
                err = _parse_error(r)
                log.warning("YouTube %s %s -> %s %s", method, path, r.status_code, err.reason)
                raise err
            return r.json() if r.content else {}
        raise YouTubeError("unauthorized", "", 401, transient=False)  # pragma: no cover

    # ----- channel
    def my_channel(self) -> dict:
        data = self.request("GET", "/channels", {"part": "snippet,status", "mine": "true"})
        items = data.get("items") or []
        if not items:
            raise YouTubeError("noChannel", "This Google account has no YouTube channel. Create one at "
                               "youtube.com first.", 404, transient=False)
        ch = items[0]
        sn = ch.get("snippet", {})
        thumbs = sn.get("thumbnails", {})
        avatar = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        info = {"id": ch["id"], "title": sn.get("title", ""), "handle": sn.get("customUrl", ""),
                "avatar": avatar, "checked_at": time.time()}
        self.db.set_setting("channel", info)
        return info

    def channel_matches(self, url: str) -> dict:
        kind, value = parse_channel_url(url)
        mine = self.db.get_setting("channel") or self.my_channel()
        if kind == "id":
            ok = value == mine["id"]
        else:
            ok = value.lower() == (mine.get("handle") or "").lower()
            if not ok:  # customUrl can lag behind a handle change; ask YouTube directly.
                try:
                    data = self.request("GET", "/channels", {"part": "id", "forHandle": value})
                    ok = any(i.get("id") == mine["id"] for i in data.get("items", []))
                except YouTubeError:
                    pass
        return {"matches": ok, "kind": kind, "value": value, "channel": mine}

    # ----- live
    def insert_broadcast(self, title: str, description: str, privacy: str, made_for_kids: bool,
                         scheduled_start: float) -> dict:
        body = {
            "snippet": {"title": title[:100], "description": description[:5000],
                        "scheduledStartTime": to_rfc3339(scheduled_start)},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(made_for_kids)},
            "contentDetails": {
                "enableAutoStart": False,
                "enableAutoStop": False,           # we keep looping until the user presses Stop
                "enableDvr": True,
                "recordFromStart": True,
                "enableEmbed": True,
                "latencyPreference": "normal",
                "monitorStream": {"enableMonitorStream": False},  # lets us go ready -> live directly
            },
        }
        return self.request("POST", "/liveBroadcasts", {"part": "snippet,status,contentDetails"}, body)

    def get_broadcast(self, broadcast_id: str) -> dict | None:
        data = self.request("GET", "/liveBroadcasts", {"part": "snippet,status,contentDetails", "id": broadcast_id})
        items = data.get("items") or []
        return items[0] if items else None

    def list_upcoming_broadcasts(self) -> list[dict]:
        data = self.request("GET", "/liveBroadcasts", {"part": "snippet,status", "broadcastStatus": "upcoming",
                                                       "broadcastType": "all", "maxResults": 50})
        return data.get("items") or []

    def delete_broadcast(self, broadcast_id: str) -> None:
        self.request("DELETE", "/liveBroadcasts", {"id": broadcast_id})

    def insert_stream(self, title: str) -> dict:
        body = {
            "snippet": {"title": title[:128], "description": "Replay Studio ingest"},
            "cdn": {"ingestionType": "rtmp", "resolution": "variable", "frameRate": "variable"},
            "contentDetails": {"isReusable": False},
        }
        return self.request("POST", "/liveStreams", {"part": "snippet,cdn,contentDetails,status"}, body)

    def get_stream(self, stream_id: str) -> dict | None:
        data = self.request("GET", "/liveStreams", {"part": "snippet,cdn,status", "id": stream_id})
        items = data.get("items") or []
        return items[0] if items else None

    def list_my_streams(self) -> list[dict]:
        data = self.request("GET", "/liveStreams", {"part": "snippet,cdn,status", "mine": "true", "maxResults": 50})
        return data.get("items") or []

    def bind(self, broadcast_id: str, stream_id: str) -> dict:
        return self.request("POST", "/liveBroadcasts/bind",
                            {"id": broadcast_id, "streamId": stream_id, "part": "id,contentDetails,status"})

    def transition(self, broadcast_id: str, status: str) -> dict:
        return self.request("POST", "/liveBroadcasts/transition",
                            {"id": broadcast_id, "broadcastStatus": status, "part": "id,status,snippet"})

    def video_metrics(self, video_id: str) -> dict:
        data = self.request("GET", "/videos", {"part": "liveStreamingDetails,statistics", "id": video_id})
        items = data.get("items") or []
        if not items:
            return {}
        it = items[0]
        lsd = it.get("liveStreamingDetails", {})
        st = it.get("statistics", {})
        return {
            "concurrent_viewers": lsd.get("concurrentViewers"),
            "view_count": st.get("viewCount"),
            "like_count": st.get("likeCount"),
            "comment_count": st.get("commentCount"),
            "has_live_chat": bool(lsd.get("activeLiveChatId")),
            "actual_start": lsd.get("actualStartTime"),
            "fetched_at": time.time(),
        }


def ingest_url(stream: dict, protocol: str) -> str:
    info = stream["cdn"]["ingestionInfo"]
    key = info["streamName"]
    register_secret(key)
    if protocol == "rtmps" and info.get("rtmpsIngestionAddress"):
        base = info["rtmpsIngestionAddress"]
    else:
        base = info["ingestionAddress"]
    return base.rstrip("/") + "/" + key
