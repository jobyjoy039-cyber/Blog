"""Cinematic motion poster: camera moves across a still poster, fog, flicker,
grain, vignette, flash cuts and a synthesized suspense score.

usage: python motion_poster.py POSTER OUT.mp4 [16x9|9x16]
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ugc_studio.plugins.audio_studio import SR, write_wav  # noqa: E402

FPS = 30
TOTAL = 22.0
UP = 4  # upscale factor of the source

# (start, end, from(cx, cy, crop_w), to(cx, cy, crop_w)) in source pixels
SHOTS_WIDE = [
    (0.0, 4.5, (350, 197, 700), (305, 205, 380)),    # full poster -> his face
    (4.5, 8.0, (525, 235, 300), (530, 225, 240)),    # her
    (8.0, 11.5, (90, 230, 270), (125, 245, 230)),    # man and boy
    (11.5, 14.0, (230, 70, 300), (235, 95, 250)),    # crow, branches
    (14.0, 16.5, (640, 140, 200), (625, 160, 170)),  # lighthouse
    (17.1, TOTAL, (500, 280, 300), (350, 197, 700)), # title -> full poster
]
SHOTS_TALL = [
    (0.0, 4.5, (330, 197, 222), (300, 205, 180)),
    (4.5, 8.0, (520, 225, 200), (520, 215, 170)),
    (8.0, 11.5, (75, 235, 200), (110, 245, 175)),
    (11.5, 14.0, (190, 120, 222), (215, 150, 190)),
    (14.0, 16.5, (635, 160, 140), (630, 175, 120)),
    (17.1, TOTAL, (500, 260, 200), (430, 197, 222)),
]
CUTS = [4.5, 8.0, 11.5, 14.0]
REVEAL = 17.1


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def prepare(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:  # webp via ffmpeg fallback
        png = Path(path).with_suffix(".png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, str(png)], check=True)
        img = cv2.imread(str(png))
    big = cv2.resize(img, None, fx=UP, fy=UP, interpolation=cv2.INTER_LANCZOS4)
    soft = cv2.GaussianBlur(big, (0, 0), 2.2)
    big = cv2.addWeighted(big, 1.6, soft, -0.6, 0)  # unsharp: recover edges after upscaling
    # grade: deeper blacks, a touch more contrast
    lut = np.clip(((np.arange(256) / 255) ** 1.12) * 255 * 1.04 - 4, 0, 255).astype(np.uint8)
    return cv2.LUT(big, lut)


def fog_texture(w, h, rng):
    small = rng.random((max(4, h // 90), max(8, (w * 2) // 90))).astype(np.float32)
    fog = cv2.resize(small, (w * 2, h), interpolation=cv2.INTER_CUBIC)
    fog = cv2.GaussianBlur(fog, (0, 0), w / 30)
    fog = (fog - fog.min()) / (np.ptp(fog) + 1e-6)
    return fog


def render(poster, out, mode):
    w, h = (1920, 1080) if mode == "16x9" else (1080, 1920)
    shots = SHOTS_WIDE if mode == "16x9" else SHOTS_TALL
    src = prepare(poster)
    sh, sw = src.shape[:2]
    rng = np.random.default_rng(13)
    fog = fog_texture(w, h, rng)
    grains = [rng.normal(0, 7, (h, w, 1)).astype(np.float32) for _ in range(6)]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vignette = np.clip(1.15 - 0.55 * r ** 1.8, 0.25, 1.0)[..., None].astype(np.float32)
    teal = np.array([150, 160, 120], np.float32)  # BGR fog tint
    flicker_events = sorted(rng.uniform(1, TOTAL - 2, 9))
    # vertical finale: the whole poster across the frame over a blurred, darkened copy of itself
    fill = None
    if mode != "16x9":
        s_cover = max(w / sw, h / sh)
        cover = cv2.resize(src, (int(sw * s_cover) + 1, int(sh * s_cover) + 1), interpolation=cv2.INTER_AREA)
        x0, y0 = (cover.shape[1] - w) // 2, (cover.shape[0] - h) // 2
        fill = (cv2.GaussianBlur(cover[y0:y0 + h, x0:x0 + w], (0, 0), 40).astype(np.float32) * 0.45)

    audio = out.with_suffix(".wav")
    make_score(audio)
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(FPS),
         "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-shortest",
         "-c:v", "libx264", "-preset", "slow", "-tune", "grain", "-b:v", "6M", "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE,
    )
    for n in range(int(TOTAL * FPS)):
        t = n / FPS
        shot = next((s for s in shots if s[0] <= t < s[1]), None)
        if shot is None:  # the beat of black before the reveal
            frame = np.zeros((h, w, 3), np.float32)
        elif fill is not None and shot is shots[-1]:
            p = ease((t - shot[0]) / (shot[1] - shot[0]))
            scale = (w * (1.12 - 0.08 * p)) / sw  # poster slightly wider than the frame, settling in
            m = np.float32([[scale, 0, w / 2 - scale * sw / 2], [0, scale, h * 0.47 - scale * sh / 2]])
            poster_layer = cv2.warpAffine(src, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                                          borderValue=(0, 0, 0))
            mask = cv2.warpAffine(np.full((sh, sw), 255, np.uint8), m, (w, h), flags=cv2.INTER_LINEAR)[..., None] / 255.0
            frame = fill * (1 - mask) + poster_layer.astype(np.float32) * mask
            frame *= vignette
        else:
            s0, s1, a, b = shot
            p = ease((t - s0) / (s1 - s0))
            cx, cy, cw = (a[i] + (b[i] - a[i]) * p for i in range(3))
            scale = w / (cw * UP)
            m = np.float32([[scale, 0, w / 2 - scale * cx * UP], [0, scale, h / 2 - scale * cy * UP]])
            frame = cv2.warpAffine(src, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
            # drifting fog (screen blend)
            off = int((t * w * 0.03) % w)
            f = fog[:, off: off + w][..., None] * 0.16
            frame = 255 - (255 - frame) * (1 - f * teal / 255 * 1.4)
            # flickering light
            flick = sum(math.exp(-((t - e) / 0.05) ** 2) for e in flicker_events)
            frame *= 1 - 0.35 * min(1.0, flick)
            frame *= vignette
        # fades and flash cuts
        if t < 1.2:
            frame *= ease(t / 1.2)
        for c in CUTS + [REVEAL]:
            d = t - c
            if 0 <= d < 0.1:
                frame = frame + (255 - frame) * (0.85 * (1 - d / 0.1))
        if t > TOTAL - 1.2:
            frame *= ease((TOTAL - t) / 1.2)
        frame += grains[n % len(grains)]
        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    audio.unlink(missing_ok=True)


# ---------------------------------------------------------------- score
def _t(d):
    return np.arange(int(d * SR)) / SR


def _place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i] * gain


def _reverb(x, seconds=2.6, rng=None):
    rng = rng or np.random.default_rng(0)
    ir = rng.standard_normal(int(seconds * SR)) * np.exp(-_t(seconds) * 3.0)
    ir[0] = 0
    n = len(x) + len(ir)
    size = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return y / (np.max(np.abs(y)) + 1e-9)


def _boom(dur=2.2, big=1.0):
    t = _t(dur)
    f = 32 + 70 * np.exp(-t * 6)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.8)
    brass = np.tanh(3 * sum(np.sin(2 * np.pi * 55 * k * t) / k for k in range(1, 9))) * np.exp(-t * 2.2) * 0.35
    noise = np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t * 14) * 0.25
    return (sub + brass * big + noise) * min(1, big)


def _heartbeat():
    t = _t(0.5)
    thump = lambda d: np.sin(2 * np.pi * 52 * _t(d)) * np.exp(-_t(d) * 18)  # noqa: E731
    out = np.zeros(len(t))
    _place(out, thump(0.25), 0.0, 1.0)
    _place(out, thump(0.25), 0.17, 0.7)
    return out


def make_score(path):
    rng = np.random.default_rng(5)
    n = int(TOTAL * SR)
    t = np.arange(n) / SR
    L, R = np.zeros(n), np.zeros(n)
    # drone: low cluster with a dissonant minor second, breathing slowly
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t)
    drone = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f, a in
                ((55, 1.0), (82.4, 0.6), (87.3, 0.45), (110, 0.3), (164.8, 0.12)))
    drone = drone * lfo * np.clip(t / 2.5, 0, 1)
    # wind: noise through a slowly sweeping low-pass
    noise = rng.standard_normal(n)
    cut = 250 + 500 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t))
    alpha = 1 - np.exp(-2 * np.pi * cut / SR)
    wind = np.empty(n)
    y = 0.0
    for k in range(0, n):
        y += alpha[k] * (noise[k] - y)
        wind[k] = y
    wind /= np.max(np.abs(wind)) + 1e-9
    L += drone * 0.18 + wind * 0.10
    R += drone * 0.18 + np.roll(wind, 900) * 0.10
    # sparse music-box notes in a minor key, drenched in reverb
    bells = np.zeros(n)
    for at, midi in ((1.8, 76), (3.4, 72), (5.2, 75), (7.1, 71), (9.6, 76), (12.2, 74), (13.4, 72)):
        f = 440 * 2 ** ((midi - 69) / 12)
        bt = _t(1.4)
        _place(bells, (np.sin(2 * np.pi * f * bt) + 0.3 * np.sin(2 * np.pi * 2.01 * f * bt)) * np.exp(-bt * 4), at, 0.5)
    wet = _reverb(bells, rng=rng)
    L += bells * 0.06 + wet * 0.07
    R += bells * 0.06 + np.roll(wet, 600) * 0.07
    # heartbeat that quickens toward the reveal
    beat_t = 4.6
    while beat_t < 15.8:
        hb = _heartbeat()
        _place(L, hb, beat_t, 0.5)
        _place(R, hb, beat_t, 0.5)
        beat_t += 1.15 - 0.4 * (beat_t - 4.6) / 11.2
    # impacts on every cut, biggest on the reveal
    for c in CUTS:
        b = _boom(2.0, 0.8)
        _place(L, b, c, 0.55)
        _place(R, b, c, 0.55)
    # riser into silence, then the reveal hit
    rt = _t(1.3)
    riser = rng.standard_normal(len(rt)) * (rt / 1.3) ** 2.5 * 0.5
    riser += np.sin(2 * np.pi * np.cumsum(200 + 1100 * (rt / 1.3) ** 2) / SR) * (rt / 1.3) ** 2 * 0.3
    _place(L, riser, 15.5, 0.7)
    _place(R, riser, 15.5, 0.7)
    gate = np.ones(n)
    gate[int(16.8 * SR): int(REVEAL * SR)] = 0.0  # dead air right before the hit
    L, R = L * gate, R * gate
    big = _boom(4.5, 1.3)
    _place(L, big, REVEAL, 0.8)
    _place(R, big, REVEAL, 0.8)
    fade = int(1.4 * SR)
    mix = np.stack([L, R], axis=1)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    mix = np.tanh(mix * 1.2)
    raw = path.with_name(path.stem + "_raw.wav")
    write_wav(raw, mix / (np.max(np.abs(mix)) + 1e-9) * 0.8)
    # two-pass loudness normalisation to -14 LUFS / -1.5 dBTP
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    st = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", probe)[-1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
          f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"{ln},alimiter=limit=0.82:level=false,aresample=48000",
                    str(path)], check=True)
    raw.unlink()


if __name__ == "__main__":
    render(sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "16x9")
