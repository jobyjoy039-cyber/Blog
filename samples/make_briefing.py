"""10-second 'voice assistant morning briefing' video, drawn in code and synced to the uploaded voice.

usage: python3 make_briefing.py <audio.wav> <out_dir>
"""
import math, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AUDIO, OUT = sys.argv[1], Path(sys.argv[2])
FR, DUR, W, H, S = 30, 10.0, 1280, 720, 2
VOICE_END = 8.57  # end of the morning-briefing part of the audio
F_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_R = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"
F_SB = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"

# word timings (from transcription)
WORDS = [("Good", 0.00, 0.34), ("morning.", 0.34, 0.66), ("It's", 1.22, 1.48), ("68", 1.48, 1.90),
         ("degrees", 1.90, 2.18), ("and", 2.18, 2.56), ("sunny.", 2.56, 2.86),
         ("Traffic", 3.50, 3.78), ("is", 3.78, 4.24), ("a", 4.24, 4.38), ("bit", 4.38, 4.48),
         ("heavy", 4.48, 4.72), ("today,", 4.72, 4.98), ("so", 5.28, 5.46), ("I'd", 5.46, 5.84),
         ("suggest", 5.84, 6.04), ("leaving", 6.04, 6.34), ("10", 6.34, 6.74), ("minutes", 6.74, 6.92),
         ("early", 6.92, 7.28), ("for", 7.28, 7.48), ("your", 7.48, 7.60), ("9", 7.60, 7.78),
         ("a.m.", 7.78, 8.04), ("meeting.", 8.16, 8.26)]
LINES = [(0, 7), (7, 13), (13, 25)]  # caption lines as word-index ranges

def P(*v): return [int(round(x * S)) for x in v]
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a))
def ease_out(x): return 1 - (1 - x) ** 3
def font(path, size): return ImageFont.truetype(path, int(size * S))

# ---------------------------------------------------------------- audio
def prepare_audio():
    wav = OUT / "voice_10s.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", AUDIO, "-t", str(VOICE_END),
                    "-af", f"afade=t=out:st={VOICE_END - 0.15}:d=0.15,apad=whole_dur={DUR}",
                    "-ar", "48000", "-ac", "1", str(wav)], check=True)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop = 48000 // FR
    env = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(int(DUR * FR))])
    env = np.nan_to_num(env)
    env = np.convolve(env / env.max(), np.ones(3) / 3, mode="same")
    return wav, env

# ---------------------------------------------------------------- static background
def background():
    im = Image.new("RGB", (W * S, H * S))
    px = np.zeros((H * S, W * S, 3), np.float32)
    yy, xx = np.mgrid[0:H * S, 0:W * S].astype(np.float32)
    top, bot = np.array([14, 18, 40]), np.array([40, 30, 62])
    k = (yy / (H * S))[..., None]
    px[:] = top * (1 - k) + bot * k
    # warm sunrise glow bottom-left
    d = np.sqrt((xx - 260 * S) ** 2 + (yy - 820 * S) ** 2) / (700 * S)
    glow = np.clip(1 - d, 0, 1)[..., None] ** 2
    px += glow * np.array([255, 140, 70]) * 0.55
    im = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8))
    return im

# ---------------------------------------------------------------- widgets
def card(d, x, y, w, h, alpha):
    c = int(255 * 0.10 * alpha)
    d.rounded_rectangle(P(x, y, x + w, y + h), radius=22 * S, fill=(255, 255, 255, c),
                        outline=(255, 255, 255, int(60 * alpha)), width=S)

def weather_card(d, x, y, a, t):
    card(d, x, y, 560, 140, a)
    A = int(255 * a)
    cx, cy = x + 75, y + 70  # sun icon, slowly rotating rays
    for i in range(10):
        ang = i * math.pi / 5 + t * 0.6
        r0, r1 = 34, 46
        d.line(P(cx + r0 * math.cos(ang), cy + r0 * math.sin(ang), cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
               fill=(255, 196, 60, A), width=5 * S)
    d.ellipse(P(cx - 26, cy - 26, cx + 26, cy + 26), fill=(255, 200, 70, A))
    temp = int(round(68 * ease_out(seg(t, 1.45, 1.95))))  # number counts up as it's spoken
    d.text(P(x + 150, y + 22), f"{temp}°", font=font(F_XB, 64), fill=(255, 255, 255, A))
    d.text(P(x + 300, y + 38), "Sunny", font=font(F_SB, 30), fill=(255, 255, 255, A))
    d.text(P(x + 300, y + 80), "Weather today", font=font(F_R, 20), fill=(200, 205, 230, A))

def traffic_card(d, x, y, a, t):
    card(d, x, y, 560, 140, a)
    A = int(255 * a)
    cx, cy = x + 75, y + 72  # little car
    d.rounded_rectangle(P(cx - 42, cy - 8, cx + 42, cy + 22), radius=10 * S, fill=(120, 170, 255, A))
    d.polygon(P(cx - 24, cy - 8, cx - 14, cy - 28, cx + 16, cy - 28, cx + 28, cy - 8), fill=(120, 170, 255, A))
    d.polygon(P(cx - 16, cy - 10, cx - 9, cy - 23, cx + 12, cy - 23, cx + 20, cy - 10), fill=(30, 40, 80, A))
    for wx in (-24, 24):
        d.ellipse(P(cx + wx - 11, cy + 12, cx + wx + 11, cy + 34), fill=(25, 25, 35, A))
    d.text(P(x + 150, y + 28), "Traffic", font=font(F_XB, 40), fill=(255, 255, 255, A))
    pa = 255 if t >= 4.5 else 0  # "Heavy" pill pops on the word
    if pa:
        d.rounded_rectangle(P(x + 150, y + 84, x + 262, y + 118), radius=17 * S, fill=(235, 70, 70, pa))
        d.text(P(x + 170, y + 88), "Heavy", font=font(F_B, 20), fill=(255, 255, 255, pa))
    # congested road bar
    d.rounded_rectangle(P(x + 290, y + 95, x + 520, y + 107), radius=6 * S, fill=(255, 255, 255, int(40 * a)))
    fill_w = 230 * ease_out(seg(t, 4.5, 5.2))
    if fill_w > 12:
        d.rounded_rectangle(P(x + 290, y + 95, x + 290 + fill_w, y + 107), radius=6 * S, fill=(235, 70, 70, A))

def calendar_card(d, x, y, a, t):
    card(d, x, y, 560, 140, a)
    A = int(255 * a)
    ix, iy = x + 35, y + 32  # calendar icon
    d.rounded_rectangle(P(ix, iy, ix + 80, iy + 78), radius=12 * S, fill=(255, 255, 255, A))
    d.rounded_rectangle(P(ix, iy, ix + 80, iy + 24), radius=12 * S, fill=(235, 80, 80, A))
    d.rectangle(P(ix, iy + 14, ix + 80, iy + 24), fill=(235, 80, 80, A))
    d.text(P(ix + 28, iy + 28), "9", font=font(F_XB, 38), fill=(30, 30, 50, A))
    d.text(P(x + 150, y + 26), "Meeting · 9:00 AM", font=font(F_XB, 32), fill=(255, 255, 255, A))
    pa = 255 if t >= 6.35 else 0  # suggestion pill appears on "10 minutes early"
    if pa:
        d.rounded_rectangle(P(x + 150, y + 82, x + 430, y + 118), radius=18 * S, fill=(70, 200, 140, pa))
        d.text(P(x + 168, y + 87), "Leave 10 min early", font=font(F_B, 21), fill=(255, 255, 255, pa))

def orb(lay, t, level, fade):
    """Glowing voice orb that pulses with the voice loudness."""
    cx, cy = 300, 330
    g = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    r = 105 + 38 * level + 4 * math.sin(t * 2.2)
    d.ellipse(P(cx - r - 40, cy - r - 40, cx + r + 40, cy + r + 40), fill=(120, 140, 255, int(110 * fade)))
    g = g.filter(ImageFilter.GaussianBlur(40 * S))
    lay.paste(g, (0, 0), g)
    d = ImageDraw.Draw(lay, "RGBA")
    for i, col in enumerate(((90, 110, 255), (150, 120, 255), (255, 150, 200))):
        rr = r * (1 - i * 0.22)
        ox = 8 * math.sin(t * 1.7 + i * 2)
        oy = 8 * math.cos(t * 1.3 + i * 2)
        d.ellipse(P(cx - rr + ox, cy - rr + oy, cx + rr + ox, cy + rr + oy), fill=col + (int(255 * fade * (0.9 - i * 0.15)),))
    # waveform bars across the orb
    for i in range(9):
        h = 8 + 70 * level * (0.5 + 0.5 * math.sin(t * 18 + i * 1.3)) * (1 - abs(i - 4) / 6)
        x = cx - 64 + i * 16
        d.rounded_rectangle(P(x - 4, cy - h / 2, x + 4, cy + h / 2), radius=4 * S, fill=(255, 255, 255, int(230 * fade)))

def captions(d, t):
    cur = None
    for a, b in LINES:
        if WORDS[a][1] - 0.15 <= t <= WORDS[b - 1][2] + 0.45:
            cur = (a, b)
    if cur is None:
        return
    a, b = cur
    f = font(F_B, 34)
    words = [w for w, _, _ in WORDS[a:b]]
    widths = [d.textlength(w + " ", font=f) for w in words]
    x = (W * S - sum(widths)) / 2
    for (w, s, e), wd in zip(WORDS[a:b], widths):
        spoken = t >= s
        col = (255, 255, 255, 255) if spoken else (255, 255, 255, 90)
        if s <= t <= e + 0.1:
            col = (255, 210, 90, 255)
        d.text((x, 630 * S), w, font=f, fill=col, stroke_width=2 * S, stroke_fill=(10, 10, 30, 200))
        x += wd

# ---------------------------------------------------------------- render
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fdir = OUT / "frames"; fdir.mkdir(exist_ok=True)
    wav, env = prepare_audio()
    bg = background()
    for i in range(int(DUR * FR)):
        t = i / FR
        lay = bg.copy()
        level = float(env[i]) if t < VOICE_END else 0.0
        outro = seg(t, 8.6, 9.0)
        orb(lay, t, level, 1.0)
        def group(alpha, draw_fn):
            """Draw on a transparent layer, then composite it at the given opacity."""
            if alpha <= 0:
                return
            g = Image.new("RGBA", lay.size, (0, 0, 0, 0))
            draw_fn(ImageDraw.Draw(g))
            if alpha < 1:
                g.putalpha(g.getchannel("A").point(lambda v: int(v * alpha)))
            lay.paste(g, (0, 0), g)
        # header
        def header(d):
            d.text(P(60, 50), "Good morning", font=font(F_XB, 46), fill=(255, 255, 255, 255))
            d.text(P(60, 110), "Tuesday · 7:42 AM", font=font(F_R, 22), fill=(200, 205, 235, 255))
        group(seg(t, 0.0, 0.4) * (1 - outro), header)
        # cards slide in from the right as each topic is mentioned
        for start, y, fn in ((1.15, 120, weather_card), (3.45, 285, traffic_card), (5.25, 450, calendar_card)):
            k = ease_out(seg(t, start, start + 0.45))
            x = 640 + 120 * (1 - k)
            group(k * (1 - outro), lambda d, fn=fn, x=x, y=y: fn(d, x, y, 1.0, t))
        if t < 8.9:
            group(1.0, lambda d: captions(d, t))
        # outro
        def outro_text(d):
            f = font(F_XB, 54); msg = "Have a great day"
            d.text(((W * S - d.textlength(msg, font=f)) / 2 + 160 * S, 300 * S), msg, font=f, fill=(255, 255, 255, 255))
            f2 = font(F_SB, 26); m2 = "Your morning briefing"
            d.text(((W * S - d.textlength(m2, font=f2)) / 2 + 160 * S, 380 * S), m2, font=f2, fill=(210, 210, 240, 255))
        group(seg(t, 9.0, 9.4), outro_text)
        fin = seg(t, 9.6, 10.0)  # fade to black
        im = lay.convert("RGB")
        if fin > 0:
            im = Image.blend(im, Image.new("RGB", im.size), fin)
        im.resize((W, H), Image.LANCZOS).save(fdir / f"f{i:04d}.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FR), "-i", str(fdir / "f%04d.png"),
                    "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-c:a", "aac", "-b:a", "160k", "-t", str(DUR), str(OUT / "morning_briefing_10s.mp4")], check=True)
    print("wrote", OUT / "morning_briefing_10s.mp4")

if __name__ == "__main__":
    main()
