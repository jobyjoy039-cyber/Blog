"""Background stream worker.

Runs as its own service, independent of the dashboard. All state lives in SQLite, so the
browser can close, the API can restart, and the worker itself can restart and reconcile.

Rules enforced here:
  * A stop request (stop_requested_at) always wins: the encoder is killed by the watchdog within
    one poll interval, no encoder is ever started afterwards, and only the YouTube "end" call is retried.
  * Recovery never creates a new broadcast: once broadcast_id is stored it is the only one used.
  * Before creating anything after a crash we look for resources created by the interrupted attempt.
  * "Live" is shown only after YouTube reports lifeCycleStatus == live.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time
from pathlib import Path
from typing import Callable

from . import db as S
from .config import Config, load_config
from .db import DB
from .encoder import Encoder, Overlay, build_command, kill_stale_encoder
from .security import SecretBox, redact, setup_logging
from .youtube import YouTubeClient, YouTubeError, ingest_url, parse_rfc3339

log = logging.getLogger("replay_studio.worker")

ENCODER_STATES = {S.STARTING_ENCODER, S.WAITING_INGEST, S.GOING_LIVE, S.LIVE, S.RECONNECTING}


class StopRequested(Exception):
    pass


class Runner(threading.Thread):
    """Drives one session to completion in its own thread."""

    def __init__(self, worker: "Worker", session_id: str):
        super().__init__(daemon=True, name=f"session-{session_id[:8]}")
        self.w = worker
        self.cfg = worker.cfg
        self.db = worker.db
        self.yt = worker.yt
        self.sid = session_id
        self.encoder: Encoder | None = None
        self.encoder_lock = threading.Lock()
        self.base_played = 0.0
        self.next_attempt = 0.0
        self.backoff = self.cfg.worker.reconnect_initial_seconds
        self.failing_since: float | None = None
        self.last_yt_poll = 0.0
        self.last_metrics_poll = 0.0
        self.last_persist = 0.0
        self.ingest_wait_started = 0.0
        self.encoder_healthy_since: float | None = None
        self.end_backoff = 2.0
        self.done = False

    # ------------------------------------------------------------ helpers
    def s(self) -> dict:
        sess = self.db.get_session(self.sid)
        assert sess is not None
        return sess

    def event(self, msg: str, level: str = "info") -> None:
        log.log(logging.WARNING if level != "info" else logging.INFO, "[%s] %s", self.sid[:8], redact(msg))
        self.db.log_event(self.sid, msg, level)

    def set_state(self, state: str, **kw) -> None:
        cur = self.s()
        if cur["state"] != state:
            self.event(f"State {cur['state']} -> {state}")
        self.db.update_session(self.sid, state=state, **kw)

    def check_stop(self) -> None:
        if self.s()["stop_requested_at"]:
            raise StopRequested()

    def media(self) -> dict:
        m = self.db.get_media(self.s()["media_id"])
        if not m or m["status"] != "ok":
            raise RuntimeError("The selected video is missing or not ready.")
        return m

    # ------------------------------------------------------------ main loop
    def run(self) -> None:
        try:
            self._reconcile_after_start()
            while not self.done:
                sess = self.db.get_session(self.sid)
                if sess is None or not sess["active"]:
                    break
                try:
                    if sess["stop_requested_at"]:
                        self.do_stop()
                        continue
                    self.step(sess)
                except StopRequested:
                    continue
                except YouTubeError as e:
                    self.handle_youtube_error(e)
                except Exception as e:  # keep the thread alive; surface the error
                    log.exception("Unexpected error in session %s", self.sid)
                    self.on_failure(f"Unexpected error: {e}")
                time.sleep(self.cfg.worker.poll_seconds)
        finally:
            self.kill_encoder()
            self.w.runner_finished(self.sid)

    def _reconcile_after_start(self) -> None:
        sess = self.s()
        if kill_stale_encoder(sess["encoder_pid"]):
            self.event("Killed an encoder left over from a previous worker process.", "warning")
        self.db.update_session(self.sid, encoder_pid=None)
        self.base_played = sess["played_total"] or 0.0
        if sess["state"] in ENCODER_STATES and not sess["stop_requested_at"]:
            # We do not know what happened while we were down: check YouTube before doing anything.
            self.event("Worker (re)started: reconciling with YouTube before resuming.")
            self.set_state(S.RECONNECTING, error="Reconciling after worker restart")
            self.next_attempt = 0.0

    def step(self, sess: dict) -> None:
        st = sess["state"]
        if st == S.SCHEDULED:
            self.step_scheduled(sess)
        elif st in (S.PENDING, S.CREATING):
            self.step_create(sess)
        elif st == S.STARTING_ENCODER:
            self.start_encoder()
            self.ingest_wait_started = time.time()
            self.set_state(S.WAITING_INGEST)
        elif st == S.WAITING_INGEST:
            self.monitor_encoder()
            self.step_wait_ingest(sess)
        elif st == S.GOING_LIVE:
            self.monitor_encoder()
            self.step_going_live(sess)
        elif st == S.LIVE:
            self.monitor_encoder()
            self.step_live(sess)
        elif st == S.RECONNECTING:
            self.step_reconnect(sess)
        elif st == S.FAILED:
            pass  # waiting for the user to press Stop (or Retry)

    # ------------------------------------------------------------ creation
    def step_scheduled(self, sess: dict) -> None:
        if not sess["broadcast_id"]:
            self.ensure_broadcast(sess)  # gives the user a watch link before the start time
        if time.time() >= (sess["scheduled_start_utc"] or 0) - self.cfg.worker.scheduled_lead_seconds:
            self.event("Scheduled start time reached.")
            self.set_state(S.CREATING)

    def ensure_broadcast(self, sess: dict) -> str:
        if sess["broadcast_id"]:
            return sess["broadcast_id"]
        if sess["broadcast_create_attempted_at"]:
            # A previous attempt may have succeeded on YouTube before we crashed. Adopt it.
            for b in self.yt.list_upcoming_broadcasts():
                pub = parse_rfc3339(b.get("snippet", {}).get("publishedAt")) or 0
                if b.get("snippet", {}).get("title") == sess["title"][:100] and \
                        pub >= sess["broadcast_create_attempted_at"] - 60:
                    self.event(f"Adopted broadcast {b['id']} created before the restart.")
                    self.db.update_session(self.sid, broadcast_id=b["id"])
                    return b["id"]
        self.check_stop()
        self.db.update_session(self.sid, broadcast_create_attempted_at=time.time())
        start = sess["scheduled_start_utc"] or time.time()
        b = self.yt.insert_broadcast(sess["title"], sess["description"], sess["privacy"],
                                     bool(sess["made_for_kids"]), max(start, time.time() + 5))
        self.db.update_session(self.sid, broadcast_id=b["id"])
        self.event(f"Created {sess['privacy']} broadcast {b['id']} (auto-stop disabled).")
        return b["id"]

    def ensure_stream(self, sess: dict) -> dict:
        title = f"replay-studio-{self.sid}"
        if sess["stream_id"]:
            st = self.yt.get_stream(sess["stream_id"])
            if st:
                return st
        if sess["stream_create_attempted_at"]:
            for st in self.yt.list_my_streams():
                if st.get("snippet", {}).get("title") == title:
                    self.db.update_session(self.sid, stream_id=st["id"])
                    self.event(f"Adopted ingest stream {st['id']} created before the restart.")
                    return st
        self.check_stop()
        self.db.update_session(self.sid, stream_create_attempted_at=time.time())
        st = self.yt.insert_stream(title)
        self.db.update_session(self.sid, stream_id=st["id"])
        self.event(f"Created ingest stream {st['id']}.")
        return st

    def step_create(self, sess: dict) -> None:
        if sess["state"] == S.PENDING:
            self.set_state(S.CREATING)
        self.media()  # fail early if the file vanished
        bid = self.ensure_broadcast(self.s())
        stream = self.ensure_stream(self.s())
        b = self.yt.get_broadcast(bid)
        if b is None:
            raise YouTubeError("liveBroadcastNotFound", "", 404, transient=False)
        life = b["status"]["lifeCycleStatus"]
        if life in ("complete", "revoked"):
            self.end_by_youtube(b)
            return
        if b.get("contentDetails", {}).get("boundStreamId") != stream["id"]:
            self.check_stop()
            self.yt.bind(bid, stream["id"])
            self.event("Bound broadcast to ingest stream.")
        self.set_state(S.STARTING_ENCODER, error=None, error_kind=None)

    # ------------------------------------------------------------ encoder
    def start_encoder(self) -> None:
        sess = self.s()
        if sess["stop_requested_at"]:
            raise StopRequested()
        m = self.media()
        stream = self.yt.get_stream(sess["stream_id"]) if sess["stream_id"] else None
        if not stream:
            raise YouTubeError("streamNotFound", "The ingest stream no longer exists.", 404, transient=False)
        url = ingest_url(stream, self.cfg.encoder.ingest_protocol)
        play = Path(m["play_path"] or m["path"])
        duration = float((m["probe"] or {}).get("duration") or 0)
        has_audio = bool(m["play_path"]) or bool((m["probe"] or {}).get("has_audio"))
        self.base_played = sess["played_total"] or 0.0
        start_at = (self.base_played % duration) if duration else 0.0
        ov = Overlay.from_dict(sess["overlay"])
        textfile = None
        if ov.enabled:
            textfile = self.cfg.data_dir / "run" / f"overlay-{self.sid}.txt"
            textfile.write_text(ov.text, encoding="utf-8")
        argv = build_command(self.cfg, play, url, has_audio, start_at, ov, textfile)
        with self.encoder_lock:
            if self.s()["stop_requested_at"]:  # final check right before spawning
                raise StopRequested()
            self.kill_encoder_locked()
            enc = Encoder(argv)
            enc.start()
            self.encoder = enc
        self.encoder_healthy_since = None
        self.db.update_session(self.sid, encoder_pid=enc.pid, media_duration=duration)
        self.event(f"Encoder started at loop position {start_at:.1f}s (pid {enc.pid}).")

    def kill_encoder(self) -> None:
        with self.encoder_lock:
            self.kill_encoder_locked()

    def kill_encoder_locked(self) -> None:
        if self.encoder:
            self.encoder.kill()
            self.persist_progress(force=True)
            self.base_played = self.s()["played_total"] or 0.0
            self.encoder = None
            self.db.update_session(self.sid, encoder_pid=None)

    def persist_progress(self, force: bool = False) -> None:
        enc = self.encoder
        if not enc:
            return
        if not force and time.time() - self.last_persist < 1.0:
            return
        self.last_persist = time.time()
        st = enc.stats
        self.db.update_session(self.sid, played_total=self.base_played + st.out_time, encoder={
            "pid": enc.pid, "fps": st.fps, "bitrate_kbps": st.bitrate_kbps, "speed": st.speed,
            "frames": st.frames, "dropped": st.dropped, "duplicated": st.duplicated,
            "run_seconds": round(time.time() - enc.started_at, 1), "last_progress_at": st.last_progress_at,
        })

    def monitor_encoder(self) -> None:
        enc = self.encoder
        if enc is None:
            self.on_failure("Encoder is not running.")
            return
        rc = enc.poll()
        if rc is not None:
            self.on_failure(f"Encoder exited (code {rc}): {enc.last_error() or 'connection lost'}")
            return
        if enc.stalled(20):
            self.on_failure("Encoder stalled (no progress for 20 s).")
            return
        self.persist_progress()
        if enc.stats.out_time > 5 and self.encoder_healthy_since is None:
            self.encoder_healthy_since = time.time()
        if self.encoder_healthy_since and time.time() - self.encoder_healthy_since > 30:
            self.backoff = self.cfg.worker.reconnect_initial_seconds
            self.failing_since = None
            if self.s()["reconnect_attempts"]:
                self.db.update_session(self.sid, reconnect_attempts=0)

    def on_failure(self, reason: str) -> None:
        """Transient failure: stop the encoder and schedule a retry with exponential backoff."""
        self.kill_encoder()
        if self.s()["stop_requested_at"]:
            return
        now = time.time()
        self.failing_since = self.failing_since or now
        give_up = self.cfg.worker.reconnect_give_up_seconds
        if give_up and now - self.failing_since > give_up:
            self.set_state(S.FAILED, error=f"Recovery failed after {int(now - self.failing_since)} s: {reason}. "
                                           "Check the host's internet connection, then press Retry or Stop stream.",
                           error_kind="recovery_failed")
            return
        self.next_attempt = now + self.backoff
        self.event(f"{reason} Reconnecting in {self.backoff:.0f} s.", "warning")
        self.backoff = min(self.backoff * 2, self.cfg.worker.reconnect_max_seconds)
        attempts = (self.s()["reconnect_attempts"] or 0) + 1
        self.set_state(S.RECONNECTING, error=reason, error_kind="reconnecting", reconnect_attempts=attempts)

    # ------------------------------------------------------------ going live
    def step_wait_ingest(self, sess: dict) -> None:
        if self.encoder is None:
            return
        stream = self.yt.get_stream(sess["stream_id"])
        self.save_ingest(stream)
        if stream and stream["status"]["streamStatus"] == "active":
            self.event("YouTube reports the ingest stream is active.")
            self.set_state(S.GOING_LIVE)
            return
        if time.time() - self.ingest_wait_started > self.cfg.worker.ingest_wait_seconds:
            self.on_failure("YouTube did not receive the stream in time.")
        else:
            time.sleep(2)

    def step_going_live(self, sess: dict) -> None:
        if self.encoder is None:
            return
        b = self.yt.get_broadcast(sess["broadcast_id"])
        if b is None:
            raise YouTubeError("liveBroadcastNotFound", "", 404, transient=False)
        life = b["status"]["lifeCycleStatus"]
        if life == "live":
            self.confirm_live(b)
            return
        if life in ("complete", "revoked"):
            self.end_by_youtube(b)
            return
        if life in ("ready", "testing"):
            self.check_stop()
            try:
                self.yt.transition(sess["broadcast_id"], "live")
                self.event("Requested transition to live; waiting for YouTube to confirm.")
            except YouTubeError as e:
                if e.reason == "redundantTransition":
                    pass
                elif e.reason == "errorStreamInactive":
                    self.ingest_wait_started = time.time()
                    self.set_state(S.WAITING_INGEST)
                    return
                else:
                    raise
        time.sleep(2)  # liveStarting / testStarting: poll again

    def confirm_live(self, b: dict) -> None:
        actual = parse_rfc3339(b.get("snippet", {}).get("actualStartTime"))
        sess = self.s()
        self.set_state(S.LIVE, live_confirmed_at=sess["live_confirmed_at"] or time.time(),
                       actual_start_utc=actual or sess["actual_start_utc"], error=None, error_kind=None)
        self.event("YouTube confirmed the broadcast is LIVE.")
        self.last_yt_poll = time.time()

    def step_live(self, sess: dict) -> None:
        now = time.time()
        if self.encoder is None or now - self.last_yt_poll < self.cfg.worker.youtube_poll_seconds:
            return
        self.last_yt_poll = now
        try:
            b = self.yt.get_broadcast(sess["broadcast_id"])
            if b is None or b["status"]["lifeCycleStatus"] in ("complete", "revoked"):
                self.end_by_youtube(b)
                return
            self.save_ingest(self.yt.get_stream(sess["stream_id"]))
            if now - self.last_metrics_poll >= self.cfg.worker.metrics_poll_seconds:
                self.last_metrics_poll = now
                m = self.yt.video_metrics(sess["broadcast_id"])
                self.db.update_session(self.sid, metrics=m)
            if sess["error_kind"] in ("transient", "quota", "auth", "youtube"):
                self.db.update_session(self.sid, error=None, error_kind=None)
        except YouTubeError as e:
            # Media keeps flowing: losing API access (network, quota, revoked token) while live does not end
            # the broadcast, so we keep streaming and tell the user what to fix.
            if e.reason == "liveBroadcastNotFound":
                raise
            hint = " Reconnect YouTube in the dashboard so status checks and Stop work." if e.kind == "auth" else ""
            self.db.update_session(self.sid, error=f"Streaming continues, but a YouTube status check failed: "
                                                   f"{e.friendly}{hint}", error_kind=e.kind)

    def save_ingest(self, stream: dict | None) -> None:
        if not stream:
            return
        st = stream.get("status", {})
        hs = st.get("healthStatus", {})
        self.db.update_session(self.sid, ingest={
            "stream_status": st.get("streamStatus"),
            "health": hs.get("status"),
            "issues": [{"severity": i.get("severity"), "reason": i.get("reason"),
                        "description": i.get("description")} for i in hs.get("configurationIssues", [])][:5],
            "checked_at": time.time(),
        })

    # ------------------------------------------------------------ recovery
    def step_reconnect(self, sess: dict) -> None:
        if time.time() < self.next_attempt:
            return
        bid = sess["broadcast_id"]
        if not bid:
            self.set_state(S.CREATING)
            return
        try:
            b = self.yt.get_broadcast(bid)
        except YouTubeError as e:
            if e.kind != "transient":
                raise
            b = "unknown"  # API unreachable: still try media, YouTube may be keeping the event open
        if b is None or (isinstance(b, dict) and b["status"]["lifeCycleStatus"] in ("complete", "revoked")):
            self.end_by_youtube(b if isinstance(b, dict) else None)
            return
        if isinstance(b, dict) and (b["status"]["lifeCycleStatus"] == "created"
                                    or not b.get("contentDetails", {}).get("boundStreamId")):
            self.set_state(S.CREATING)
            return
        try:
            self.start_encoder()
        except YouTubeError as e:
            if e.kind != "transient":
                raise
            self.on_failure(f"Could not fetch ingest details: {e.friendly}")
            return
        # Give the new encoder a moment; a dead network makes FFmpeg exit within seconds.
        deadline = time.time() + 6
        while time.time() < deadline:
            if self.s()["stop_requested_at"]:
                raise StopRequested()
            if self.encoder is None or self.encoder.poll() is not None:
                break
            time.sleep(0.25)
        if self.encoder is None or self.encoder.poll() is not None:
            err = self.encoder.last_error() if self.encoder else ""
            self.on_failure(f"Reconnect attempt failed: {err or 'ingest unreachable'}.")
            return
        life = b["status"]["lifeCycleStatus"] if isinstance(b, dict) else None
        if life == "live" or (life is None and sess["live_confirmed_at"]):
            self.event("Reconnected; media is flowing to the same broadcast.")
            self.set_state(S.LIVE, error=None, error_kind=None)
            self.last_yt_poll = 0.0
        else:
            self.ingest_wait_started = time.time()
            self.set_state(S.WAITING_INGEST, error=None, error_kind=None)

    def handle_youtube_error(self, e: YouTubeError) -> None:
        sess = self.s()
        if e.transient:
            if sess["state"] in (S.PENDING, S.CREATING, S.SCHEDULED):
                self.db.update_session(self.sid, error=f"{e.friendly} Retrying…", error_kind="transient")
                time.sleep(min(self.backoff, 30))
                self.backoff = min(self.backoff * 2, self.cfg.worker.reconnect_max_seconds)
            else:
                self.on_failure(e.friendly)
            return
        if e.reason == "liveBroadcastNotFound" and sess["broadcast_id"]:
            self.end_by_youtube(None, "The broadcast was deleted on YouTube.")
            return
        self.kill_encoder()
        if sess["broadcast_id"] and sess["state"] not in (S.PENDING, S.CREATING, S.SCHEDULED):
            # Something exists on YouTube: keep the session so Stop can clean it up.
            self.set_state(S.FAILED, error=e.friendly, error_kind=e.kind, youtube_reason=e.reason)
        elif sess["broadcast_id"]:
            self.set_state(S.FAILED, error=e.friendly, error_kind=e.kind, youtube_reason=e.reason)
        else:
            self.set_state(S.ERROR, error=e.friendly, error_kind=e.kind, youtube_reason=e.reason, ended_at=time.time())
        self.event(f"YouTube error: {e.friendly}", "error")

    def end_by_youtube(self, b: dict | None, reason: str | None = None) -> None:
        self.kill_encoder()
        if self.s()["stop_requested_at"]:
            self.set_state(S.ENDED, ended_at=time.time())
            return
        life = b["status"]["lifeCycleStatus"] if b else "deleted"
        msg = reason or {
            "complete": "YouTube ended this broadcast (it was ended in YouTube Studio or by YouTube).",
            "revoked": "YouTube revoked this broadcast (policy or eligibility). Check YouTube Studio for details.",
        }.get(life, "The broadcast no longer exists on YouTube.")
        self.set_state(S.ENDED_BY_YOUTUBE, error=msg + " Start a new stream manually if you want to continue.",
                       error_kind="ended_by_youtube", youtube_reason=life, ended_at=time.time())
        self.event(msg, "error")

    # ------------------------------------------------------------ stop
    def do_stop(self) -> None:
        self.kill_encoder()
        sess = self.s()
        if sess["state"] not in (S.STOPPING, S.END_PENDING):
            self.set_state(S.STOPPING, error=None, error_kind=None)
            self.event("Stop requested: media stopped, ending the YouTube broadcast.")
        try:
            result = self._end_on_youtube(sess)
        except YouTubeError as e:
            delay = self.end_backoff
            self.end_backoff = min(self.end_backoff * 2, self.cfg.worker.end_retry_max_seconds)
            hint = " Reconnect YouTube or end the event in YouTube Studio." if e.kind == "auth" else ""
            self.set_state(S.END_PENDING, error=f"End confirmation pending: {e.friendly}.{hint} Retrying in {delay:.0f} s.",
                           error_kind="end_pending")
            self._sleep_interruptible(delay)
            return
        self.set_state(result, ended_at=time.time(), error=None, error_kind=None)
        self.event("YouTube confirmed the broadcast has ended." if result == S.ENDED else "Stream cancelled before going live.")
        self.done = True

    def _end_on_youtube(self, sess: dict) -> str:
        bid = sess["broadcast_id"]
        if not bid and sess["broadcast_create_attempted_at"]:
            # A create call may have succeeded right before the crash; clean it up.
            for b in self.yt.list_upcoming_broadcasts():
                pub = parse_rfc3339(b.get("snippet", {}).get("publishedAt")) or 0
                if b.get("snippet", {}).get("title") == sess["title"][:100] and pub >= sess["broadcast_create_attempted_at"] - 60:
                    bid = b["id"]
                    self.db.update_session(self.sid, broadcast_id=bid)
        if not bid:
            return S.CANCELLED
        for _ in range(30):
            b = self.yt.get_broadcast(bid)
            if b is None:
                return S.ENDED if sess["live_confirmed_at"] else S.CANCELLED
            life = b["status"]["lifeCycleStatus"]
            if life in ("complete", "revoked"):
                return S.ENDED
            if life in ("created", "ready"):
                self.yt.delete_broadcast(bid)  # never went live: remove the unused upcoming event
                return S.CANCELLED
            if life in ("live", "testing"):
                try:
                    self.yt.transition(bid, "complete")
                except YouTubeError as e:
                    if e.reason not in ("redundantTransition",):
                        raise
            time.sleep(2)  # liveStarting / testStarting / just requested complete
        raise YouTubeError("endNotConfirmed", "YouTube has not confirmed the end yet", 0, transient=True)

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end and not self.w.shutting_down:
            time.sleep(0.25)


class Worker:
    def __init__(self, cfg: Config, yt_factory: Callable[[Config, DB, SecretBox], YouTubeClient] = YouTubeClient):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.db = DB(cfg.db_path)
        self.box = SecretBox(cfg.data_dir)
        self.yt = yt_factory(cfg, self.db, self.box)
        self.runners: dict[str, Runner] = {}
        self.lock = threading.Lock()
        self.shutting_down = False

    def runner_finished(self, sid: str) -> None:
        with self.lock:
            self.runners.pop(sid, None)

    def tick(self) -> None:
        self.db.set_setting("worker_heartbeat", {"ts": time.time(), "pid": os.getpid()})
        for sess in self.db.active_sessions():
            with self.lock:
                r = self.runners.get(sess["id"])
                if r is None:
                    r = Runner(self, sess["id"])
                    self.runners[sess["id"]] = r
                    r.start()
            # Watchdog: a stop request kills media immediately even if the runner is blocked on an API call.
            if sess["stop_requested_at"] and r.encoder is not None:
                with r.encoder_lock:
                    r.kill_encoder_locked()

    def run_forever(self) -> None:
        log.info("Replay Studio worker started (pid %s, db %s)", os.getpid(), self.cfg.db_path)

        def _term(signum, frame):
            self.shutting_down = True
        if threading.current_thread() is threading.main_thread():  # not in the Android app's thread
            signal.signal(signal.SIGTERM, _term)
            signal.signal(signal.SIGINT, _term)
        while not self.shutting_down:
            try:
                self.tick()
            except Exception:
                log.exception("Worker tick failed")
            time.sleep(self.cfg.worker.poll_seconds)
        log.info("Worker shutting down; stopping encoders (sessions resume on next start).")
        for r in list(self.runners.values()):
            r.done = True
            r.kill_encoder()


def main() -> None:
    setup_logging()
    Worker(load_config()).run_forever()


if __name__ == "__main__":
    main()
