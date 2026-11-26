"""Long-running FFmpeg process that loops one local file into an RTMP(S) ingest.

The command is always built as an argv list and executed without a shell, so file names
and titles can never be interpreted as shell syntax.
"""
from __future__ import annotations

import collections
import ctypes
import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .security import redact

log = logging.getLogger("replay_studio.encoder")


def filter_escape(value: str) -> str:
    """Escape a value for an FFmpeg filter option: level 1 (option value), then level 2 (filtergraph)."""
    v = value
    for ch in ("\\", "'", ":"):
        v = v.replace(ch, "\\" + ch)
    for ch in ("\\", "'", "[", "]", ",", ";"):
        v = v.replace(ch, "\\" + ch)
    return v


@dataclass
class Overlay:
    enabled: bool = False
    text: str = "Enjoying the stream? Subscribe!"
    every_minutes: float = 10.0
    show_seconds: float = 8.0
    position: str = "bottom"  # "top" or "bottom"

    @classmethod
    def from_dict(cls, d: dict | None) -> "Overlay":
        d = d or {}
        o = cls(**{k: d[k] for k in ("enabled", "text", "every_minutes", "show_seconds", "position") if k in d})
        o.text = (o.text or "").replace("\r", " ").replace("\n", " ")[:120]
        o.every_minutes = max(1.0, float(o.every_minutes))
        o.show_seconds = min(max(2.0, float(o.show_seconds)), o.every_minutes * 60)
        o.position = "top" if o.position == "top" else "bottom"
        return o


def overlay_filter(cfg: Config, ov: Overlay, textfile: Path) -> str:
    """drawbox+drawtext shown for show_seconds every every_minutes, keyed off the continuous output clock."""
    period = ov.every_minutes * 60
    enable = f"lt(mod(t,{period:.0f}),{ov.show_seconds:.0f})"
    y_box = "ih*0.06" if ov.position == "top" else "ih*0.80"
    y_txt = "h*0.06+(h*0.14-text_h)/2" if ov.position == "top" else "h*0.80+(h*0.14-text_h)/2"
    font = filter_escape(cfg.encoder.font_file)
    tf = filter_escape(str(textfile))
    return (f"drawbox=x=iw*0.1:y={y_box}:w=iw*0.8:h=ih*0.14:color=0xCC0000@0.85:t=fill:enable='{enable}',"
            f"drawtext=fontfile={font}:textfile={tf}:fontcolor=white:fontsize=h*0.055:"
            f"x=(w-text_w)/2:y={y_txt}:enable='{enable}'")


def build_command(cfg: Config, input_path: Path, output_url: str, has_audio: bool, start_at: float = 0.0,
                  overlay: Overlay | None = None, overlay_textfile: Path | None = None,
                  output_format: str = "flv") -> list[str]:
    e = cfg.encoder
    gop = e.fps * e.keyframe_seconds
    argv = [e.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "warning",
            "-progress", "pipe:1", "-stats_period", "1"]
    if start_at > 0.01:
        argv += ["-ss", f"{start_at:.3f}"]
    # -re: read in real time. -stream_loop -1: loop forever inside one process; FFmpeg offsets the
    # timestamps of each new pass by the file duration, so output timestamps stay continuous.
    argv += ["-re", "-stream_loop", "-1", "-fflags", "+genpts", "-i", str(input_path.resolve())]
    if not has_audio:
        argv += ["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={e.audio_sample_rate}"]
    vchain = (f"[0:v:0]scale={e.width}:{e.height}:force_original_aspect_ratio=decrease,"
              f"pad={e.width}:{e.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={e.fps}")
    if overlay and overlay.enabled and overlay_textfile:
        vchain += "," + overlay_filter(cfg, overlay, overlay_textfile)
    vchain += ",format=yuv420p[v]"
    asrc = "[0:a:0]" if has_audio else "[1:a:0]"
    achain = f"{asrc}aresample={e.audio_sample_rate}:async=1000,aformat=channel_layouts=stereo[a]"
    argv += ["-filter_complex", f"{vchain};{achain}", "-map", "[v]", "-map", "[a]"]
    argv += ["-c:v", "libx264", "-preset", e.x264_preset, "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-b:v", f"{e.video_bitrate_k}k", "-minrate", f"{e.video_bitrate_k}k",
             "-maxrate", f"{e.video_bitrate_k}k", "-bufsize", f"{e.video_bitrate_k * 2}k",
             "-x264-params", "nal-hrd=cbr:force-cfr=1",
             "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0", "-r", str(e.fps),
             "-c:a", "aac", "-b:a", f"{e.audio_bitrate_k}k", "-ar", str(e.audio_sample_rate), "-ac", "2"]
    if output_format == "flv":
        argv += ["-f", "flv", "-flvflags", "no_duration_filesize", output_url]
    else:
        argv += ["-f", output_format, output_url]
    return argv


def _set_pdeathsig() -> None:  # pragma: no cover - runs in child
    """Make FFmpeg die if the worker dies, so a restarted worker never doubles the ingest."""
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except OSError:
        pass


@dataclass
class EncoderStats:
    out_time: float = 0.0
    fps: float = 0.0
    bitrate_kbps: float = 0.0
    speed: float = 0.0
    frames: int = 0
    dropped: int = 0
    duplicated: int = 0
    last_progress_at: float = 0.0
    total_size: int = 0


class Encoder:
    def __init__(self, argv: list[str]):
        self.argv = argv
        self.proc: subprocess.Popen | None = None
        self.stats = EncoderStats()
        self.stderr_tail: collections.deque[str] = collections.deque(maxlen=40)
        self.started_at = 0.0
        self._threads: list[threading.Thread] = []

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    def start(self) -> None:
        log.info("Starting encoder: %s", redact(" ".join(self.argv)))
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1,
                                     preexec_fn=_set_pdeathsig, close_fds=True)
        self.started_at = time.time()
        self.stats.last_progress_at = time.time()
        for target in (self._read_progress, self._read_stderr):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)

    def _read_progress(self) -> None:
        assert self.proc and self.proc.stdout
        cur: dict[str, str] = {}
        for line in self.proc.stdout:
            line = line.strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            cur[k] = v
            if k == "progress":
                self._apply(cur)
                cur = {}

    def _apply(self, d: dict[str, str]) -> None:
        s = self.stats
        try:
            if d.get("out_time_us", "N/A") not in ("N/A", ""):
                s.out_time = max(s.out_time, int(d["out_time_us"]) / 1e6)
            s.fps = float(d.get("fps", s.fps) or 0)
            br = d.get("bitrate", "")
            if br.endswith("kbits/s"):
                s.bitrate_kbps = float(br[:-7])
            sp = d.get("speed", "")
            if sp.endswith("x"):
                s.speed = float(sp[:-1])
            s.frames = int(d.get("frame", s.frames) or 0)
            s.dropped = int(d.get("drop_frames", s.dropped) or 0)
            s.duplicated = int(d.get("dup_frames", s.duplicated) or 0)
            if d.get("total_size", "N/A") != "N/A":
                s.total_size = int(d["total_size"])
        except ValueError:
            pass
        s.last_progress_at = time.time()

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for line in self.proc.stderr:
            line = redact(line.rstrip())
            if line:
                self.stderr_tail.append(line)
                log.warning("ffmpeg: %s", line)

    def poll(self) -> int | None:
        return self.proc.poll() if self.proc else 0

    def stalled(self, seconds: float = 20.0) -> bool:
        return self.poll() is None and time.time() - self.stats.last_progress_at > seconds

    def stop(self, timeout: float = 5.0) -> None:
        p = self.proc
        if not p or p.poll() is not None:
            return
        try:
            p.send_signal(signal.SIGINT)  # lets FFmpeg flush and close the RTMP connection cleanly
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)
        except ProcessLookupError:
            pass

    def kill(self) -> None:
        p = self.proc
        if p and p.poll() is None:
            p.kill()
            p.wait(timeout=5)

    def last_error(self) -> str:
        return " | ".join(list(self.stderr_tail)[-3:])


def kill_stale_encoder(pid: int | None) -> bool:
    """Kill an FFmpeg left over from a crashed worker (only if the pid really is ffmpeg)."""
    if not pid:
        return False
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    if not cmd or b"ffmpeg" not in os.path.basename(cmd[0]) or b"-stream_loop" not in cmd:
        return False
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except OSError:
        return False
