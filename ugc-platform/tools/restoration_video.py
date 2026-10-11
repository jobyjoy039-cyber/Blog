""""Barn find to showroom" restoration video: renderer + assembler.

Scenes 1-2 are built from the real photo (push-in, dust, light rays, macro
close-ups with rack focus and handheld shake). Scenes 3-9 need AI-generated
footage: drop clips named scene3.mp4 ... scene9.mp4 into CLIPS_DIR and they
replace the storyboard cards, graded and cut to the same soundtrack.

usage: python restoration_video.py PHOTO OUT.mp4 [CLIPS_DIR]
"""
import json
import math
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ugc_studio.plugins.audio_studio import SR, write_wav  # noqa: E402

W, H, FPS = 1920, 1080, 24
BAR = 138  # 2.39:1 letterbox
UP = 2
ACCENT = (64, 160, 255)  # BGR warm orange

SCENES = [  # (start, end, title, beats, prompt)
    (0, 5, "The Forgotten Machine", "", ""),
    (5, 12, "Damage Inspection", "", ""),
    (12, 22, "Complete Disassembly", "Wheels · Engine · Swingarm · Suspension · Handlebar",
     "Motorcycle automatically disassembles in mid air, every component floating separately, exploded technical view, cinematic lighting, photorealistic mechanical animation, black background."),
    (22, 32, "Cleaning", "Pressure wash → Degrease → Rust removal → Sand blast → Polish",
     "Time-lapse motorcycle restoration, pressure washing removes mud, rust dissolves, metal becomes shiny, satisfying transformation, cinematic close-ups, ultra realistic."),
    (32, 45, "Engine Rebuild", "Pistons · Valves · Clutch · Bearings · Gearbox",
     "Exploded motorcycle engine assembling itself, pistons, crankshaft, valves, bearings moving into place, technical cinematic animation, ultra detailed, mechanical precision."),
    (45, 55, "Painting", "Old frame → Primer → Gloss black → Clear coat",
     "Motorcycle frame suspended in paint booth, glossy black paint sprayed in slow motion, metallic reflections, cinematic lighting, ultra realistic, 4K."),
    (55, 70, "Reassembly", "Engine · Frame · Tank · Seat · Wheels · Lights · Fairings",
     "Motorcycle parts flying together in perfect synchronization, cinematic assembly animation, photorealistic, smooth transitions, dramatic lighting."),
    (70, 80, "First Start", "Ignition → Fuel pump → Starter → Engine fires → Exhaust smoke",
     "Close-up motorcycle ignition, dashboard lights illuminate, engine cranks then starts successfully, exhaust smoke, realistic engine vibration, cinematic sound design."),
    (80, 90, "Beauty Reveal", "Golden hour · 360° orbit · Headlight on",
     "Fully restored motorcycle at golden hour, glossy paint, cinematic orbit camera, shallow depth of field, lens flare, ultra realistic 8K, premium commercial advertisement."),
]
TOTAL = 90.0
MACROS = [  # (cx, cy, crop width) in photo pixels: engine, wiring, frame, suspension, exhaust
    (840, 395, 210), (750, 290, 260), (660, 425, 240), (560, 480, 160), (515, 610, 330),
]
PLATES = [(180, 372, 280, 498), (572, 78, 636, 132)]  # licence plates to blur
TEXTS = [  # (start, end, text, size)
    (1.0, 4.7, "Every legend begins with a forgotten story...", 0.042),
    (5.6, 11.6, "Years of neglect...", 0.05),
    (84.5, 89.4, "From Scrap to Showroom.", 0.075),
]


def font(size, weight="Light"):
    for q in (f"Inter:style={weight}", "Inter", "DejaVu Sans"):
        out = subprocess.run(["fc-match", "-f", "%{file}", q], capture_output=True, text=True).stdout
        if out and Path(out).exists():
            return ImageFont.truetype(out, size)
    return ImageFont.load_default()


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def grade(img):
    """Teal & orange: cool shadows, warm highlights, gentle S-curve."""
    f = img.astype(np.float32) / 255
    lum = f.mean(axis=2, keepdims=True)
    f += (1 - lum) ** 2 * np.array([0.07, 0.035, -0.04], np.float32)   # BGR: teal shadows
    f += lum ** 2 * np.array([-0.06, 0.005, 0.07], np.float32)          # orange highlights
    f = np.clip(f, 0, 1)
    f = f * f * (3 - 2 * f) * 0.35 + f * 0.65                          # S-curve
    gray = f.mean(axis=2, keepdims=True)
    f = gray + (f - gray) * 1.12
    return np.clip(f * 255, 0, 255).astype(np.uint8)


def prepare_photo(path):
    img = cv2.imread(path)
    for x0, y0, x1, y1 in PLATES:  # privacy: plates unreadable
        roi = img[y0:y1, x0:x1]
        small = cv2.resize(roi, (max(1, roi.shape[1] // 12), max(1, roi.shape[0] // 12)), interpolation=cv2.INTER_AREA)
        img[y0:y1, x0:x1] = cv2.GaussianBlur(cv2.resize(small, roi.shape[1::-1], interpolation=cv2.INTER_NEAREST), (0, 0), 6)
    big = cv2.resize(img, None, fx=UP, fy=UP, interpolation=cv2.INTER_LANCZOS4)
    big = cv2.addWeighted(big, 1.5, cv2.GaussianBlur(big, (0, 0), 2.0), -0.5, 0)
    return grade(big)


def view(src, cx, cy, cw, shake=(0.0, 0.0)):
    scale = W / (cw * UP)
    m = np.float32([[scale, 0, W / 2 - scale * cx * UP + shake[0]], [0, scale, H / 2 - scale * cy * UP + shake[1]]])
    return cv2.warpAffine(src, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


class Dust:
    def __init__(self, rng, n=140):
        self.p = np.column_stack([rng.uniform(0, W, n), rng.uniform(0, H, n)])
        self.v = rng.normal(0, 1, (n, 2)) * [6, 3] + [5, -2]
        self.size = rng.choice([1, 1, 2, 2, 3, 6, 10, 16], n)
        self.phase = rng.uniform(0, 6.28, n)

    def draw(self, t, strength=1.0):
        layer = np.zeros((H, W), np.float32)
        pos = (self.p + self.v * t + 12 * np.sin(t * 0.7 + self.phase)[:, None]) % [W, H]
        for (x, y), s, ph in zip(pos, self.size, self.phase):
            a = (0.5 + 0.5 * math.sin(t * 2.3 + ph)) * (0.35 if s > 5 else 1.0)
            cv2.circle(layer, (int(x), int(y)), int(s), a, -1, cv2.LINE_AA)
        return cv2.GaussianBlur(layer, (0, 0), 2.2)[..., None] * strength


def light_rays(rng):
    stripes = cv2.resize(rng.random((1, 60)).astype(np.float32), (W * 2, 1), interpolation=cv2.INTER_CUBIC)
    rays = np.repeat(stripes, H * 2, axis=0)
    rays = cv2.warpAffine(rays, cv2.getRotationMatrix2D((W, H), -28, 1.0), (W * 2, H * 2))
    rays = cv2.GaussianBlur(rays, (0, 0), 18)
    fall = np.linspace(1, 0.15, H * 2, dtype=np.float32)[:, None]
    return np.clip(rays * fall, 0, 1)


def text_layer(text, size_frac, weight="Light"):
    f = font(int(H * size_frac), weight)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    tw = int(d.textlength(text, font=f))
    img = Image.new("L", (tw + 40, int(H * size_frac * 1.6)), 0)
    ImageDraw.Draw(img).text((20, 0), text, font=f, fill=255)
    return np.asarray(img, np.float32) / 255


def card(scene_idx, src):
    s0, s1, title, beats, prompt = SCENES[scene_idx]
    bg = cv2.GaussianBlur(view(src, 768, 470, 1500), (0, 0), 24).astype(np.float32) * 0.32
    img = Image.fromarray(cv2.cvtColor(bg.astype(np.uint8), cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(img)
    x = int(W * 0.1)
    d.text((x, BAR + 70), f"SCENE {scene_idx + 1:02d}   ·   {s0}–{s1}s", font=font(30, "SemiBold"), fill=(255, 160, 64))
    d.text((x, BAR + 120), title, font=font(92, "Bold"), fill="white")
    d.text((x, BAR + 245), beats, font=font(36, "Regular"), fill=(220, 220, 220))
    d.text((x, BAR + 330), "AI SHOT  ·  generate in Kling / Veo / Runway, save as scene%d.mp4" % (scene_idx + 1),
           font=font(26, "SemiBold"), fill=(255, 160, 64))
    y = BAR + 375
    for line in textwrap.wrap(prompt, 88):
        d.text((x, y), line, font=font(28, "Regular"), fill=(190, 200, 205))
        y += 40
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR).astype(np.float32)


def clip_reader(clips_dir, idx):
    if not clips_dir:
        return None
    p = Path(clips_dir) / f"scene{idx + 1}.mp4"
    return cv2.VideoCapture(str(p)) if p.exists() else None


def clip_frame(cap, local_t, dur):
    """Fit the clip's length to the scene (speed-ramped), cover-crop, grade."""
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    idx = min(n - 1, int(local_t / dur * n))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    if not ok:
        return np.zeros((H, W, 3), np.float32)
    s = max(W / fr.shape[1], H / fr.shape[0])
    fr = cv2.resize(fr, (int(fr.shape[1] * s + 1), int(fr.shape[0] * s + 1)), interpolation=cv2.INTER_CUBIC)
    y0, x0 = (fr.shape[0] - H) // 2, (fr.shape[1] - W) // 2
    return grade(fr[y0:y0 + H, x0:x0 + W]).astype(np.float32)


def render(photo, out, clips_dir=None):
    rng = np.random.default_rng(21)
    src = prepare_photo(photo)
    dust, rays = Dust(rng), light_rays(rng)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vignette = np.clip(1.12 - 0.5 * r ** 2, 0.3, 1)[..., None]
    dof = np.clip((r - 0.45) / 0.6, 0, 1)[..., None]  # edge blur weight for macro shots
    grains = [rng.normal(0, 5, (H, W, 1)).astype(np.float32) for _ in range(5)]
    texts = [(a, b, text_layer(txt, sz, "Medium" if sz < 0.07 else "Bold")) for a, b, txt, sz in TEXTS]
    cards = {i: card(i, src) for i in range(2, len(SCENES))}
    caps = {i: clip_reader(clips_dir, i) for i in range(2, len(SCENES))}
    warm = np.array([120, 200, 255], np.float32)

    audio = out.with_suffix(".wav")
    make_score(audio)
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-shortest",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "22", "-maxrate", "6M", "-bufsize", "12M",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE,
    )
    for n in range(int(TOTAL * FPS)):
        t = n / FPS
        si = next(i for i, s in enumerate(SCENES) if s[0] <= t < s[1])
        s0, s1 = SCENES[si][:2]
        local = t - s0
        if si == 0:  # wide push-in through dusty morning light
            p = ease(local / 5)
            frame = view(src, 700 - 40 * p, 470, 1536 - 300 * p).astype(np.float32)
            off = int(local * 14)
            ray = rays[H // 2 + off // 3: H // 2 + off // 3 + H, W // 2 - off: W // 2 - off + W][..., None]
            frame = 255 - (255 - frame) * (1 - ray * 0.33 * warm / 255)
            frame += dust.draw(t) * 210
        elif si == 1:  # macro inspection: rack focus, handheld, whip between shots
            k = min(4, int(local / 1.4))
            lt = local - k * 1.4
            cx, cy, cw = MACROS[k]
            shake = (14 * math.sin(t * 3.1) + 7 * math.sin(t * 7.3), 9 * math.sin(t * 2.3 + 1) + 5 * math.sin(t * 6.1))
            frame = view(src, cx, cy, cw / (1 + 0.08 * ease(lt / 1.4)), shake).astype(np.float32)
            focus = max(0.0, 1 - lt / 0.35) * 7  # rack focus at the start of each shot
            blurred = cv2.GaussianBlur(frame, (0, 0), 6 + focus)
            frame = frame * (1 - dof) + blurred * dof
            if focus > 0.2:
                frame = cv2.GaussianBlur(frame, (0, 0), focus)
            if lt > 1.28 and k < 4:  # whip pan into the next close-up
                frame = cv2.blur(frame, (int(40 + (lt - 1.28) * 900), 1))
            frame += dust.draw(t, 0.5) * 150
        else:
            cap = caps.get(si)
            if cap is not None:
                frame = clip_frame(cap, local, s1 - s0)
            else:
                z = 1 + 0.03 * ease(local / (s1 - s0))
                c = cards[si]
                m = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]])
                frame = cv2.warpAffine(c, m, (W, H), borderMode=cv2.BORDER_REFLECT)
        # flash on every scene change (welding-flash style)
        for c0 in [s[0] for s in SCENES[1:]]:
            d = t - c0
            if 0 <= d < 0.12:
                frame = frame + (np.float32([200, 230, 255]) - frame) * (0.8 * (1 - d / 0.12))
        frame *= vignette
        for a, b, layer in texts:  # titles: fade + rise, centred in the picture area
            if a <= t < b:
                alpha = min(ease((t - a) / 0.8), ease((b - t) / 0.6))
                lh, lw = layer.shape
                x0 = (W - lw) // 2
                final = lh >= 120
                y0 = int((H * 0.62 if final else H - BAR - lh - 64) + 18 * (1 - alpha))
                # soft dark band behind the words so they read over bright sand or chrome
                band = np.exp(-(((np.arange(H) - (y0 + lh / 2)) / (lh * 1.1)) ** 2)).astype(np.float32)[:, None, None]
                frame *= 1 - 0.55 * band * alpha
                region = frame[y0:y0 + lh, x0:x0 + lw]
                shadow = cv2.GaussianBlur(layer, (0, 0), 5)[..., None] * 0.7 * alpha
                region[:] = region * (1 - shadow)
                region[:] = region + (255 - region) * layer[..., None] * alpha
        if t < 0.8:
            frame *= ease(t / 0.8)
        if t > TOTAL - 1.0:
            frame *= ease((TOTAL - t) / 1.0)
        frame += grains[n % len(grains)]
        frame[:BAR] = 0
        frame[H - BAR:] = 0
        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    audio.unlink(missing_ok=True)


# ------------------------------------------------------------------ score
def _t(d):
    return np.arange(int(d * SR)) / SR


def _place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if 0 <= i < len(buf):
        buf[i:j] += sig[: j - i] * gain


def _lowpass(x, hz):
    a = 1 - math.exp(-2 * math.pi * hz / SR)
    y = np.empty_like(x)
    acc = 0.0
    for k in range(len(x)):
        acc += a * (x[k] - acc)
        y[k] = acc
    return y


def _hit(dur=2.5, power=1.0):
    t = _t(dur)
    sub = np.sin(2 * np.pi * np.cumsum(34 + 80 * np.exp(-t * 7)) / SR) * np.exp(-t * 1.7)
    body = np.random.default_rng(3).standard_normal(len(t)) * np.exp(-t * 18) * 0.4
    return (sub + body) * power


def _clank(rng):
    t = _t(0.6)
    out = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in
              ((rng.uniform(900, 1400), 9), (rng.uniform(2300, 3100), 14), (rng.uniform(4100, 5200), 20)))
    return out * 0.5 + rng.standard_normal(len(t)) * np.exp(-t * 80) * 0.4


def _noise_bed(rng, dur, hz):
    return _lowpass(rng.standard_normal(int(dur * SR)), hz)


def _pad(freqs, dur, attack=1.5):
    t = _t(dur)
    sig = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) for f in freqs)
    env = np.minimum(1, t / attack) * np.minimum(1, (dur - t) / 1.2)
    return sig * env / len(freqs)


def _engine(dur, rate_fn, rng):
    """Single-cylinder bike: firing pulses through a resonant exhaust."""
    n = int(dur * SR)
    out = np.zeros(n)
    t = 0.0
    pulse_t = _t(0.06)
    pulse = (np.sin(2 * np.pi * 95 * pulse_t) + 0.5 * rng.standard_normal(len(pulse_t))) * np.exp(-pulse_t * 55)
    while t < dur:
        _place(out, pulse * rng.uniform(0.8, 1.1), t)
        t += 1 / rate_fn(t)
    return np.tanh(_lowpass(out, 1100) * 3)


def make_score(path):
    rng = np.random.default_rng(9)
    n = int(TOTAL * SR)
    L, R = np.zeros(n), np.zeros(n)

    def both(sig, at, g=1.0, width=0):
        _place(L, sig, at, g)
        _place(R, sig, at + width / SR, g)

    a_minor = [55, 82.4, 110, 130.8]
    both(_pad(a_minor, 12.5, 3.0), 0, 0.22)
    both(_noise_bed(rng, 12, 400), 0, 0.15, 700)                    # wind
    for k in range(24):                                              # ticking clock
        both(_clank(rng)[: int(0.03 * SR)], 0.5 + k * 0.5, 0.08)
    for c in (5.0, 6.4, 7.8, 9.2, 10.6):
        both(_hit(1.2, 0.5), c, 0.5)
    # build: ostinato pulse from 12s, getting denser; taiko from 32s
    bpm, beat = 92, 60 / 92
    t = 12.0
    while t < 70:
        step = beat / (2 if t < 32 else 4)
        tone = np.sin(2 * np.pi * 110 * _t(0.12)) * np.exp(-_t(0.12) * 30)
        both(np.tanh(tone * 3), t, 0.18 + 0.12 * (t - 12) / 58)
        t += step
    t = 32.0
    while t < 70:
        both(_hit(0.8, 0.6), t, 0.5)
        t += beat * 2
    both(_pad([55, 65.4, 82.4, 110], 58, 4), 12, 0.2)                 # strings bed
    for k, at in enumerate((13, 15, 17, 19, 21)):                     # disassembly: parts flying off
        both(_clank(rng), at, 0.35, 300 * (1 if k % 2 else -1))
    both(_noise_bed(rng, 4, 5000) * 0.6, 22, 0.25)                    # pressure wash
    both(_noise_bed(rng, 2, 2500), 28, 0.2)                           # sand blast
    for k in range(18):                                               # ratchets / wrenches
        both(_clank(rng)[: int(0.08 * SR)], 32.3 + k * 0.7, 0.2)
    for at in (46, 48.5, 51, 53.5):                                   # spray gun
        both(_noise_bed(rng, 1.6, 7000), at, 0.18)
    for k in range(14):
        both(_clank(rng), 55.5 + k, 0.28)
    rt = _t(4)                                                         # riser into the first start
    both(rng.standard_normal(len(rt)) * (rt / 4) ** 3 * 0.4, 66, 0.6)
    gate = np.ones(n)
    gate[int(70 * SR): int(80 * SR)] = 0.12                            # music drops for the first start
    L *= gate
    R *= gate
    both(_clank(rng)[: int(0.05 * SR)], 70.6, 0.5)                     # ignition click
    chime = np.sin(2 * np.pi * 1760 * _t(0.25)) * np.exp(-_t(0.25) * 12)
    both(chime, 71.1, 0.2)                                             # dash lights
    ft = _t(1.6)
    both(np.sin(2 * np.pi * np.cumsum(300 + 120 * ft / 1.6) / SR) * 0.15 * np.minimum(1, (1.6 - ft) * 4), 72, 0.6)  # fuel pump
    crank = _engine(2.0, lambda x: 6.0, rng) * 0.6                       # starter cranking
    both(crank, 74, 0.7)
    eng = _engine(14, lambda x: 11 + 30 * math.exp(-((x - 2.2) / 0.6) ** 2) + 4 * math.exp(-x), rng)  # fires, blips, idles
    eng *= np.minimum(1, _t(14) / 0.05)
    eng[-int(2 * SR):] *= np.linspace(1, 0, int(2 * SR))
    both(eng, 76, 0.75, 400)
    both(_hit(4, 1.3), 80, 0.8)                                       # reveal
    both(_pad([110, 138.6, 164.8, 220, 277.2], 10, 1.0), 80, 0.3)     # A major, triumphant
    mix = np.tanh(np.stack([L, R], axis=1) * 1.1)
    raw = path.with_name(path.stem + "_raw.wav")
    write_wav(raw, mix / (np.max(np.abs(mix)) + 1e-9) * 0.8)
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    st = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", probe)[-1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
          f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"{ln},alimiter=limit=0.82:level=false",
                    str(path)], check=True)
    raw.unlink()


if __name__ == "__main__":
    render(sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
