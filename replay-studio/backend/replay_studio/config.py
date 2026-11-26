"""Configuration loading.

Settings come from a TOML file (path in REPLAY_STUDIO_CONFIG, default ./config.toml).
Individual values can be overridden with environment variables named
REPLAY_STUDIO_<SECTION>_<KEY> (for example REPLAY_STUDIO_SERVER_PORT=8080).
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8787
    # Public base URL of the dashboard, used for the OAuth redirect.
    public_url: str = "http://localhost:8787"
    # Set true when the dashboard is served over HTTPS (adds Secure to cookies).
    secure_cookies: bool = False
    session_hours: int = 72


@dataclass
class PathsConfig:
    data_dir: str = "./data"
    # Folder on the Linux host whose videos can be selected without uploading.
    media_dir: str = "./media"


@dataclass
class LimitsConfig:
    max_upload_gb: float = 20.0
    library_quota_gb: float = 200.0
    min_free_disk_gb: float = 5.0
    upload_chunk_mb: int = 8


@dataclass
class GoogleConfig:
    client_id: str = ""
    client_secret: str = ""
    auth_uri: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    revoke_uri: str = "https://oauth2.googleapis.com/revoke"
    api_base: str = "https://www.googleapis.com/youtube/v3"


@dataclass
class EncoderConfig:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    width: int = 1280
    height: int = 720
    fps: int = 30
    video_bitrate_k: int = 4000
    audio_bitrate_k: int = 128
    audio_sample_rate: int = 44100
    keyframe_seconds: int = 2
    x264_preset: str = "veryfast"
    # "rtmps" (production) or "rtmp" (local test ingest only).
    ingest_protocol: str = "rtmps"
    font_file: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@dataclass
class WorkerConfig:
    poll_seconds: float = 0.5
    youtube_poll_seconds: float = 30.0
    metrics_poll_seconds: float = 60.0
    ingest_wait_seconds: float = 120.0
    reconnect_initial_seconds: float = 2.0
    reconnect_max_seconds: float = 60.0
    # Give up reconnecting after this many seconds of continuous failure (0 = never).
    reconnect_give_up_seconds: float = 1800.0
    end_retry_max_seconds: float = 60.0
    scheduled_lead_seconds: float = 90.0


@dataclass
class UIConfig:
    timezone: str = "Asia/Kolkata"


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    source: str = ""

    @property
    def data_dir(self) -> Path:
        return Path(self.paths.data_dir).expanduser().resolve()

    @property
    def media_dir(self) -> Path:
        return Path(self.paths.media_dir).expanduser().resolve()

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "replay_studio.db"

    @property
    def oauth_redirect_uri(self) -> str:
        return self.server.public_url.rstrip("/") + "/api/youtube/callback"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.library_dir, self.uploads_dir, self.data_dir / "run"):
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(self.data_dir, 0o700)

    def redacted(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "source":
                continue
            section = getattr(self, f.name)
            vals = {k.name: getattr(section, k.name) for k in fields(section)}
            if f.name == "google":
                vals["client_secret"] = "[set]" if vals["client_secret"] else "[missing]"
            out[f.name] = vals
        return out


def _coerce(value: str, default: Any) -> Any:
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value


def load_config(path: str | os.PathLike | None = None) -> Config:
    path = path or os.environ.get("REPLAY_STUDIO_CONFIG", "config.toml")
    cfg = Config()
    raw: dict[str, Any] = {}
    p = Path(path)
    if p.exists():
        with p.open("rb") as fh:
            raw = tomllib.load(fh)
        cfg.source = str(p.resolve())
        # Relative paths in the file are relative to the file itself.
        base = p.resolve().parent
        for key in ("data_dir", "media_dir"):
            v = raw.get("paths", {}).get(key)
            if v and not Path(v).expanduser().is_absolute():
                raw["paths"][key] = str(base / v)
    for f in fields(cfg):
        if f.name == "source":
            continue
        section = getattr(cfg, f.name)
        for k in fields(section):
            if k.name in raw.get(f.name, {}):
                setattr(section, k.name, raw[f.name][k.name])
            env = os.environ.get(f"REPLAY_STUDIO_{f.name.upper()}_{k.name.upper()}")
            if env is not None:
                setattr(section, k.name, _coerce(env, k.default))
    return cfg
