"""Analyse a recorded ingest (FLV) for loop continuity and A/V sync.

The test source flashes the whole frame white and plays a loud 1 kHz beep during the first 0.2 s
of every pass, over a continuous quiet 300 Hz tone. In the recording we expect:
  * flash onsets spaced exactly one file-duration apart (loop timing),
  * each beep onset within 1.5 frames of its flash onset (A/V sync, also across loops),
  * no timestamp gaps or backward jumps, no black frames and no silence at the boundaries.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _run(argv: list[str]) -> str:
    cp = subprocess.run(argv, capture_output=True, text=True, check=False)
    return cp.stdout + cp.stderr


def packet_times(path: Path, stream: str) -> list[float]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", "packet=pts_time",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return [float(p["pts_time"]) for p in json.loads(out).get("packets", []) if p.get("pts_time") not in (None, "N/A")]


def onsets(times_values: list[tuple[float, float]], threshold: float, min_gap: float = 1.0) -> list[float]:
    res, prev = [], False
    for t, v in times_values:
        on = v > threshold
        if on and not prev and (not res or t - res[-1] > min_gap):
            res.append(t)
        prev = on
    return res


def flash_onsets(path: Path) -> list[float]:
    out = _run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0", "-vf",
                "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"])
    tv, t = [], None
    for line in out.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"YAVG=([\d.]+)", line)
        if m and t is not None:
            tv.append((t, float(m.group(1))))
    return onsets(tv, 200)


def beep_onsets(path: Path) -> list[float]:
    out = _run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:a:0", "-af",
                "asetnsamples=n=441:p=0,astats=metadata=1:reset=1,"
                "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"])
    tv, t = [], None
    for line in out.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"RMS_level=(-?[\d.]+|-inf)", line)
        if m and t is not None:
            tv.append((t, -200.0 if m.group(1) == "-inf" else float(m.group(1))))
    return onsets(tv, -15)


def detect(path: Path, filt: str, key: str) -> list[str]:
    out = _run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), *filt.split(" "), "-f", "null", "-"])
    return [l for l in out.splitlines() if key in l]


def analyse(path: Path, loop_seconds: float) -> dict:
    v = packet_times(path, "v:0")
    a = packet_times(path, "a:0")
    v_sorted = sorted(v)
    end = v_sorted[-1] - 0.5 if v_sorted else 0   # ignore the final packets cut by Stop
    v_sorted = [t for t in v_sorted if t < end]
    a = [t for t in a if t < end]
    v_gaps = [b - x for x, b in zip(v_sorted, v_sorted[1:])]
    a_gaps = [b - x for x, b in zip(a, a[1:])]
    flashes, beeps = flash_onsets(path), beep_onsets(path)
    pairs = []
    for f in flashes:
        near = min(beeps, key=lambda b: abs(b - f)) if beeps else None
        pairs.append((f, near, None if near is None else near - f))
    spacing = [b - x for x, b in zip(flashes, flashes[1:])]
    return {
        "video_packets": len(v), "audio_packets": len(a),
        "video_span": (v_sorted[-1] - v_sorted[0]) if v else 0,
        "audio_span": (a[-1] - a[0]) if a else 0,
        "max_video_gap": max(v_gaps) if v_gaps else None,
        "max_audio_gap": max(a_gaps) if a_gaps else None,
        "audio_backwards": sum(1 for g in a_gaps if g < 0),
        "flash_onsets": flashes, "beep_onsets": beeps, "loop_spacing": spacing,
        "av_offsets": [p[2] for p in pairs],
        "black": detect(path, "-map 0:v:0 -vf blackdetect=d=0.05:pix_th=0.05", "black_start"),
        "silence": detect(path, "-map 0:a:0 -af silencedetect=noise=-45dB:d=0.05", "silence_start"),
        "loop_seconds": loop_seconds,
    }


def make_test_source(path: Path, seconds: int = 4, audio: bool = True) -> Path:
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:duration={seconds}"]
    if audio:
        argv += ["-f", "lavfi", "-i", f"sine=frequency=300:sample_rate=44100:duration={seconds}",
                 "-f", "lavfi", "-i", f"sine=frequency=1000:sample_rate=44100:duration={seconds}",
                 "-filter_complex",
                 "[0:v]drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='lt(t,0.2)'[v];"
                 "[1:a]volume=0.4[lo];[2:a]volume='if(lt(t,0.2),7,0)':eval=frame[hi];"
                 "[lo][hi]amix=inputs=2:normalize=0[a]",
                 "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-shortest"]
    argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(argv, check=True)
    return path


if __name__ == "__main__":
    import sys
    print(json.dumps(analyse(Path(sys.argv[1]), float(sys.argv[2])), indent=1))
