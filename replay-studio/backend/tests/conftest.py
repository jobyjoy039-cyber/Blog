from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from av_analysis import make_test_source  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "correct-horse-battery"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(fn, timeout: float, interval: float = 0.25, what: str = "condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except (httpx.HTTPError, KeyError, TypeError):
            pass
        time.sleep(interval)
    raise AssertionError(f"Timed out waiting for {what} (last={last!r})")


def ffmpeg_loop_pids() -> list[int]:
    pids = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if cmd and cmd[0].endswith(b"ffmpeg") and b"-stream_loop" in cmd:
            pids.append(int(p.name))
    return pids


class Stack:
    def __init__(self, tmp: Path, extra_cfg: str = "", extra_env: dict | None = None):
        self.tmp = tmp
        self.api_port, self.fake_port, self.rtmp_port = free_port(), free_port(), free_port()
        (tmp / "media").mkdir()
        self.config = tmp / "config.toml"
        self.config.write_text(f"""
[server]
host = "127.0.0.1"
port = {self.api_port}
public_url = "http://127.0.0.1:{self.api_port}"
[paths]
data_dir = "{tmp / 'data'}"
media_dir = "{tmp / 'media'}"
[limits]
min_free_disk_gb = 0.1
upload_chunk_mb = 1
[google]
client_id = "test-client.apps.googleusercontent.com"
client_secret = "test-client-secret-value"
auth_uri = "http://127.0.0.1:{self.fake_port}/o/oauth2/auth"
token_uri = "http://127.0.0.1:{self.fake_port}/token"
revoke_uri = "http://127.0.0.1:{self.fake_port}/revoke"
api_base = "http://127.0.0.1:{self.fake_port}"
[encoder]
ingest_protocol = "rtmp"
video_bitrate_k = 2500
[worker]
poll_seconds = 0.25
youtube_poll_seconds = 2
metrics_poll_seconds = 4
ingest_wait_seconds = 40
reconnect_initial_seconds = 1
reconnect_max_seconds = 4
end_retry_max_seconds = 2
scheduled_lead_seconds = 55
{extra_cfg}
""")
        self.env = {**os.environ, "REPLAY_STUDIO_CONFIG": str(self.config), "PYTHONUNBUFFERED": "1",
                    **(extra_env or {})}
        self.procs: dict[str, subprocess.Popen] = {}
        self.logs = tmp / "logs"
        self.logs.mkdir()
        self.client: httpx.Client | None = None
        self.fake = httpx.Client(base_url=f"http://127.0.0.1:{self.fake_port}", timeout=10)

    def _spawn(self, name: str, argv: list[str]) -> None:
        log = open(self.logs / f"{name}.log", "ab")
        self.procs[name] = subprocess.Popen(argv, env=self.env, stdout=log, stderr=subprocess.STDOUT, cwd=self.tmp)

    def start_fake(self) -> None:
        self._spawn("fake", [sys.executable, "-m", "replay_studio.fake_youtube", "--port", str(self.fake_port),
                             "--rtmp-port", str(self.rtmp_port), "--record-dir", str(self.tmp / "ingest")])
        wait_for(lambda: self.fake.get("/_control/state").status_code == 200, 15, what="fake youtube")

    def start_api(self) -> None:
        self._spawn("api", [sys.executable, "-m", "replay_studio", "api"])
        wait_for(lambda: httpx.get(f"http://127.0.0.1:{self.api_port}/api/health").status_code == 200, 20,
                 what="api")

    def stop_api(self) -> None:
        self.stop("api")

    def start_worker(self) -> None:
        self._spawn("worker", [sys.executable, "-m", "replay_studio", "worker"])

    def stop(self, name: str, sig: int = signal.SIGTERM) -> None:
        p = self.procs.pop(name, None)
        if p and p.poll() is None:
            p.send_signal(sig)
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()

    def login(self) -> httpx.Client:
        c = httpx.Client(base_url=f"http://127.0.0.1:{self.api_port}", timeout=30,
                         headers={"X-Replay-Studio": "1"})
        r = c.post("/api/login", json={"password": PASSWORD})
        assert r.status_code == 200, r.text
        self.client = c
        return c

    def connect_youtube(self) -> None:
        c = self.client
        url = c.get("/api/youtube/connect").json()["url"]
        r = httpx.get(url, follow_redirects=False)           # "Google" consent -> redirect back
        cb = r.headers["location"]
        r = c.get(cb.replace(f"http://127.0.0.1:{self.api_port}", ""), follow_redirects=False)
        assert r.headers["location"] == "/?connected=1", r.headers["location"]

    def upload(self, path: Path) -> str:
        c = self.client
        data = path.read_bytes()
        u = c.post("/api/uploads", json={"filename": path.name, "size": len(data)}).json()
        off, chunk = u["received"], u["chunk_bytes"]
        res = None
        while off < len(data):
            res = c.put(f"/api/uploads/{u['id']}", params={"offset": off}, content=data[off:off + chunk]).json()
            off = res["received"]
        mid = res["media"]["id"]
        wait_for(lambda: c.get(f"/api/media/{mid}").json()["status"] in ("ok", "invalid"), 60, what="probe")
        return mid

    def status(self) -> dict:
        return self.client.get("/api/status").json()

    def session(self) -> dict | None:
        return self.status()["session"]

    def fake_state(self) -> dict:
        return self.fake.get("/_control/state").json()

    def start_session(self, mid: str, **kw) -> dict:
        body = {"media_id": mid, "title": "Replay Studio test", "made_for_kids": False, "confirm_rights": True,
                "privacy": "unlisted", **kw}
        r = self.client.post("/api/sessions", json=body)
        assert r.status_code == 200, r.text
        return r.json()["session"]

    def wait_state(self, states: str | tuple, timeout: float = 60) -> dict:
        states = (states,) if isinstance(states, str) else states

        def check():
            sid = self.current_id
            s = self.client.get(f"/api/sessions/{sid}").json()["session"]
            return s if s["state"] in states else None
        return wait_for(check, timeout, what=f"state {states}")

    current_id: str = ""

    def close(self) -> None:
        for name in list(self.procs):
            self.stop(name, signal.SIGKILL if name == "fake" else signal.SIGTERM)
        for pid in ffmpeg_loop_pids():
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
                if str(self.tmp).encode() in cmd:
                    os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        subprocess.run(["pkill", "-f", f"rtmp://127.0.0.1:{self.rtmp_port}"], check=False)

    def our_encoders(self) -> list[int]:
        out = []
        for pid in ffmpeg_loop_pids():
            try:
                if str(self.tmp).encode() in Path(f"/proc/{pid}/cmdline").read_bytes():
                    out.append(pid)
            except OSError:
                pass
        return out


@pytest.fixture(scope="session")
def test_video(tmp_path_factory) -> Path:
    return make_test_source(tmp_path_factory.mktemp("src") / "loop_test.mp4", seconds=4)


@pytest.fixture
def stack_factory(tmp_path):
    stacks = []

    def make(extra_cfg: str = "", extra_env: dict | None = None) -> Stack:
        d = tmp_path / f"stack{len(stacks)}"
        d.mkdir()
        st = Stack(d, extra_cfg, extra_env)
        stacks.append(st)
        subprocess.run([sys.executable, "-m", "replay_studio", "set-password", "--password", PASSWORD],
                       env=st.env, check=True, capture_output=True)
        st.start_fake()
        st.start_api()
        st.start_worker()
        st.login()
        st.connect_youtube()
        return st
    yield make
    for st in stacks:
        st.close()


@pytest.fixture
def stack(stack_factory) -> Stack:
    return stack_factory()
