"""Media library: ffprobe analysis, normalization, safe path handling."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import Config

log = logging.getLogger("replay_studio.media")

VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".ts", ".flv", ".avi"}


class MediaError(Exception):
    pass


def safe_media_path(cfg: Config, relative: str) -> Path:
    """Resolve a path inside the configured media folder; refuse anything that escapes it."""
    root = cfg.media_dir
    if not relative or "\x00" in relative:
        raise MediaError("Invalid file name.")
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise MediaError("That file is outside the configured media folder.")
    if not candidate.is_file():
        raise MediaError("File not found in the media folder.")
    if candidate.suffix.lower() not in VIDEO_EXTS:
        raise MediaError(f"Unsupported file type {candidate.suffix}.")
    return candidate


def list_media_folder(cfg: Config, limit: int = 500) -> list[dict]:
    root = cfg.media_dir
    if not root.is_dir():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if p.suffix.lower() in VIDEO_EXTS and not fn.startswith("."):
                try:
                    rp = p.resolve()
                    if root not in rp.parents:
                        continue
                    out.append({"path": str(p.relative_to(root)), "size": p.stat().st_size})
                except OSError:
                    continue
                if len(out) >= limit:
                    return out
    return out


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rate(s: str | None) -> float | None:
    if not s or s in ("0/0",):
        return None
    if "/" in s:
        n, d = s.split("/")
        return float(n) / float(d) if float(d) else None
    return _f(s)


def probe(cfg: Config, path: Path, timeout: float = 120) -> dict:
    """Run ffprobe and summarise what matters for looping. Raises MediaError if unreadable."""
    argv = [cfg.encoder.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
            str(Path(path).resolve())]
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise MediaError("ffprobe is not installed (install the ffmpeg package).") from None
    except subprocess.TimeoutExpired:
        raise MediaError("ffprobe timed out reading the file.") from None
    if cp.returncode != 0:
        raise MediaError("The file could not be read as video: " + (cp.stderr.strip().splitlines() or ["unknown error"])[-1][:300])
    data = json.loads(cp.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise MediaError("The file has no video stream.")
    duration = _f(fmt.get("duration")) or _f(v.get("duration"))
    if not duration or duration < 0.5:
        raise MediaError("The file has no usable duration (it may be incomplete or still uploading).")
    v_dur = _f(v.get("duration")) or duration
    a_dur = (_f(a.get("duration")) or duration) if a else None
    info = {
        "duration": round(duration, 3),
        "width": v.get("width"), "height": v.get("height"),
        "video_codec": v.get("codec_name"),
        "fps": round(_rate(v.get("avg_frame_rate")) or _rate(v.get("r_frame_rate")) or 0, 3),
        "r_frame_rate": v.get("r_frame_rate"), "avg_frame_rate": v.get("avg_frame_rate"),
        "has_audio": a is not None,
        "audio_codec": a.get("codec_name") if a else None,
        "audio_channels": a.get("channels") if a else None,
        "audio_sample_rate": int(a["sample_rate"]) if a and a.get("sample_rate") else None,
        "video_duration": round(v_dur, 3), "audio_duration": round(a_dur, 3) if a_dur else None,
        "video_start": _f(v.get("start_time")) or 0.0,
        "audio_start": (_f(a.get("start_time")) or 0.0) if a else None,
        "format": fmt.get("format_name"),
        "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        "size": int(fmt["size"]) if fmt.get("size") else path.stat().st_size,
    }
    info["issues"] = loop_issues(info)
    info["needs_normalize"] = bool(info["issues"])
    return info


def loop_issues(info: dict) -> list[str]:
    """Things that would cause drift, gaps or sync problems at the loop boundary."""
    issues = []
    if info["has_audio"] and info["audio_duration"] is not None \
            and abs(info["audio_duration"] - info["video_duration"]) > 0.1:
        issues.append(f"audio ({info['audio_duration']:.2f}s) and video ({info['video_duration']:.2f}s) lengths differ")
    if abs(info["video_start"]) > 0.05 or (info["has_audio"] and abs((info["audio_start"] or 0) - info["video_start"]) > 0.05):
        issues.append("streams do not start at time zero")
    r, avg = _rate(info.get("r_frame_rate")), _rate(info.get("avg_frame_rate"))
    if r and avg and abs(r - avg) / r > 0.02:
        issues.append("variable frame rate")
    return issues


COPYABLE_VIDEO = {"h264", "hevc", "mpeg4", "prores", "mjpeg"}


def video_is_clean(info: dict) -> bool:
    """True when the video track can be stream-copied into the loop-ready file."""
    r, avg = _rate(info.get("r_frame_rate")), _rate(info.get("avg_frame_rate"))
    vfr = bool(r and avg and abs(r - avg) / r > 0.02)
    return info["video_codec"] in COPYABLE_VIDEO and not vfr and abs(info["video_start"]) <= 0.05


def prepare_loop_file(cfg: Config, src: Path, info: dict, dest: Path, timeout: float | None = None) -> dict:
    """Write the loop-ready copy the encoder plays.

    Why: AAC audio is coded in 1024-sample frames plus encoder priming, so a typical MP4's decoded audio is
    10-40 ms longer than its video. -stream_loop offsets each new pass by the longer stream, so video and
    audio drift apart by that amount on every loop (measured: ~1-17 ms/loop). Here the audio is converted to
    PCM and trimmed/padded to *exactly* the video length (sample-accurate), so every pass is identical and
    A/V sync cannot drift no matter how many loops run. Clean video is stream-copied (fast, lossless);
    VFR / odd-timestamp video is re-encoded once to constant frame rate.
    Returns a dict describing what was done."""
    enc = cfg.encoder
    sr = enc.audio_sample_rate
    tmp = dest.with_name(dest.stem + ".partial" + dest.suffix)
    clean = video_is_clean(info)
    if clean:
        v_dur = info["video_duration"]
        vargs = ["-c:v", "copy"]
        vfilter: list[str] = []
    else:
        v_dur = info["video_duration"]
        vfilter = ["-vf", f"setpts=PTS-STARTPTS,scale={enc.width}:{enc.height}:force_original_aspect_ratio=decrease,"
                          f"pad={enc.width}:{enc.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={enc.fps},format=yuv420p"]
        vargs = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-g", str(enc.fps * enc.keyframe_seconds),
                 "-sc_threshold", "0", "-t", f"{v_dur:.3f}"]
    argv = [enc.ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(Path(src).resolve())]
    if not info["has_audio"]:
        argv += ["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={sr}"]
    argv += vfilter
    # Exact sample count. For re-encoded video the length is rounded to whole output frames.
    if not clean:
        v_dur = round(v_dur * enc.fps) / enc.fps
    samples = round(v_dur * sr)
    af = (f"asetpts=PTS-STARTPTS,aresample={sr}:async=1,aformat=channel_layouts=stereo,"
          f"apad,atrim=end_sample={samples}")
    argv += ["-map", "0:v:0", "-map", "0:a:0" if info["has_audio"] else "1:a:0", *vargs,
             "-af", af, "-c:a", "pcm_s16le", "-ar", str(sr), "-ac", "2", "-f", "mov", str(tmp.resolve())]
    cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if cp.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise MediaError("Preparing the loop-ready copy failed: " + cp.stderr.strip()[-300:])
    os.replace(tmp, dest)
    return {"video": "copied" if clean else "re-encoded (constant frame rate)", "samples": samples,
            "duration": v_dur}


def thumbnail(cfg: Config, src: Path, dest: Path, at: float) -> Path:
    argv = [cfg.encoder.ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{at:.2f}",
            "-i", str(Path(src).resolve()), "-frames:v", "1", "-vf", "scale=480:-2", str(dest.resolve())]
    subprocess.run(argv, capture_output=True, timeout=60, check=False)
    return dest


def disk_free(path: Path) -> int:
    return shutil.disk_usage(path).free


def library_usage(cfg: Config) -> int:
    total = 0
    for d in (cfg.library_dir, cfg.uploads_dir):
        for p in d.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    return total
