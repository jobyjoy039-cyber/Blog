from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from av_analysis import make_test_source
from replay_studio.api import create_app
from replay_studio.config import Config
from replay_studio.encoder import Overlay, build_command, filter_escape
from replay_studio.security import RedactingFilter, hash_password, redact, register_secret, verify_password
from replay_studio.youtube import parse_channel_url


# ---------------------------------------------------------------- pure functions

def test_redaction_of_keys_tokens_and_urls():
    register_secret("abcd-efgh-ijkl-mnop")
    text = ("pushing to rtmps://a.rtmps.youtube.com/live2/abcd-efgh-ijkl-mnop failed; "
            "Authorization: Bearer ya29.A0ARrdaM-secret; refresh_token=1//0gSecretRefreshTokenValue123; "
            "GET /api/youtube/callback?code=4/0AX4Xf&state=xyz")
    out = redact(text)
    for secret in ("abcd-efgh-ijkl-mnop", "ya29.A0ARrdaM-secret", "1//0gSecretRefreshTokenValue123", "4/0AX4Xf", "xyz"):
        assert secret not in out
    assert "rtmps://a.rtmps.youtube.com/live2/[REDACTED]" in out


def test_logging_filter_redacts(caplog):
    register_secret("zzzz-stream-key-1234")
    lg = logging.getLogger("t")
    h = caplog.handler
    h.addFilter(RedactingFilter())
    lg.warning("key is %s", "zzzz-stream-key-1234")
    assert "zzzz-stream-key-1234" not in caplog.text and "[REDACTED]" in caplog.text


def test_password_hash_roundtrip():
    h = hash_password("a long passphrase")
    assert verify_password("a long passphrase", h) and not verify_password("nope", h)


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/@MyChannel", ("handle", "@MyChannel")),
    ("youtube.com/@my.channel-1/videos", ("handle", "@my.channel-1")),
    ("@handle_x", ("handle", "@handle_x")),
    ("https://m.youtube.com/channel/UCabcdefghijklmnopqrstuv", ("id", "UCabcdefghijklmnopqrstuv")),
])
def test_parse_channel_url(url, expected):
    assert parse_channel_url(url) == expected


@pytest.mark.parametrize("bad", ["https://evil.com/@x", "https://youtube.com/watch?v=abc", "", "UCshort"])
def test_parse_channel_url_rejects(bad):
    with pytest.raises(ValueError):
        parse_channel_url(bad)


def test_command_is_argv_and_hostile_filename_is_one_argument(tmp_path):
    cfg = Config()
    evil = tmp_path / "x; rm -rf ~ $(reboot) `id`.mp4"
    evil.write_bytes(b"")
    argv = build_command(cfg, evil, "rtmps://a.rtmps.youtube.com/live2/KEY", True)
    assert isinstance(argv, list) and str(evil.resolve()) in argv
    i = argv.index("-stream_loop")
    assert argv[i + 1] == "-1" and "-re" in argv
    assert argv[argv.index("-g") + 1] == "60"                    # 2 s keyframes at 30 fps
    assert argv[-1] == "rtmps://a.rtmps.youtube.com/live2/KEY"
    assert "-ss" not in argv


def test_resume_position_and_overlay(tmp_path):
    cfg = Config()
    ov = Overlay.from_dict({"enabled": True, "text": "Sub\nscribe", "every_minutes": 15, "show_seconds": 10})
    argv = build_command(cfg, tmp_path / "a.mp4", "rtmp://h/app/k", True, 12.5, ov, tmp_path / "t:'x.txt")
    assert argv[argv.index("-ss") + 1] == "12.500"
    fc = argv[argv.index("-filter_complex") + 1]
    assert "lt(mod(t,900),10)" in fc and "textfile=" in fc
    assert "\\:" in fc and "\\'" in fc                           # escaped path characters
    assert ov.text == "Sub scribe"


def test_filter_escape():
    assert filter_escape("a:b") == "a\\\\:b"           # FFmpeg docs: level1 \: then level2 \\:
    assert filter_escape("it's") == "it\\\\\\'s"
    assert filter_escape("x,y") == "x\\,y"


# ---------------------------------------------------------------- API (in-process)

@pytest.fixture
def app_client(tmp_path):
    cfg = Config()
    cfg.paths.data_dir = str(tmp_path / "data")
    cfg.paths.media_dir = str(tmp_path / "media")
    cfg.limits.min_free_disk_gb = 0.01
    cfg.limits.upload_chunk_mb = 1
    (tmp_path / "media").mkdir()
    app = create_app(cfg)
    app.state.db.set_setting("password_hash", hash_password("pw-for-tests-123"))
    c = TestClient(app)
    return c, cfg, app


def login(c):
    assert c.post("/api/login", json={"password": "pw-for-tests-123"}).status_code == 200
    c.headers["X-Replay-Studio"] = "1"


def test_auth_required_and_csrf_header(app_client):
    c, _, _ = app_client
    assert c.get("/api/status").status_code == 401
    assert c.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert c.post("/api/login", json={"password": "pw-for-tests-123"}).status_code == 200
    assert c.get("/api/status").status_code == 200
    assert c.post("/api/uploads", json={"filename": "a.mp4", "size": 10}).status_code == 403   # no header
    c.cookies.set("rs_session", "1.2.forged")
    assert c.get("/api/status").status_code == 401


def test_media_folder_is_confined(app_client, tmp_path):
    c, cfg, _ = app_client
    login(c)
    (tmp_path / "outside.mp4").write_bytes(b"x")
    for p in ("../outside.mp4", "/etc/passwd", str(tmp_path / "outside.mp4")):
        r = c.post("/api/media/import", json={"path": p})
        assert r.status_code == 400, p
    (Path(cfg.paths.media_dir) / "link.mp4").symlink_to(tmp_path / "outside.mp4")
    assert c.post("/api/media/import", json={"path": "link.mp4"}).status_code == 400


def wait_media(c, mid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        m = c.get(f"/api/media/{mid}").json()
        if m["status"] in ("ok", "invalid"):
            return m
        time.sleep(0.2)
    raise AssertionError("media processing timed out")


def test_resumable_upload_with_interruption(app_client, tmp_path):
    c, cfg, _ = app_client
    login(c)
    src = make_test_source(tmp_path / "clip.mp4", seconds=3)
    data = src.read_bytes()
    u = c.post("/api/uploads", json={"filename": "clip.mp4", "size": len(data)}).json()
    first = 40_000
    assert c.put(f"/api/uploads/{u['id']}", params={"offset": 0}, content=data[:first]).json()["received"] == first
    # "connection dropped": a new client asks where to resume, and stale offsets are refused
    again = c.post("/api/uploads", json={"filename": "clip.mp4", "size": len(data)}).json()
    assert again["id"] == u["id"] and again["received"] == first
    r = c.put(f"/api/uploads/{u['id']}", params={"offset": 0}, content=data[:10])
    assert r.status_code == 409 and r.json()["received"] == first
    r = c.put(f"/api/uploads/{u['id']}", params={"offset": first}, content=data[first:]).json()
    assert r["complete"]
    m = wait_media(c, r["media"]["id"])
    assert m["status"] == "ok", m
    p = m["probe"]
    assert p["has_audio"] and p["width"] == 1280 and abs(p["duration"] - 3.0) < 0.05 and m["loop_ready"]
    assert c.get(f"/api/media/{m['id']}/file", headers={"Range": "bytes=0-99"}).status_code == 206


def test_incomplete_or_bogus_files_are_reported(app_client, tmp_path):
    c, cfg, app = app_client
    login(c)
    src = make_test_source(tmp_path / "full.mp4", seconds=3)
    trunc = Path(cfg.paths.media_dir) / "truncated.mp4"
    trunc.write_bytes(src.read_bytes()[: src.stat().st_size // 2])
    (Path(cfg.paths.media_dir) / "notvideo.mp4").write_bytes(b"hello world" * 100)
    for name in ("truncated.mp4", "notvideo.mp4"):
        m = c.post("/api/media/import", json={"path": name}).json()
        m = wait_media(c, m["id"])
        assert m["status"] == "invalid" and m["error"], m
    assert c.post("/api/uploads", json={"filename": "evil.sh", "size": 10}).status_code == 400
    assert c.post("/api/uploads", json={"filename": "huge.mp4", "size": 10 ** 15}).status_code == 413


def test_session_validation(app_client, tmp_path):
    c, cfg, app = app_client
    login(c)
    # Pretend a channel is connected so validation (not OAuth) is exercised.
    app.state.yt.connected = lambda: True
    app.state.db.set_setting("channel", {"id": "UC" + "x" * 22, "title": "T"})
    src = make_test_source(Path(cfg.paths.media_dir) / "ok.mp4", seconds=2)
    m = wait_media(c, c.post("/api/media/import", json={"path": src.name}).json()["id"])
    base = {"media_id": m["id"], "title": "Loop", "made_for_kids": False, "confirm_rights": True}
    assert c.post("/api/sessions", json={**base, "confirm_rights": False}).status_code == 400
    assert c.post("/api/sessions", json={**base, "privacy": "public"}).status_code == 400
    assert c.post("/api/sessions", json={**base, "title": "<b>"}).status_code == 422
    assert c.post("/api/sessions", json={**base, "scheduled_start": "2001-01-01T10:00"}).status_code == 400
    r = c.post("/api/sessions", json={**base, "scheduled_start": "2099-01-01T10:00"})
    assert r.status_code == 400  # more than a year ahead
    # naive schedule times are Asia/Kolkata; stored as UTC
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    local = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(hours=2)).replace(second=0, microsecond=0)
    r = c.post("/api/sessions", json={**base, "scheduled_start": local.replace(tzinfo=None).isoformat()})
    assert r.status_code == 200, r.text
    s = r.json()["session"]
    assert s["state"] == "scheduled" and s["privacy"] == "unlisted"
    assert abs(s["scheduled_start_utc"] - local.timestamp()) < 1
    assert s["description"].startswith("Prerecorded video playing on repeat.")
    # one active stream per channel
    assert c.post("/api/sessions", json=base).status_code == 409
    # public with confirmation is accepted by validation (still blocked here by the active session)
    assert c.post("/api/sessions", json={**base, "privacy": "public", "confirm_public": True}).status_code == 409
    # stop persists the intent immediately
    st = c.post(f"/api/sessions/{s['id']}/stop").json()["session"]
    assert st["stop_requested"]


def test_overlay_preview_renders_png(app_client):
    c, _, _ = app_client
    login(c)
    r = c.post("/api/overlay/preview", json={"enabled": True, "text": "Subscribe for more: it's free!",
                                            "every_minutes": 10, "show_seconds": 8, "position": "top"})
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


def test_diagnostics_hide_secrets(app_client):
    c, cfg, _ = app_client
    cfg.google.client_secret = "GOCSPX-very-secret"
    login(c)
    body = c.get("/api/diagnostics").text
    assert "GOCSPX-very-secret" not in body
