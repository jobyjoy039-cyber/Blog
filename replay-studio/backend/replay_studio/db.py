"""SQLite persistence shared by the API process and the stream worker."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS secrets (name TEXT PRIMARY KEY, ciphertext TEXT NOT NULL, updated_at REAL);
CREATE TABLE IF NOT EXISTS media (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL, source TEXT NOT NULL,
  size INTEGER, probe TEXT, status TEXT NOT NULL, error TEXT, play_path TEXT,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
  id TEXT PRIMARY KEY, filename TEXT NOT NULL, size INTEGER NOT NULL, received INTEGER NOT NULL,
  tmp_path TEXT NOT NULL, media_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  media_id TEXT NOT NULL,
  title TEXT NOT NULL, description TEXT NOT NULL, privacy TEXT NOT NULL, made_for_kids INTEGER NOT NULL,
  scheduled_start_utc REAL,
  state TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  stop_requested_at REAL,
  idempotency_key TEXT UNIQUE,
  broadcast_id TEXT, stream_id TEXT,
  broadcast_create_attempted_at REAL, stream_create_attempted_at REAL,
  live_confirmed_at REAL, actual_start_utc REAL, ended_at REAL,
  played_total REAL NOT NULL DEFAULT 0,
  media_duration REAL,
  encoder_pid INTEGER,
  encoder TEXT, ingest TEXT, metrics TEXT, overlay TEXT,
  error TEXT, error_kind TEXT, youtube_reason TEXT,
  reconnect_attempts INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_per_channel ON sessions(channel_id) WHERE active = 1;
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, ts REAL NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_session ON events(session_id, id);
"""

# Session states
SCHEDULED = "scheduled"
PENDING = "pending"            # start requested, worker has not picked it up
CREATING = "creating"          # creating/binding YouTube resources
STARTING_ENCODER = "starting_encoder"
WAITING_INGEST = "waiting_ingest"
GOING_LIVE = "going_live"      # transition to live requested, awaiting confirmation
LIVE = "live"
RECONNECTING = "reconnecting"
FAILED = "failed"              # recovery gave up; broadcast may still exist -> user must Stop
STOPPING = "stopping"
END_PENDING = "end_pending"    # media stopped, YouTube end not yet confirmed
ENDED = "ended"
CANCELLED = "cancelled"        # stopped before ever going live
ENDED_BY_YOUTUBE = "ended_by_youtube"
ERROR = "error"                # could not start; nothing left running

TERMINAL = {ENDED, CANCELLED, ENDED_BY_YOUTUBE, ERROR}

JSON_COLS = {"encoder", "ingest", "metrics", "overlay", "probe"}


class DB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("PRAGMA synchronous=NORMAL")
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Write transaction taken immediately (serialises concurrent writers)."""
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for k in JSON_COLS & d.keys():
            if d[k]:
                d[k] = json.loads(d[k])
        return d

    # ------------------------------------------------------------ settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.conn() as c:
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set_setting(self, key: str, value: Any) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (key, json.dumps(value)))

    def delete_setting(self, key: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM settings WHERE key=?", (key,))

    # ------------------------------------------------------------ secrets (ciphertext only)
    def put_secret(self, name: str, ciphertext: str) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO secrets(name,ciphertext,updated_at) VALUES(?,?,?) "
                      "ON CONFLICT(name) DO UPDATE SET ciphertext=excluded.ciphertext, updated_at=excluded.updated_at",
                      (name, ciphertext, time.time()))

    def get_secret(self, name: str) -> str | None:
        with self.conn() as c:
            r = c.execute("SELECT ciphertext FROM secrets WHERE name=?", (name,)).fetchone()
        return r["ciphertext"] if r else None

    def delete_secret(self, name: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM secrets WHERE name=?", (name,))

    # ------------------------------------------------------------ media
    def add_media(self, name: str, path: str, source: str, size: int) -> dict:
        mid = uuid.uuid4().hex[:12]
        with self.conn() as c:
            c.execute("INSERT INTO media(id,name,path,source,size,status,created_at) VALUES(?,?,?,?,?,?,?)",
                      (mid, name, path, source, size, "probing", time.time()))
        return self.get_media(mid)

    def get_media(self, mid: str) -> dict | None:
        with self.conn() as c:
            return self._row(c.execute("SELECT * FROM media WHERE id=?", (mid,)).fetchone())

    def find_media_by_path(self, path: str) -> dict | None:
        with self.conn() as c:
            return self._row(c.execute("SELECT * FROM media WHERE path=?", (path,)).fetchone())

    def list_media(self) -> list[dict]:
        with self.conn() as c:
            return [self._row(r) for r in c.execute("SELECT * FROM media ORDER BY created_at DESC")]

    def update_media(self, mid: str, **fields: Any) -> None:
        self._update("media", mid, fields)

    def delete_media(self, mid: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM media WHERE id=?", (mid,))

    # ------------------------------------------------------------ uploads
    def create_upload(self, filename: str, size: int, tmp_path: str) -> dict:
        uid = uuid.uuid4().hex
        now = time.time()
        with self.conn() as c:
            c.execute("INSERT INTO uploads(id,filename,size,received,tmp_path,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                      (uid, filename, size, 0, tmp_path, now, now))
        return self.get_upload(uid)

    def get_upload(self, uid: str) -> dict | None:
        with self.conn() as c:
            return self._row(c.execute("SELECT * FROM uploads WHERE id=?", (uid,)).fetchone())

    def list_uploads(self) -> list[dict]:
        with self.conn() as c:
            return [self._row(r) for r in c.execute("SELECT * FROM uploads WHERE media_id IS NULL ORDER BY created_at DESC")]

    def update_upload(self, uid: str, **fields: Any) -> None:
        fields["updated_at"] = time.time()
        self._update("uploads", uid, fields)

    def delete_upload(self, uid: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM uploads WHERE id=?", (uid,))

    # ------------------------------------------------------------ sessions
    def get_session(self, sid: str) -> dict | None:
        with self.conn() as c:
            return self._row(c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone())

    def active_session(self, channel_id: str | None = None) -> dict | None:
        with self.conn() as c:
            if channel_id:
                r = c.execute("SELECT * FROM sessions WHERE active=1 AND channel_id=?", (channel_id,)).fetchone()
            else:
                r = c.execute("SELECT * FROM sessions WHERE active=1 ORDER BY created_at DESC").fetchone()
        return self._row(r)

    def active_sessions(self) -> list[dict]:
        with self.conn() as c:
            return [self._row(r) for r in c.execute("SELECT * FROM sessions WHERE active=1 ORDER BY created_at")]

    def recent_sessions(self, limit: int = 20) -> list[dict]:
        with self.conn() as c:
            return [self._row(r) for r in
                    c.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,))]

    def update_session(self, sid: str, **fields: Any) -> None:
        if "state" in fields:
            fields["active"] = 0 if fields["state"] in TERMINAL else 1
        fields["updated_at"] = time.time()
        self._update("sessions", sid, fields)

    def request_stop(self, sid: str) -> dict | None:
        """Persist stop intent atomically. Returns the updated session."""
        with self.tx() as c:
            r = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            if r is None:
                return None
            if r["active"] and r["stop_requested_at"] is None:
                c.execute("UPDATE sessions SET stop_requested_at=?, updated_at=? WHERE id=?",
                          (time.time(), time.time(), sid))
        return self.get_session(sid)

    def _update(self, table: str, key: str, fields: dict[str, Any]) -> None:
        if not fields:
            return
        cols, vals = [], []
        for k, v in fields.items():
            if k in JSON_COLS and v is not None and not isinstance(v, str):
                v = json.dumps(v)
            cols.append(f"{k}=?")
            vals.append(v)
        vals.append(key)
        with self.conn() as c:
            c.execute(f"UPDATE {table} SET {', '.join(cols)} WHERE id=?", vals)

    # ------------------------------------------------------------ events
    def log_event(self, session_id: str | None, message: str, level: str = "info") -> None:
        from .security import redact
        with self.conn() as c:
            c.execute("INSERT INTO events(session_id,ts,level,message) VALUES(?,?,?,?)",
                      (session_id, time.time(), level, redact(message)[:2000]))

    def events(self, session_id: str, limit: int = 50) -> list[dict]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM events WHERE session_id=? ORDER BY id DESC LIMIT ?",
                             (session_id, limit)).fetchall()
        return [dict(r) for r in rows]
