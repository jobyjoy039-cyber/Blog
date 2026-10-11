"""Studio audio: voice processing, original music beds, sound effects, mastering.

Everything here is synthesised from scratch, so the music and SFX are
royalty-free and safe for paid ads (no stock-library licences to track).

- voice_chain(): broadcast voiceover processing for TTS (rumble cut, mud cut,
  presence lift, harmonic exciter to restore "air" above KittenTTS's 12 kHz
  bandwidth, de-esser, glue compression).
- compose_music(): a 4-chord progression with warm pad, bass, plucked arp and
  drums, with kick-driven "pumping" like a commercial track. Styles change
  tempo, groove and instrumentation; the seed picks key and progression.
- sfx_track(): whooshes on scene transitions, pops on headlines, a chime on
  the call to action.
- master(): mixes voice + ducked music + SFX and runs two-pass EBU R128
  loudness normalisation to -14 LUFS / -1 dBTP.
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000

STYLES = {
    "upbeat": {"bpm": 116, "kick": "four", "arp": 8, "hat": 8, "pad": 0.22, "swing": 0.0},
    "energetic": {"bpm": 126, "kick": "four", "arp": 16, "hat": 16, "pad": 0.18, "swing": 0.0},
    "chill": {"bpm": 88, "kick": "half", "arp": 4, "hat": 8, "pad": 0.3, "swing": 0.12},
    "luxury": {"bpm": 76, "kick": "none", "arp": 4, "hat": 0, "pad": 0.36, "swing": 0.0},
}

# Chord roots in semitones from the key, with chord quality. All are common
# pop/commercial progressions.
PROGRESSIONS = [
    [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")],   # I V vi IV
    [(9, "min"), (5, "maj"), (0, "maj"), (7, "maj")],   # vi IV I V
    [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")],   # I vi IV V
    [(5, "maj"), (0, "maj"), (7, "maj"), (9, "min")],   # IV I V vi
]
VOICINGS = {"maj": [0, 4, 7, 11, 14], "min": [0, 3, 7, 10, 14]}  # add7/add9 for a lush pad


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def _env(n: int, attack: float, release: float) -> np.ndarray:
    a, r = max(1, int(attack * SR)), max(1, int(release * SR))
    e = np.ones(n)
    e[: min(a, n)] = np.linspace(0, 1, min(a, n))
    if r < n:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _pad_note(freq: float, dur: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(dur)
    out = np.zeros_like(t)
    for detune in (-0.0018, 0.0, 0.0021):
        f = freq * (1 + detune)
        phase = rng.uniform(0, 2 * np.pi)
        for h in range(1, 7):  # band-limited saw-ish tone, soft highs
            out += np.sin(2 * np.pi * f * h * t + phase * h) / h ** 1.6
    return out * _env(len(t), 0.35, 0.5) / 3


def _pluck(freq: float, dur: float = 0.5) -> np.ndarray:
    t = _t(dur)
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.12 * np.sin(6 * np.pi * freq * t)
    return tone * np.exp(-t * 7) * _env(len(t), 0.003, 0.05)


def _bass(freq: float, dur: float) -> np.ndarray:
    t = _t(dur)
    tone = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t)
    return tone * np.exp(-t * 2.2) * _env(len(t), 0.005, 0.08)


def _kick() -> np.ndarray:
    t = _t(0.38)
    freq = 46 + 110 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 8.5)
    click = np.exp(-t * 400) * 0.3
    return body + click


def _snare(rng: np.random.Generator) -> np.ndarray:
    t = _t(0.22)
    noise = np.diff(rng.standard_normal(len(t) + 1)) * np.exp(-t * 24)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 35)
    return 0.45 * noise + 0.5 * tone


def _hat(rng: np.random.Generator) -> np.ndarray:
    t = _t(0.05)
    noise = np.diff(np.diff(rng.standard_normal(len(t) + 2)))
    return noise * np.exp(-t * 90) * 0.5


def _place(buf: np.ndarray, sig: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def compose_music(style: str, duration: float, out_path: Path, seed: int = 0) -> Path:
    """Write a stereo 48 kHz WAV music bed exactly `duration` seconds long."""
    cfg = STYLES.get(style, STYLES["upbeat"])
    rng = np.random.default_rng(seed)
    key = int(rng.integers(0, 12))
    prog = PROGRESSIONS[int(rng.integers(0, len(PROGRESSIONS)))]
    beat = 60.0 / cfg["bpm"]
    bar = beat * 4
    n = int((duration + 1.0) * SR)
    pad_l, pad_r, drums, bass, arp_l, arp_r = (np.zeros(n) for _ in range(6))

    t_bar, i = 0.0, 0
    while t_bar < duration + bar:
        root, quality = prog[i % len(prog)]
        base = 48 + key % 12 + root  # around C3..B3
        for k, iv in enumerate(VOICINGS[quality]):
            note = _pad_note(_hz(base + 12 + iv), bar + 0.4, rng)
            _place(pad_l if k % 2 else pad_r, note, t_bar, 1.0)
            _place(pad_r if k % 2 else pad_l, note, t_bar + 0.012, 0.6)  # Haas width
        for b in (0, 2):
            _place(bass, _bass(_hz(base - 12), beat * 2), t_bar + b * beat)
        steps = cfg["arp"]
        if steps:
            notes = [base + 24 + VOICINGS[quality][j % 3] for j in range(steps)]
            for s, note in enumerate(notes):
                swing = cfg["swing"] * (bar / steps) if s % 2 else 0.0
                target = arp_l if s % 2 else arp_r
                _place(target, _pluck(_hz(note)), t_bar + s * bar / steps + swing, rng.uniform(0.75, 1.0))
        for b in range(4):
            at = t_bar + b * beat
            if cfg["kick"] == "four" or (cfg["kick"] == "half" and b in (0, 2)):
                _place(drums, _kick(), at, 0.9)
            if cfg["kick"] != "none" and b in (1, 3):
                _place(drums, _snare(rng), at, 0.55)
        if cfg["hat"]:
            for h in range(cfg["hat"]):
                swing = cfg["swing"] * (bar / cfg["hat"]) if h % 2 else 0.0
                _place(drums, _hat(rng), t_bar + h * bar / cfg["hat"] + swing, 0.5 if h % 2 else 0.3)
        t_bar += bar
        i += 1

    # Kick-driven pump on the pad and arp, the signature "commercial" groove.
    tt = np.arange(n) / SR
    pump = 1 - 0.38 * np.exp(-((tt % beat) / beat) * 7) if cfg["kick"] != "none" else np.ones(n)
    pad_gain, arp_gain = cfg["pad"], 0.16
    left = (pad_l * pad_gain + arp_l * arp_gain) * pump + bass * 0.32 + drums * 0.42
    right = (pad_r * pad_gain + arp_r * arp_gain) * pump + bass * 0.32 + drums * 0.42
    mix = np.stack([left, right], axis=1)[: int(duration * SR)]
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)  # gentle saturation / glue
    fade = min(len(mix), int(1.5 * SR))
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 1.5
    mix[: int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR))[:, None]
    peak = np.max(np.abs(mix)) or 1.0
    write_wav(out_path, mix / peak * 0.5)
    return out_path


def _whoosh(rng: np.random.Generator, dur: float = 0.5) -> np.ndarray:
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    x = np.linspace(0, 1, n)
    cutoff = 300 + 5200 * np.sin(np.pi * x) ** 2  # sweep up then down
    alpha = 1 - np.exp(-2 * np.pi * cutoff / SR)
    out = np.empty(n)
    y = 0.0
    for k in range(n):  # time-varying one-pole low-pass
        y += alpha[k] * (noise[k] - y)
        out[k] = y
    return out * np.sin(np.pi * x) ** 2 * 1.6


def _pop() -> np.ndarray:
    t = _t(0.09)
    freq = 900 * np.exp(-t * 18) + 280
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 45)


def _chime() -> np.ndarray:
    t = _t(1.6)
    out = np.zeros_like(t)
    for f, a in ((1318.5, 1.0), (1975.5, 0.6), (2637.0, 0.25)):  # E6, B6, E7
        out += a * np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2)
    return out * _env(len(t), 0.002, 0.2) * 0.5


def sfx_track(duration: float, transitions: list[float], pops: list[float], chime_at: float | None,
              out_path: Path, seed: int = 0) -> Path:
    rng = np.random.default_rng(seed + 7)
    n = int(duration * SR)
    left, right = np.zeros(n), np.zeros(n)
    for i, t in enumerate(transitions):
        w = _whoosh(rng)
        pan = 0.35 if i % 2 else -0.35  # alternate sides with the slide direction
        _place(left, w, t - 0.25, 0.38 * (1 - pan))
        _place(right, w, t - 0.25, 0.38 * (1 + pan))
    for t in pops:
        p = _pop()
        _place(left, p, t, 0.25)
        _place(right, p, t, 0.25)
    if chime_at is not None:
        c = _chime()
        _place(left, c, chime_at, 0.35)
        _place(right, c, chime_at + 0.008, 0.35)
    mix = np.stack([left, right], axis=1)
    write_wav(out_path, np.clip(mix, -0.95, 0.95))
    return out_path


def write_wav(path: Path, data: np.ndarray) -> None:
    data = np.atleast_2d(data.T).T if data.ndim == 1 else data
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def voice_chain() -> str:
    """FFmpeg filter chain that makes TTS sound like a treated studio VO."""
    return ",".join([
        "aresample=48000",
        "highpass=f=85",                               # rumble
        "equalizer=f=280:t=q:w=1.1:g=-2.5",            # boxiness / mud
        "equalizer=f=3300:t=q:w=1.3:g=2.5",            # presence, intelligibility on phone speakers
        "aexciter=amount=2:drive=7:freq=5500:blend=0", # synthesize air above the TTS bandwidth
        "equalizer=f=11000:t=h:w=0.7:g=2",             # gentle air shelf
        "deesser=i=0.35",
        "acompressor=threshold=-21dB:ratio=3:attack=6:release=70:makeup=3",
    ])


def _ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio failed: {proc.stderr[-1200:]}")
    return proc


def master(voice_clips: list[tuple[str, float]], duration: float, out_path: Path,
           music: str | None = None, sfx: str | None = None, target_lufs: float = -14.0) -> Path:
    """Mix voice clips (path, start time) over ducked music + SFX, then
    two-pass loudness-normalise. Returns a 48 kHz stereo WAV."""
    inputs: list[str] = []
    filters: list[str] = []
    for i, (path, start) in enumerate(voice_clips):
        inputs += ["-i", str(path)]
        ms = int(start * 1000)
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}|{ms}[v{i}]")
    n = len(voice_clips)
    filters.append("".join(f"[v{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:duration=longest,"
                   f"apad=whole_dur={duration:.3f},atrim=0:{duration:.3f},{voice_chain()},"
                   "aformat=channel_layouts=stereo[voice]")
    bus = ["[voice]"]
    if music:
        m = n
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        filters += [
            "[voice]asplit=2[vout][vkey]",
            f"[{m}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{duration:.3f},"
            "equalizer=f=2800:t=q:w=1.5:g=-4,volume=0.55[mus]",   # carve space for the voice
            "[mus][vkey]sidechaincompress=threshold=0.04:ratio=7:attack=12:release=380:makeup=1[ducked]",
        ]
        bus = ["[vout]", "[ducked]"]
    if sfx:
        s = n + (1 if music else 0)
        inputs += ["-i", str(sfx)]
        filters.append(f"[{s}:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.8[fx]")
        bus.append("[fx]")
    filters.append("".join(bus) + f"amix=inputs={len(bus)}:normalize=0:duration=first,"
                   f"atrim=0:{duration:.3f}[mix]")

    premix = out_path.with_name(out_path.stem + "_premix.wav")
    _ffmpeg([*inputs, "-filter_complex", ";".join(filters), "-map", "[mix]", "-ar", "48000", "-c:a", "pcm_s24le", str(premix)])

    # Two-pass loudnorm: measure, then apply linearly so the target is hit exactly.
    probe = _ffmpeg(["-i", str(premix), "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"])
    stats = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", probe.stderr)[-1])
    ln = (f"loudnorm=I={target_lufs}:TP=-1.5:LRA=9:linear=true:"
          f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
          f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:offset={stats['target_offset']}")
    _ffmpeg(["-i", str(premix), "-af", f"{ln},alimiter=limit=0.82:level=false,aresample=48000",
             "-c:a", "pcm_s16le", str(out_path)])
    premix.unlink(missing_ok=True)
    return out_path
