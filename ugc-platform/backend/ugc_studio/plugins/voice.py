"""Voice engines.

VoiceStudio (github.com/debpalash/VoiceStudio) is used as a speech server: it
hosts many TTS engines (KittenTTS, OmniVoice, CosyVoice, VoxCPM, ...) behind one
HTTP API, so new voices arrive without code changes here. Pick the engine with
UGC_VOICESTUDIO_ENGINE. Check each engine's weights licence before commercial
use: KittenTTS is Apache-2.0, OmniVoice weights are non-commercial.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import httpx

from ..domain import JobRequest
from .base import AlignPlugin, VoicePlugin
from .brain_local import WORDS_PER_SECOND
from ..domain import Word


def wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / float(w.getframerate())
    except wave.Error:  # non-PCM WAV: ask ffprobe
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())


def trim_silence(path: Path, keep: float = 0.06) -> float:
    """Cut leading/trailing silence from a voice clip in place; return new duration.
    TTS engines pad each clip, and across 5-7 scenes the padding adds seconds."""
    tmp = path.with_suffix(".trim.wav")
    edge = f"silenceremove=start_periods=1:start_threshold=-42dB:start_silence={keep}"
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path),
         "-af", f"{edge},areverse,{edge},areverse", str(tmp)],
        capture_output=True,
    )
    if proc.returncode == 0 and tmp.exists() and wav_duration(tmp) > 0.3:
        tmp.replace(path)
    else:
        tmp.unlink(missing_ok=True)
    return wav_duration(path)


class VoiceStudioVoice(VoicePlugin):
    name = "voicestudio"
    priority = 10
    license = "AGPL-3.0 server (separate process); engine weights vary"
    description = "Speech via a VoiceStudio server (KittenTTS by default; cloning engines available)."

    def __init__(self, base_url: str, engine: str, speed: float = 1.2, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.engine = engine
        self.speed = speed  # UGC delivery is brisk; 1.2 is ~2.8 words/s on KittenTTS
        self.client = client or httpx.Client(timeout=httpx.Timeout(300, connect=3))
        self.commercial_ok = engine in {"kittentts", "voxcpm2", "moss-tts-nano", "gpt-sovits", "pockettts"}

    def available(self) -> tuple[bool, str]:
        try:
            r = self.client.get(f"{self.base_url}/health", timeout=2)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True, ""
            return False, f"VoiceStudio not ready: {r.text[:80]}"
        except (httpx.HTTPError, ValueError) as e:
            return False, f"VoiceStudio unreachable at {self.base_url} ({type(e).__name__})"

    def synthesize(self, text: str, out_path: Path, request: JobRequest) -> float:
        data = {"text": text, "engine": self.engine, "speed": str(self.speed)}
        if request.voice:
            data["profile_id"] = request.voice
        if request.language and request.language != "en":
            data["language"] = request.language
        r = self.client.post(f"{self.base_url}/generate", data=data, files={"_": ("", b"")})
        r.raise_for_status()
        if not r.headers.get("content-type", "").startswith("audio/"):
            raise RuntimeError(f"VoiceStudio returned {r.headers.get('content-type')}: {r.text[:200]}")
        out_path.write_bytes(r.content)
        return trim_silence(out_path)


class SilentVoice(VoicePlugin):
    """Last-resort fallback: silence timed to the script, so captions still render."""

    name = "silent"
    priority = 100
    license = "MIT (this project)"
    description = "No speech. Silence sized to the read time; captions carry the message."

    def synthesize(self, text: str, out_path: Path, request: JobRequest) -> float:
        duration = max(1.2, len(text.split()) / WORDS_PER_SECOND)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", f"{duration:.3f}", str(out_path)],
            check=True,
        )
        return duration


class ProportionalAligner(AlignPlugin):
    """Word timings spread over the clip by word length. Good enough for
    captions on clean TTS; a WhisperX aligner plugin can replace it."""

    name = "proportional"
    priority = 90
    license = "MIT (this project)"
    description = "Estimates word timings from word length (no model)."

    def align(self, text: str, audio_path: Path, duration: float) -> list[Word]:
        words = text.split()
        if not words:
            return []
        lead, tail = 0.08, 0.12
        span = max(0.1, duration - lead - tail)
        weights = [len(w.strip(".,!?;:")) + 2 for w in words]
        total = sum(weights)
        t, out = lead, []
        for w, wt in zip(words, weights):
            d = span * wt / total
            out.append(Word(text=w, start=round(t, 3), end=round(t + d, 3)))
            t += d
        return out
