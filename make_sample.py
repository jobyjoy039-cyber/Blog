"""5-second original 'Casting Call' sample, drawn entirely in code (no AI credits).

Beats:
  0.0-3.4  wide stage: spotlight flickers on, title pops in, tiny lizard in a
           paper-wing costume walks to the X, puffs up, lets out a tiny flame (camera pushes in)
  3.4-5.0  head judge close-up: sips coffee, deadpan, "Next."
"""
import math, random, subprocess, sys, wave, struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
FR, DUR, W, H, S = 30, 5.0, 1280, 720, 2  # S = supersampling factor
N = int(FR * DUR)
CUT = 3.4
FONT_B = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_BI = "/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf"

def P(*v): return [int(round(x * S)) for x in v]
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a))
def ease_io(x): return x * x * (3 - 2 * x)
def ease_back(x, k=1.70158):
    x -= 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2

# ---------------------------------------------------------------- stage background
def stage_bg():
    im = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(im)
    for y in range(0, 470 * S):  # back wall gradient
        k = y / (470 * S)
        d.line([(0, y), (W * S, y)], fill=(int(10 + 20 * k), int(22 + 35 * k), int(45 + 50 * k)))
    for i in range(26):  # back curtain folds
        x = i * 52 + 20
        d.rectangle(P(x, 60, x + 18, 470), fill=(14, 34, 62))
    # floor (wooden planks in perspective)
    d.polygon(P(0, 720, 1280, 720, 1120, 470, 160, 470), fill=(40, 52, 70))
    for i in range(-12, 13):
        x0, x1 = 640 + i * 110, 640 + i * 48
        d.line(P(x0, 720, x1, 470), fill=(30, 40, 56), width=2 * S)
    d.line(P(160, 470, 1120, 470), fill=(70, 85, 105), width=3 * S)
    # red side curtains with fold shading
    for side in (0, 1):
        for i in range(6):
            x = i * 30 if side == 0 else 1280 - 180 + i * 30
            col = (150, 20, 28) if i % 2 == 0 else (110, 12, 20)
            d.rectangle(P(x, 0, x + 30, 720), fill=col)
        sx = 180 if side == 0 else 1100
        d.line(P(sx, 0, sx, 720), fill=(60, 5, 10), width=4 * S)
    # top valance with scallops
    d.rectangle(P(0, 0, 1280, 60), fill=(130, 16, 26))
    for i in range(17):
        d.ellipse(P(i * 80 - 10, 30, i * 80 + 70, 90), fill=(130, 16, 26))
    d.line(P(0, 62, 1280, 62), fill=(200, 150, 60), width=3 * S)
    # red X tape on the mark
    for a, b in (((600, 545), (680, 575)), ((680, 545), (600, 575))):
        d.line(P(*a, *b), fill=(210, 40, 40), width=7 * S)
    return im

def spotlight_layer():
    m = Image.new("L", (W * S, H * S), 0)
    d = ImageDraw.Draw(m)
    d.polygon(P(600, 0, 680, 0, 820, 600, 460, 600), fill=95)
    d.ellipse(P(470, 520, 810, 610), fill=170)
    return m.filter(ImageFilter.GaussianBlur(28 * S))

# ---------------------------------------------------------------- judge background
def judge_bg():
    im = Image.new("RGB", (W * S, H * S), (40, 14, 16))
    d = ImageDraw.Draw(im)
    for y in range(H * S):
        k = y / (H * S)
        d.line([(0, y), (W * S, y)], fill=(int(60 - 20 * k), int(22 - 8 * k), int(20 - 6 * k)))
    for row in range(6):  # rows of theatre seats
        y = 120 + row * 85
        for c in range(-1, 15):
            x = c * 95 + (row % 2) * 47
            d.rounded_rectangle(P(x, y, x + 80, y + 70), radius=18 * S, fill=(150, 24, 34))
            d.rounded_rectangle(P(x + 6, y + 6, x + 74, y + 34), radius=12 * S, fill=(180, 40, 48))
    for i in range(9):  # warm balcony lamps
        d.ellipse(P(i * 160 + 40, 40, i * 160 + 70, 70), fill=(255, 210, 140))
    im = im.filter(ImageFilter.GaussianBlur(9 * S))
    d = ImageDraw.Draw(im)
    d.rectangle(P(0, 600, 1280, 720), fill=(196, 160, 112))  # judges' table
    d.rectangle(P(0, 600, 1280, 612), fill=(225, 195, 150))
    d.rectangle(P(860, 630, 1060, 700), fill=(240, 236, 225))  # papers
    d.line(P(880, 650, 1030, 650), fill=(160, 160, 160), width=2 * S)
    d.line(P(880, 670, 1000, 670), fill=(160, 160, 160), width=2 * S)
    return im

# ---------------------------------------------------------------- characters
def draw_lizard(d, cx, cy, t_walk, puff, mouth):
    """Tiny green lizard in a cardboard dragon costume. cx,cy = feet centre."""
    sc = 1.0 + 0.35 * puff
    bob = abs(math.sin(t_walk * 14)) * 4 * (1 - puff)
    def L(x, y): return (cx + x * sc, cy - bob + y * sc)
    def E(x0, y0, x1, y1, **k):
        a, b = L(x0, y0), L(x1, y1)
        d.ellipse(P(a[0], a[1], b[0], b[1]), **k)
    g, gd = (96, 190, 90), (60, 140, 64)
    # shadow
    d.ellipse(P(cx - 60, cy - 6, cx + 60, cy + 8), fill=(18, 24, 34))
    # tail
    tail = [L(-30, -20), L(-70, -26), L(-95, -50), L(-85, -54), L(-62, -36), L(-28, -32)]
    d.polygon([v for p in tail for v in P(*p)], fill=gd)
    # paper wings (costume) with tape
    for side, col in ((-1, (210, 190, 150)), (1, (230, 212, 170))):
        flap = math.sin(t_walk * 10) * 6 * (1 - puff) + puff * 14
        wing = [L(0, -55), L(-25 + side * 8, -110 - flap), L(-55 + side * 4, -80 - flap * 0.5)]
        d.polygon([v for p in wing for v in P(*p)], fill=col, outline=(120, 100, 70))
    a = L(-20, -62); b = L(-6, -56)
    d.rectangle(P(a[0], a[1], b[0], b[1]), fill=(235, 235, 220))
    # body + belly
    E(-38, -60, 38, -8, fill=g)
    E(-22, -48, 26, -12, fill=(170, 220, 140))
    # back spikes (cardboard, slightly crooked)
    for i, x in enumerate((-26, -12, 2)):
        sp = [L(x, -55), L(x + 7, -74 - (i % 2) * 6), L(x + 14, -57)]
        d.polygon([v for p in sp for v in P(*p)], fill=(230, 120, 40))
    # legs
    step = math.sin(t_walk * 14) * 6 * (1 - puff)
    E(-28 + step, -16, -10 + step, 2, fill=gd)
    E(12 - step, -16, 30 - step, 2, fill=gd)
    # head
    E(18, -92, 70, -48, fill=g)
    E(48, -80, 84, -54, fill=g)  # snout
    E(72, -74, 77, -69, fill=(40, 90, 40))  # nostril
    # eye (big, nervous)
    E(30, -90, 54, -64, fill=(255, 255, 255), outline=(40, 80, 40))
    E(40 + 3 * puff, -82, 50 + 3 * puff, -70, fill=(20, 20, 20))
    E(43, -80, 46, -77, fill=(255, 255, 255))
    # mouth
    if mouth > 0.05:
        E(60, -60, 86, -60 + 16 * mouth, fill=(90, 20, 30))
    else:
        a, b = L(56, -58), L(80, -60)
        d.line(P(a[0], a[1], b[0], b[1]), fill=(40, 90, 40), width=2 * S)
    return L(84, -56)  # mouth tip, for the flame

def draw_flame(d, x, y, k):
    """Tiny, disappointing flame puff + smoke. k in [0,1] lifetime."""
    if k <= 0 or k >= 1:
        return
    size = 22 * math.sin(math.pi * min(1, k * 1.6))
    if size > 0:
        d.ellipse(P(x - 2, y - size * 0.5, x + size * 1.6, y + size * 0.5), fill=(255, 150, 40))
        d.ellipse(P(x, y - size * 0.28, x + size, y + size * 0.28), fill=(255, 230, 120))
    sk = seg(k, 0.35, 1.0)
    if sk > 0:  # smoke ring drifts up
        r = 8 + 22 * sk
        c = int(150 - 60 * sk)
        d.ellipse(P(x + 30 - r, y - 30 * sk - 40 - r, x + 30 + r, y - 30 * sk - 40 + r),
                  outline=(c, c, c + 10), width=max(1, int(5 * (1 - sk) * S)))

def draw_judge(d, t):
    """Older head judge, deadpan, sipping coffee."""
    cx = 560
    # jacket + shirt + tie
    d.polygon(P(cx - 230, 720, cx - 170, 450, cx + 170, 450, cx + 230, 720), fill=(110, 78, 52))
    d.polygon(P(cx - 60, 450, cx + 60, 450, cx, 560), fill=(235, 232, 220))
    d.polygon(P(cx - 14, 470, cx + 14, 470, cx + 22, 600, cx, 620, cx - 22, 600), fill=(170, 30, 40))
    # neck + head
    d.rectangle(P(cx - 45, 400, cx + 45, 460), fill=(225, 170, 135))
    d.ellipse(P(cx - 135, 150, cx + 135, 440), fill=(236, 186, 150))
    d.ellipse(P(cx - 150, 270, cx - 110, 330), fill=(225, 170, 135))  # ears
    d.ellipse(P(cx + 110, 270, cx + 150, 330), fill=(225, 170, 135))
    # messy grey hair
    rnd = random.Random(4)
    for _ in range(16):
        a = rnd.uniform(math.pi * 1.05, math.pi * 1.95)
        r = rnd.uniform(115, 140)
        x, y = cx + r * math.cos(a), 290 + r * 1.15 * math.sin(a)
        s = rnd.uniform(28, 44)
        d.ellipse(P(x - s, y - s, x + s, y + s), fill=(200, 200, 205))
    # eyebrow raise near the end
    raise_ = 14 * ease_io(seg(t, 4.45, 4.6))
    blink = 1.0 if 3.95 < t < 4.05 else 0.0
    for side in (-1, 1):
        ex = cx + side * 55
        d.ellipse(P(ex - 32, 255, ex + 32, 315), fill=(255, 255, 255))
        d.ellipse(P(ex - 9, 285, ex + 9, 305), fill=(40, 30, 25))
        lid = 285 + 18 * blink  # heavy, half-closed lids = deadpan
        d.chord(P(ex - 34, 250, ex + 34, lid + 22), 180, 360, fill=(220, 165, 130))
        d.rectangle(P(ex - 34, 250, ex + 34, lid), fill=(220, 165, 130))
        d.line(P(ex - 34, lid, ex + 34, lid), fill=(120, 80, 60), width=3 * S)
        ry = raise_ if side == 1 else 0
        d.polygon(P(ex - 40, 238 - ry, ex + 40, 232 - ry, ex + 38, 248 - ry, ex - 38, 252 - ry), fill=(170, 170, 175))
        d.ellipse(P(ex - 40, 248, ex + 40, 322), outline=(40, 40, 40), width=4 * S)  # glasses
    d.line(P(cx - 15, 285, cx + 15, 285), fill=(40, 40, 40), width=4 * S)
    d.ellipse(P(cx - 22, 300, cx + 22, 350), fill=(225, 160, 125))  # nose
    # mug moves up to mouth and down
    up = ease_io(seg(t, 3.5, 3.8)) - ease_io(seg(t, 4.3, 4.55))
    mx, my = cx + 150 - 90 * up, 600 - 230 * up
    if up < 0.6:  # mouth/moustache visible when the mug isn't covering it
        d.line(P(cx - 30, 395, cx + 30, 395), fill=(120, 60, 50), width=4 * S)
    d.ellipse(P(cx - 70, 350, cx + 70, 395), fill=(205, 205, 210))  # moustache
    # hand + mug
    d.ellipse(P(mx - 50, my + 10, mx + 30, my + 80), fill=(225, 170, 135))
    d.rounded_rectangle(P(mx - 40, my - 90, mx + 40, my + 20), radius=10 * S, fill=(245, 245, 240))
    d.ellipse(P(mx + 28, my - 70, mx + 70, my - 10), outline=(245, 245, 240), width=10 * S)
    d.ellipse(P(mx - 40, my - 100, mx + 40, my - 80), fill=(225, 225, 220))
    if up < 0.3:  # steam
        for i in range(3):
            sx = mx - 20 + i * 20
            off = math.sin(t * 6 + i) * 6
            d.arc(P(sx - 8 + off, my - 150, sx + 8 + off, my - 105), 90, 270, fill=(230, 230, 230), width=3 * S)

# ---------------------------------------------------------------- text
def text_layer(lines, scale, alpha):
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    if alpha <= 0 or scale <= 0:
        return lay
    d = ImageDraw.Draw(lay)
    for txt, font, size, fill, y in lines:
        f = ImageFont.truetype(font, int(size * S * scale))
        bb = d.textbbox((0, 0), txt, font=f)
        x = (W * S - (bb[2] - bb[0])) / 2
        yy = (y * S) - (bb[3] - bb[1]) / 2
        d.text((x, yy), txt, font=f, fill=fill + (int(255 * alpha),),
               stroke_width=int(4 * S * scale), stroke_fill=(10, 10, 20, int(255 * alpha)))
    return lay

# ---------------------------------------------------------------- render
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fdir = OUT / "frames"; fdir.mkdir(exist_ok=True)
    bg, spot, jbg = stage_bg(), spotlight_layer(), judge_bg()
    light = Image.new("RGB", (W * S, H * S), (150, 200, 255))
    for i in range(N):
        t = i / FR
        if t < CUT:
            on = ease_io(seg(t, 0.0, 0.5))
            if 0.15 < t < 0.22 or 0.3 < t < 0.34:
                on *= 0.3  # flicker
            im = Image.composite(light, bg, spot.point(lambda v: int(v * on)))
            dark = Image.new("RGB", im.size, (0, 0, 0))
            im = Image.blend(dark, im, 0.25 + 0.75 * on)
            d = ImageDraw.Draw(im)
            walk = seg(t, 0.9, 2.4)
            lx = 1240 - 600 * ease_io(walk)
            puff = ease_back(seg(t, 2.45, 2.75)) * (1 - ease_io(seg(t, 3.05, 3.3)))
            mouth = ease_io(seg(t, 2.6, 2.75)) * (1 - seg(t, 3.0, 3.15))
            tip = draw_lizard(d, lx, 560, t, clamp(puff, 0, 1.2), mouth)
            draw_flame(d, tip[0], tip[1], seg(t, 2.72, 3.3))
            # title pops in and out
            pin = seg(t, 0.35, 0.7)
            sc = ease_back(pin) if pin < 1 else 1
            al = min(1, pin * 3) * (1 - seg(t, 1.6, 1.95))
            im.paste(text_layer([("CASTING CALL", FONT_B, 44, (255, 205, 60), 250),
                                 ("THE DRAGON", FONT_BI, 110, (255, 255, 255), 330)], sc, al),
                     (0, 0), text_layer([("CASTING CALL", FONT_B, 44, (255, 205, 60), 250),
                                         ("THE DRAGON", FONT_BI, 110, (255, 255, 255), 330)], sc, al))
            if 2.75 < t < 3.3:  # tiny sound caption
                tl = text_layer([("*squeak*", FONT_BI, 30, (255, 240, 200), 395)], 1, seg(t, 2.75, 2.85))
                im.paste(tl, (0, 0), tl)
            # slow push-in on the lizard during the audition
            z = 1 + 0.35 * ease_io(seg(t, 2.2, 3.0))
            fx, fy = 640, 480
            cw, ch = W * S / z, H * S / z
            x0 = clamp(fx * S - cw / 2, 0, W * S - cw); y0 = clamp(fy * S - ch / 2, 0, H * S - ch)
            im = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))
        else:
            im = jbg.copy()
            draw_judge(ImageDraw.Draw(im), t)
            if t > 4.55:
                tl = text_layer([("Next.", FONT_B, 64, (255, 255, 255), 650)], 1, seg(t, 4.55, 4.65))
                im.paste(tl, (0, 0), tl)
        im = im.resize((W, H), Image.LANCZOS)
        im.save(fdir / f"f{i:04d}.png")

    # ---------------- simple synthesized sound effects
    sr = 44100
    a = np.random.default_rng(1).normal(0, 0.004, int(sr * DUR))  # room tone
    def add(t0, sig):
        s = int(t0 * sr); a[s:s + len(sig)] += sig[: len(a) - s]
    tt = lambda d_: np.arange(int(sr * d_)) / sr
    x = tt(0.6); add(0.35, 0.6 * np.sin(2 * np.pi * (70 - 30 * x) * x) * np.exp(-x * 6))  # title boom
    for k in range(7):  # tiny footsteps
        x = tt(0.05); add(0.95 + k * 0.21, 0.25 * np.sin(2 * np.pi * 900 * x) * np.exp(-x * 120))
    x = tt(0.35); add(2.72, 0.35 * np.sin(2 * np.pi * (700 + 1400 * x) * x) * np.exp(-x * 4))  # squeak
    x = tt(0.4); add(2.75, 0.2 * np.random.default_rng(2).normal(0, 1, len(x)) * np.exp(-x * 8))  # puff
    x = tt(0.5); add(3.85, 0.12 * np.random.default_rng(3).normal(0, 1, len(x)) * np.sin(np.pi * x / 0.5))  # slurp
    a = np.clip(a, -1, 1)
    with wave.open(str(OUT / "sfx.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(v * 32767)) for v in a))

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FR), "-i", str(fdir / "f%04d.png"),
                    "-i", str(OUT / "sfx.wav"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-c:a", "aac", "-shortest", str(OUT / "casting_call_sample.mp4")], check=True)
    print("wrote", OUT / "casting_call_sample.mp4")

if __name__ == "__main__":
    main()
