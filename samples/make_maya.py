"""Code-animated explainer for the 'Maya - chapter 6' narration.

usage: python3 make_maya.py <audio.wav> <words.json> <out_dir>
"""
import json, math, random, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AUDIO, WORDS_JSON, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
FR, W, H, S = 30, 1280, 720, 2
DUR = 80.0
SERIF = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
SERIF_B = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
SERIF_I = "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"
SANS_B = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
GOLD, GOLD_D, CREAM, INK = (232, 190, 110), (170, 130, 60), (245, 236, 215), (12, 10, 30)
_fc = {}

def font(path, size):
    k = (path, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, int(size * S))
    return _fc[k]
def P(*v): return [int(round(x * S)) for x in v]
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, a, b): return clamp((t - a) / (b - a))
def eo(x): return 1 - (1 - x) ** 3
def eio(x): return x * x * (3 - 2 * x)
def rgba(c, a): return tuple(c[:3]) + (int(255 * clamp(a)),)

def new_layer(): return Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
def sub(layer, alpha, fn):
    """Draw fn on its own transparent layer and composite it at `alpha`."""
    if alpha <= 0.003:
        return
    g = new_layer()
    fn(ImageDraw.Draw(g), g)
    if alpha < 0.997:
        g.putalpha(g.getchannel("A").point(lambda v: int(v * alpha)))
    layer.alpha_composite(g)

def ctext(d, txt, f, y, fill, x=640, anchor="mm"):
    d.text((x * S, y * S), txt, font=f, fill=fill, anchor=anchor)

# ------------------------------------------------------------------ words / captions
def load_words():
    raw = json.load(open(WORDS_JSON))
    out, i = [], 0
    fix = {"Maya": "Māyā", "Maya,": "Māyā,", "Upanishads,": "Upaniṣads,", "Shankara,": "Śaṅkara,"}
    while i < len(raw):
        w, s, e = raw[i]
        if w == "Go" and i + 2 < len(raw) and raw[i + 2][0] == "Pada":
            out.append(["Gauḍapāda", s, raw[i + 2][2]]); i += 3; continue
        if w == "Rig" and raw[i + 1][0].startswith("Veda"):
            out.append(["Ṛg", s, e]); i += 1; continue
        out.append([fix.get(w, w), s, e]); i += 1
    lines, cur = [], []
    for k, (w, s, e) in enumerate(out):
        cur.append(k)
        nxt_gap = out[k + 1][1] - e if k + 1 < len(out) else 9
        if w[-1] in ".,?" and (len(cur) >= 5 or nxt_gap > 0.6) or len(cur) >= 9 or nxt_gap > 0.9:
            lines.append(cur); cur = []
    if cur: lines.append(cur)
    return out, lines

WORDS, LINES = load_words()

def captions(d, t):
    for ln in LINES:
        s, e = WORDS[ln[0]][1], WORDS[ln[-1]][2]
        if s - 0.2 <= t <= e + 0.5:
            f = font(SANS_B, 25)
            ws = [WORDS[k][0] for k in ln]
            widths = [d.textlength(w + " ", font=f) for w in ws]
            x = (W * S - sum(widths)) / 2
            for k, wd in zip(ln, widths):
                w, ws_, we = WORDS[k]
                col = (255, 255, 255, 235) if t >= ws_ else (255, 255, 255, 110)
                if ws_ <= t <= we + 0.08:
                    col = GOLD + (255,)
                d.text((x, 662 * S), w, font=f, fill=col, anchor="lm", stroke_width=2 * S, stroke_fill=(0, 0, 0, 160))
                x += wd
            return

# ------------------------------------------------------------------ static art
def night_bg():
    yy, xx = np.mgrid[0:H * S, 0:W * S].astype(np.float32)
    k = (yy / (H * S))[..., None]
    px = np.array([10, 9, 32]) * (1 - k) + np.array([28, 18, 48]) * k
    d = np.sqrt((xx - 640 * S) ** 2 + (yy - 360 * S) ** 2) / (760 * S)
    px += (np.clip(1 - d, 0, 1) ** 2)[..., None] * np.array([60, 40, 70])
    im = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8)).convert("RGBA")
    dr = ImageDraw.Draw(im)
    rnd = random.Random(7)
    for _ in range(160):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.6, 1.6)
        c = rnd.randint(90, 180)
        dr.ellipse(P(x - r, y - r, x + r, y + r), fill=(c, c, c + 30, 255))
    # thin gold frame with corner ornaments
    dr.rectangle(P(24, 24, W - 24, H - 24), outline=GOLD_D + (255,), width=S)
    for cx, cy in ((24, 24), (W - 24, 24), (24, H - 24), (W - 24, H - 24)):
        dr.polygon(P(cx, cy - 9, cx + 9, cy, cx, cy + 9, cx - 9, cy), fill=GOLD + (255,))
    return im

def palace_art():
    im = new_layer()
    d = ImageDraw.Draw(im)
    vx, vy = 640, 300
    d.rectangle(P(0, 0, W, vy), fill=(36, 26, 52, 255))
    # floor: checkered tiles in one-point perspective
    rows = [vy + 6 * (1.32 ** i) for i in range(14)]
    for r in range(len(rows) - 1):
        y0, y1 = rows[r], min(rows[r + 1], H)
        for c in range(-14, 15):
            def xat(y, cc): return vx + (cc * 95) * (y - vy) / (H - vy)
            poly = [xat(y0, c), y0, xat(y0, c + 1), y0, xat(y1, c + 1), y1, xat(y1, c), y1]
            col = (190, 170, 140) if (r + c) % 2 else (150, 128, 104)
            d.polygon(P(*poly), fill=col + (255,))
        if rows[r + 1] > H:
            break
    # side colonnades
    for side in (-1, 1):
        for i in range(6):
            depth = 1 - i / 6
            x = vx + side * (130 + 520 * depth ** 1.6)
            top = vy - 30 - 230 * depth ** 1.6
            bot = vy + 10 + 380 * depth ** 1.6
            wcol = 8 + 34 * depth ** 1.6
            d.rectangle(P(x - wcol, top, x + wcol, bot), fill=(214, 196, 160, 255))
            d.rectangle(P(x - wcol - 6, top - 14, x + wcol + 6, top), fill=(232, 214, 176, 255))
    # back wall arch, glowing
    d.rectangle(P(vx - 140, 60, vx + 140, vy + 4), fill=(60, 44, 70, 255))
    d.pieslice(P(vx - 90, 80, vx + 90, 260), 180, 360, fill=(255, 214, 150, 255))
    d.rectangle(P(vx - 90, 170, vx + 90, vy + 4), fill=(255, 214, 150, 255))
    return im

POOL = [(470, 470), (810, 470), (880, 600), (400, 600)]  # trapezoid on the floor

def landscape_art():
    yy, xx = np.mgrid[0:H * S, 0:W * S].astype(np.float32)
    k = (yy / (H * S))[..., None]
    px = np.array([40, 60, 120]) * (1 - k) + np.array([240, 170, 120]) * k
    im = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    d.ellipse(P(820, 230, 940, 350), fill=(255, 220, 150, 255))
    for base, amp, col, ph in ((430, 70, (70, 60, 110), 0.3), (480, 50, (50, 45, 85), 1.7), (540, 35, (36, 34, 62), 3.1)):
        pts = [(x, base - amp * (0.6 + 0.4 * math.sin(x / 140 + ph)) * abs(math.sin(x / 260 + ph))) for x in range(0, W + 20, 20)]
        d.polygon([v for p in [(0, H)] + pts + [(W, H)] for v in P(*p)], fill=col + (255,))
    river = [(560, H), (640, 560), (600, 500), (660, 450), (700, 450), (650, 500), (700, 560), (760, H)]
    d.polygon([v for p in river for v in P(*p)], fill=(140, 170, 210, 255))
    return im

# ------------------------------------------------------------------ scenes
def label(d, txt, a):
    f = font(SANS_B, 18)
    d.text((640 * S, 62 * S), "  ".join(txt), font=f, fill=rgba(GOLD, a), anchor="mm")

def phrase(layer, txt, y, t0, size=40, italic=True, col=CREAM, t_out=None):
    a = eo(seg(TNOW, t0, t0 + 0.5))
    if t_out is not None:
        a *= 1 - seg(TNOW, t_out, t_out + 0.35)
    def fn(d, g):
        ctext(d, txt, font(SERIF_I if italic else SERIF, size), y + 8 * (1 - a), col + (255,))
    sub(layer, a, fn)

def scene_title(layer, t):
    def fn(d, g):
        a = eo(seg(t, 0.1, 1.0))
        ctext(d, "M Ā Y Ā", font(SERIF_B, 120), 320, rgba(GOLD, a))
        ctext(d, "Chapter 6  ·  Putting it together", font(SERIF_I, 34), 420, rgba(CREAM, seg(t, 0.6, 1.3)))
        w = 260 * eo(seg(t, 0.4, 1.4))
        d.line(P(640 - w, 372, 640 + w, 372), fill=GOLD_D + (255,), width=S)
    sub(layer, 1, fn)

def scene_rigveda(layer, t):
    cx, cy, R = 640, 390, 150
    def base(d, g):
        label(d, "ṚG VEDA", 1)
        # compass draws the circle while "measure out" is spoken
        k = eio(seg(t, 4.3, 7.3))
        ang = -90 + 360 * k
        if k > 0:
            d.arc(P(cx - R, cy - R, cx + R, cy + R), -90, ang, fill=GOLD + (255,), width=3 * S)
        if k < 1:
            px_, py_ = cx + R * math.cos(math.radians(ang)), cy + R * math.sin(math.radians(ang))
            hx, hy = (cx + px_) / 2, (cy + py_) / 2 - 140
            d.line(P(cx, cy, hx, hy), fill=CREAM + (255,), width=4 * S)
            d.line(P(px_, py_, hx, hy), fill=CREAM + (255,), width=4 * S)
            d.ellipse(P(hx - 9, hy - 9, hx + 9, hy + 9), fill=GOLD + (255,))
        # world gets shaped inside the circle on "shape the world"
        s = eo(seg(t, 8.0, 9.0))
        if s > 0:
            hy0 = cy + 30
            d.line(P(cx - R * 0.95 * s, hy0, cx + R * 0.95 * s, hy0), fill=GOLD + (255,), width=2 * S)
            m = [(cx - 110, hy0), (cx - 50, hy0 - 70 * s), (cx, hy0 - 25 * s), (cx + 55, hy0 - 90 * s), (cx + 115, hy0)]
            d.line([v for p in m for v in P(*p)], fill=GOLD + (255,), width=2 * S, joint="curve")
            r = 22 * s
            d.ellipse(P(cx - 60 - r, cy - 70 - r, cx - 60 + r, cy - 70 + r), outline=GOLD + (255,), width=2 * S)
            for i in range(3):
                yy = hy0 + 22 + i * 18
                d.line(P(cx - 90 + i * 15, yy, cx + 90 - i * 15, yy), fill=GOLD_D + (255,), width=S)
    sub(layer, 1, base)
    # the rivals' cunning: a shadow that circles and changes shape
    def rival(d, g):
        ang = math.radians(150 + (t - 10) * 35)
        x, y = cx + (R + 70) * math.cos(ang), cy + (R + 60) * math.sin(ang)
        morph = 0.5 + 0.5 * math.sin(t * 5)
        rr = 34
        pts = []
        for i in range(24):
            a_ = i / 24 * 2 * math.pi
            wob = 1 + 0.35 * morph * math.sin(3 * a_ + t * 4) + 0.2 * (1 - morph) * math.sin(5 * a_)
            pts += P(x + rr * wob * math.cos(a_), y + rr * wob * math.sin(a_))
        d.polygon(pts, fill=(130, 45, 100, 255))
        for ex in (-10, 10):
            d.ellipse(P(x + ex - 4, y - 8, x + ex + 4, y), fill=(255, 90, 90, 255))
    sub(layer, seg(t, 10.0, 10.6), rival)
    phrase(layer, "the power to measure out and shape the world", 130, 4.9, size=36)
    phrase(layer, "…and the cunning of their rivals", 595, 10.4, size=32, col=(230, 150, 170))

def scene_upanishads(layer, t):
    cx, cy = 640, 380
    icons = ["sun", "mountain", "tree", "wave", "moon", "flower", "bird", "star"]
    def fn(d, g):
        label(d, "UPANIṢADS", 1)
        rays = eo(seg(t, 17.2, 18.4))
        for i, name in enumerate(icons):
            a = eo(seg(t, 14.7 + i * 0.12, 15.2 + i * 0.12))
            if a <= 0:
                continue
            ang = -math.pi / 2 + i * 2 * math.pi / len(icons)
            r = 70 + 150 * a
            x, y = cx + r * math.cos(ang), cy + r * 0.82 * math.sin(ang)
            if rays > 0:
                d.line(P(cx, cy, cx + (x - cx) * rays, cy + (y - cy) * rays), fill=GOLD_D + (255,), width=S)
            draw_icon(d, name, x, y, 26 * a)
        # veil over the hidden lord
        d.rounded_rectangle(P(cx - 48, cy - 62, cx + 48, cy + 62), radius=14 * S, fill=(60, 45, 90, 255),
                            outline=GOLD_D + (255,), width=S)
        for i in range(5):
            x = cx - 32 + i * 16
            d.line(P(x, cy - 52, x + math.sin(t * 2 + i) * 4, cy + 52), fill=(85, 65, 120, 255), width=2 * S)
    glow = 0.55 + 0.25 * math.sin(t * 3)
    def light(d, g):
        r = 90
        d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(255, 210, 140, int(140 * glow)))
    g = new_layer(); light(ImageDraw.Draw(g), g)
    layer.alpha_composite(g.filter(ImageFilter.GaussianBlur(30 * S)))
    sub(layer, 1, fn)
    phrase(layer, "all of nature becomes Māyā", 130, 14.7, size=38)
    phrase(layer, "the display of one hidden Lord", 600, 17.3, size=32, col=GOLD)

def draw_icon(d, name, x, y, s):
    c = GOLD + (255,)
    w = max(1, int(2 * S))
    if s < 1:
        return
    if name == "sun":
        d.ellipse(P(x - s * .45, y - s * .45, x + s * .45, y + s * .45), outline=c, width=w)
        for i in range(8):
            a = i * math.pi / 4
            d.line(P(x + s * .65 * math.cos(a), y + s * .65 * math.sin(a), x + s * .9 * math.cos(a), y + s * .9 * math.sin(a)), fill=c, width=w)
    elif name == "mountain":
        d.line(P(x - s, y + s * .6, x - s * .2, y - s * .6, x + s * .2, y, x + s * .5, y - s * .3, x + s, y + s * .6), fill=c, width=w)
    elif name == "tree":
        d.line(P(x, y + s * .8, x, y), fill=c, width=w)
        d.ellipse(P(x - s * .55, y - s * .8, x + s * .55, y + s * .15), outline=c, width=w)
    elif name == "wave":
        pts = [(x - s + i * s / 6, y + s * .25 * math.sin(i * 1.3)) for i in range(13)]
        d.line([v for p in pts for v in P(*p)], fill=c, width=w, joint="curve")
    elif name == "moon":
        d.arc(P(x - s * .6, y - s * .6, x + s * .6, y + s * .6), 60, 300, fill=c, width=w)
        d.arc(P(x - s * .3, y - s * .5, x + s * .6, y + s * .5), 80, 280, fill=c, width=w)
    elif name == "flower":
        for i in range(5):
            a = i * 2 * math.pi / 5
            d.ellipse(P(x + s * .4 * math.cos(a) - s * .25, y + s * .4 * math.sin(a) - s * .25,
                        x + s * .4 * math.cos(a) + s * .25, y + s * .4 * math.sin(a) + s * .25), outline=c, width=w)
    elif name == "bird":
        d.arc(P(x - s, y - s * .3, x, y + s * .5), 200, 340, fill=c, width=w)
        d.arc(P(x, y - s * .3, x + s, y + s * .5), 200, 340, fill=c, width=w)
    elif name == "star":
        pts = []
        for i in range(10):
            r = s * (0.7 if i % 2 == 0 else 0.3)
            a = -math.pi / 2 + i * math.pi / 5
            pts += P(x + r * math.cos(a), y + r * math.sin(a))
        d.polygon(pts, outline=c, width=w)

def scene_gaudapada(layer, t):
    cx, cy = 640, 370
    def fn(d, g):
        label(d, "GAUḌAPĀDA  &  ŚAṄKARA", 1)
        k = eio(seg(t, 23.7, 25.3))
        n = 36
        for i in range(n):
            ring = i % 3
            ang = i / n * 2 * math.pi + t * 0.15 * (1 if ring != 1 else -1)
            r = k * (70 + ring * 55)
            x, y = cx + r * math.cos(ang), cy + r * 0.85 * math.sin(ang)
            rr = 9 - ring * 2
            d.ellipse(P(x - rr, y - rr, x + rr, y + rr), fill=rgba(GOLD, 1 - 0.25 * ring))
        a = seg(t, 22.6, 23.2)
        rr = 16 + 4 * math.sin(t * 3)
        d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), fill=rgba((255, 236, 190), a))
        # neither real nor unreal
        for word, x, t0, t1 in (("REAL", 330, 26.3, 26.9), ("UNREAL", 950, 27.7, 28.3)):
            wa = seg(t, t0 - 0.3, t0)
            if wa <= 0:
                continue
            f = font(SERIF_B, 44)
            ctext(d, word, f, 380, rgba(CREAM, wa), x=x)
            sl = eo(seg(t, t0, t1))
            tw = d.textlength(word, font=f) / S / 2 + 12
            if sl > 0:
                d.line(P(x - tw, 395, x - tw + 2 * tw * sl, 365), fill=(220, 80, 80, 255), width=4 * S)
    sub(layer, 1, fn)
    phrase(layer, "the One appears as many", 130, 23.6, size=40)
    phrase(layer, "neither real nor unreal", 600, 26.2, size=32, col=GOLD)

def scene_origin(layer, t):
    def fn(d, g):
        label(d, "WHERE THE WORD BEGAN", 1)
        y = 300
        L = eo(seg(t, 29.6, 30.6))
        d.line(P(170, y, 170 + 940 * L, y), fill=GOLD_D + (255,), width=3 * S)
        if L > 0.98:
            d.polygon(P(1110, y, 1094, y - 9, 1094, y + 9), fill=GOLD_D + (255,))
        # "illusion" crossed out at the beginning, then "the power to make"
        a1 = seg(t, 31.2, 31.6)
        if a1 > 0:
            ctext(d, "illusion", font(SERIF_I, 34), y - 45, rgba((200, 190, 200), a1), x=260)
            st = eo(seg(t, 31.8, 32.4))
            if st > 0:
                d.line(P(200, y - 45, 200 + 120 * st, y - 45), fill=(220, 80, 80, 255), width=3 * S)
        a2 = eo(seg(t, 33.6, 34.2))
        if a2 > 0:
            d.ellipse(P(250, y - 10, 270, y + 10), fill=GOLD + (255,))
            ctext(d, "the power to make", font(SERIF_B, 34), y + 50, rgba(GOLD, a2), x=260)
            for i in range(8):  # spark
                ang = i * math.pi / 4
                r0, r1 = 16, 16 + 14 * a2
                d.line(P(260 + r0 * math.cos(ang), y + r0 * math.sin(ang), 260 + r1 * math.cos(ang), y + r1 * math.sin(ang)),
                       fill=GOLD + (255,), width=2 * S)
        a3 = eo(seg(t, 35.3, 35.9))
        if a3 > 0:
            d.ellipse(P(940, y - 10, 960, y + 10), fill=rgba(CREAM, a3))
            ctext(d, "illusion", font(SERIF_B, 34), y + 50, rgba(CREAM, a3), x=950)
            ctext(d, "came later", font(SERIF_I, 24), y + 88, rgba((200, 195, 215), a3), x=950)
    sub(layer, 1, fn)
    # form that gives shape and hides what is behind it
    def form(d, g):
        cx, cy = 640, 500
        hide = eo(seg(t, 40.2, 41.4))
        r = 70
        d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(255, 220, 150, 255))
        if hide > 0:
            sh = 1 + 0.0 * hide
            vase = [(-28, -80), (28, -80), (22, -60), (60, -20), (66, 20), (40, 70), (-40, 70), (-66, 20), (-60, -20), (-22, -60)]
            off = 160 * (1 - hide)
            d.polygon([v for (x, y) in vase for v in P(cx + x * sh + off, cy + y * sh)], fill=(40, 28, 60, 255), outline=GOLD + (255,), width=2 * S)
    sub(layer, seg(t, 38.4, 38.9), form)
    phrase(layer, "whatever gives form also hides what lies behind it", 620, 39.2, size=28, col=CREAM)

PALACE = None
def scene_palace(layer, t):
    def base(d, g):
        g.alpha_composite(PALACE)
    sub(layer, 1, base)
    # pool: looks like polished floor until "the water was real"
    reveal = eo(seg(t, 50.6, 51.3))
    def pool(d, g):
        poly = [v for p in POOL for v in P(*p)]
        d.polygon(poly, fill=(int(178 - 110 * reveal), int(160 - 40 * reveal), int(132 + 70 * reveal), 255))
        for i in range(5):
            y = 485 + i * 24 + 4 * math.sin(t * 2 + i)
            d.line(P(470 - i * 15, y, 810 + i * 15, y), fill=(220, 225, 240, int(40 + 120 * reveal)), width=S)
    sub(layer, 1, pool)
    # Duryodhana walks forward, then falls into the water on "He fell"
    walk = eio(seg(t, 46.8, 53.8))
    fall = eo(seg(t, 53.8, 54.4))
    sc = 0.45 + 0.75 * walk
    fx, fy = 640, 360 + 112 * walk + 60 * fall
    def man(d, g):
        h = 150 * sc
        tilt = 0.7 * fall
        def R(x, y):
            return (fx + x * math.cos(tilt) - y * math.sin(tilt), fy + x * math.sin(tilt) + y * math.cos(tilt))
        body = [R(-22 * sc, -h * 0.75), R(22 * sc, -h * 0.75), R(30 * sc, 0), R(-30 * sc, 0)]
        d.polygon([v for p in body for v in P(*p)], fill=(30, 18, 40, 255))
        hx, hy = R(0, -h * 0.86)
        hr = 14 * sc
        d.ellipse(P(hx - hr, hy - hr, hx + hr, hy + hr), fill=(30, 18, 40, 255))
        crown = [R(-12 * sc, -h * 0.94), R(-8 * sc, -h * 1.06), R(0, -h * 0.98), R(8 * sc, -h * 1.06), R(12 * sc, -h * 0.94)]
        d.polygon([v for p in crown for v in P(*p)], fill=GOLD + (255,))
    sub(layer, 1 - seg(t, 56.8, 57.6), man)
    if 53.8 < t < 57.5:  # splash ripples
        def rip(d, g):
            k = (t - 53.8) / 3.7
            for i in range(3):
                r = 30 + 160 * clamp(k - i * 0.12) ** 0.7
                d.ellipse(P(fx - r, fy - r * 0.25, fx + r, fy + r * 0.25), outline=(230, 240, 255, 255), width=2 * S)
        sub(layer, 1 - (t - 53.8) / 3.7, rip)
    # the edge he was certain about
    def edge(d, g):
        k = eo(seg(t, 55.7, 56.5))
        y = 618
        x0, x1 = 360, 360 + 560 * k
        for x in range(int(x0), int(x1), 24):
            d.line(P(x, y, min(x + 14, x1), y), fill=GOLD + (255,), width=3 * S)
        if k > 0.9:
            ctext(d, "where he was sure the floor ended", font(SERIF_I, 22), y - 20, (255, 236, 190, 255))
    sub(layer, seg(t, 55.6, 55.8) * (1 - seg(t, 57.4, 57.8)), edge)
    def band(d, g):
        d.rectangle(P(0, 0, W, 165), fill=(8, 6, 22, 255))
    sub(layer, 0.7, band)
    def labels(d, g):
        label(d, "MAHĀBHĀRATA  ·  THE PALACE OF MAYA", 1)
    sub(layer, 1, labels)
    # dark overlay + closing lines
    dim = eo(seg(t, 57.6, 58.3))
    if dim > 0:
        def ov(d, g):
            d.rectangle(P(0, 0, W, H), fill=(8, 6, 22, 255))
        sub(layer, 0.78 * dim, ov)
    phrase(layer, "The water was real.  The stone was real.", 130, 50.6, size=34)
    if t > 57.6:
        phrase(layer, "That is Māyā.", 270, 57.8, size=54, italic=False, col=GOLD)
        phrase(layer, "Not a false world —", 360, 59.4, size=38)
        phrase(layer, "a world we are sure we have measured.", 420, 61.2, size=38)

LAND = None
def scene_reality(layer, t):
    def base(d, g):
        g.alpha_composite(LAND)
    sub(layer, 1, base)
    # lines drawn on reality: grid + boundaries, drawn on "lines drawn on it"
    k = eio(seg(t, 69.8, 71.6))
    def lines(d, g):
        n = 9
        for i in range(1, n):
            x = i * W / n
            d.line(P(x, H, x, H - H * clamp(k * 1.4 - i * 0.04)), fill=GOLD + (255,), width=2 * S)
        for j in range(1, 6):
            y = j * H / 6
            d.line(P(0, y, W * clamp(k * 1.4 - j * 0.06), y), fill=GOLD + (255,), width=2 * S)
        bk = eio(seg(t, 70.4, 72.0))
        b = [(120, 520), (300, 470), (420, 540), (560, 480), (700, 520), (880, 450), (1160, 500)]
        m = max(2, int(len(b) * bk))
        if bk > 0:
            d.line([v for p in b[:m] for v in P(*p)], fill=(255, 245, 220, 255), width=3 * S)
    sub(layer, 0.8 if t < 75 else 0.8 + 0.2 * seg(t, 75, 76), lines)
    # pen nib at the end of the line on "that you drew them"
    def pen(d, g):
        x, y = 1160, 500
        d.polygon(P(x, y, x + 18, y - 50, x + 40, y - 42), fill=GOLD + (255,))
        d.line(P(x + 29, y - 46, x + 110, y - 260), fill=CREAM + (255,), width=6 * S)
    sub(layer, eo(seg(t, 76.4, 77.2)), pen)
    def dim(d, g):
        d.rectangle(P(0, 0, W, 300), fill=(8, 6, 22, 255))
    sub(layer, 0.55, dim)
    phrase(layer, "Māyā was never the opposite of reality.", 110, 65.3, size=36, t_out=72.2)
    phrase(layer, "It is reality, with lines drawn on it.", 170, 67.9, size=36, col=GOLD, t_out=72.2)
    if t > 72.6:
        phrase(layer, "The question is not whether the lines are there —", 115, 72.6, size=32)
        phrase(layer, "it is whether you remember that you drew them.", 175, 76.0, size=36, col=GOLD)

def scene_end(layer, t):
    def fn(d, g):
        ctext(d, "M Ā Y Ā", font(SERIF_B, 96), 330, GOLD + (255,))
        ctext(d, "Chapter 6", font(SERIF_I, 32), 410, CREAM + (255,))
    sub(layer, 1, fn)

SCENES = [(0.0, 2.55, scene_title), (2.35, 12.7, scene_rigveda), (12.5, 19.9, scene_upanishads),
          (19.7, 29.2, scene_gaudapada), (29.0, 42.8, scene_origin), (42.6, 63.8, scene_palace),
          (63.6, 78.5, scene_reality), (78.2, DUR, scene_end)]
XF = 0.5

def main():
    global PALACE, LAND, TNOW
    OUT.mkdir(parents=True, exist_ok=True)
    fdir = OUT / "frames"; fdir.mkdir(exist_ok=True)
    bg, PALACE, LAND = night_bg(), palace_art(), landscape_art()
    n = int(DUR * FR)
    only = sys.argv[4:] and [int(x) for x in sys.argv[4].split(",")]
    for i in range(n):
        if only and i not in only:
            continue
        t = TNOW = i / FR
        frame = bg.copy()
        for s0, s1, fn in SCENES:
            a = seg(t, s0, s0 + XF) * (1 - seg(t, s1 - XF, s1))
            if s0 == 0: a = 1 - seg(t, s1 - XF, s1)
            if s1 == DUR: a = seg(t, s0, s0 + XF)
            if a <= 0:
                continue
            lay = new_layer()
            fn(lay, t)
            if a < 1:
                lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(lay)
        cap = new_layer()
        captions(ImageDraw.Draw(cap), t)
        frame.alpha_composite(cap)
        out = frame.convert("RGB")
        fade = seg(t, DUR - 0.6, DUR) + (1 - seg(t, 0, 0.4))
        if fade > 0:
            out = Image.blend(out, Image.new("RGB", out.size), clamp(fade))
        out.resize((W, H), Image.LANCZOS).save(fdir / f"f{i:05d}.png")
    if only:
        return
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FR), "-i", str(fdir / "f%05d.png"),
                    "-i", AUDIO, "-af", f"apad=whole_dur={DUR}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-t", str(DUR), str(OUT / "maya_chapter6.mp4")], check=True)
    print("wrote", OUT / "maya_chapter6.mp4")

TNOW = 0.0
if __name__ == "__main__":
    main()
