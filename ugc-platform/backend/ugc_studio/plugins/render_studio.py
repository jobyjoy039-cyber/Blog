"""Studio renderer: a motion-graphics engine for UGC ads.

Frames are composed in Python (Pillow) and streamed to FFmpeg, which burns in
the captions and encodes. Composing frames ourselves gives sub-pixel smooth
camera moves (FFmpeg's zoompan jitters), real parallax, eased motion and
designed transitions.

Look:
- Brand theme: the accent colour is sampled from the product photos.
- Background: the product photo, blurred and colour-graded toward the accent,
  with a vignette. It moves slower than the foreground (parallax depth).
- Product card: rounded corners and a soft drop shadow, a gentle float, and a
  different eased camera move per scene; the hook opens on a punch-in.
- Transitions: slide-up whip, zoom-through and slide-left, each with a
  synthesized whoosh.
- Overlays: progress bar, headline boxes in the brand colour, word-pop
  captions, an "Ad" disclosure, and an animated "Shop now" button on the CTA.
"""
from __future__ import annotations

import colorsys
import math
import shutil
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .. import timeline as tl
from ..domain import RenderInput, RenderOutput
from . import audio_studio
from .base import RenderPlugin
from .brain_local import _price
from .render_ffmpeg import _ass_escape, _ass_time, _chunks, _font_path

FPS = 30
DEFAULT_ACCENT = (229, 72, 77)
MOVES = ["push", "pan_left", "pull", "pan_right", "rise"]
TRANSITIONS = ["slide_up", "zoom", "slide_left"]


# --- easing -------------------------------------------------------------------
def ease_io(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x: float, k: float = 1.6) -> float:
    x = min(1.0, max(0.0, x))
    return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2


# --- theme --------------------------------------------------------------------
@dataclass
class Theme:
    accent: tuple[int, int, int]

    @property
    def ass_accent(self) -> str:  # ASS colours are &HAABBGGRR
        r, g, b = self.accent
        return f"&H00{b:02X}{g:02X}{r:02X}"


def pick_accent(images: list[str]) -> tuple[int, int, int]:
    """Most vivid colour that covers a meaningful share of the product photos."""
    best, best_score = None, 0.0
    for path in images[:3]:
        try:
            img = Image.open(path).convert("RGB")
        except OSError:
            continue
        img.thumbnail((96, 96))
        q = img.quantize(colors=10)
        palette = q.getpalette()
        total = img.width * img.height
        for count, idx in q.getcolors() or []:
            r, g, b = palette[idx * 3: idx * 3 + 3]
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.3 or v < 0.3:
                continue  # skip whites, greys, blacks
            score = s * v * min(1.0, (count / total) * 8)
            if score > best_score:
                best, best_score = (r, g, b), score
    if best is None:
        return DEFAULT_ACCENT
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in best))
    r, g, b = colorsys.hsv_to_rgb(h, max(0.55, s), min(0.82, max(0.55, v)))  # legible behind white text
    return int(r * 255), int(g * 255), int(b * 255)


# --- layers -------------------------------------------------------------------
def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, int(img.width * s + 1)), max(h, int(img.height * s + 1))), Image.BILINEAR)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def make_background(src: str | None, w: int, h: int, theme: Theme) -> Image.Image:
    bw, bh = int(w * 1.3), int(h * 1.3)
    if src:
        bg = _cover(Image.open(src).convert("RGB"), bw, bh).filter(ImageFilter.GaussianBlur(max(8, bw // 22)))
    else:
        bg = Image.new("RGB", (bw, bh), theme.accent)
    dark = tuple(int(c * 0.22) for c in theme.accent)
    grade = Image.linear_gradient("L").resize((bw, bh))  # 0 at top -> 255 at bottom
    tint = Image.composite(Image.new("RGB", (bw, bh), (8, 8, 12)), Image.new("RGB", (bw, bh), dark), grade)
    bg = Image.blend(bg, tint, 0.7)
    vignette = Image.radial_gradient("L").resize((bw, bh)).point(lambda p: int(min(255, p * 1.15)))
    return Image.composite(Image.new("RGB", (bw, bh), (0, 0, 0)), bg, vignette.point(lambda p: int(p * 0.55)))


def make_card(src: str | None, w: int, h: int, title: str, theme: Theme, font: str) -> Image.Image:
    """Product photo with rounded corners and a soft drop shadow (RGBA)."""
    box_w, box_h = int(w * 0.8 * 1.15), int(h * (0.48 if h > w else 0.62) * 1.15)  # 15% headroom for zoom
    if src:
        img = Image.open(src).convert("RGB")
        s = min(box_w / img.width, box_h / img.height)
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
    else:  # no photo: typographic card
        img = Image.new("RGB", (box_w, int(box_w * 0.75)), theme.accent)
        d = ImageDraw.Draw(img)
        fp = _font_path(font)
        size = img.width // 9
        f = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
        words, lines, line = title.split(), [], ""
        for word in words:
            if line and len(line + " " + word) > 16:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        lines.append(line)
        y = img.height / 2 - len(lines[:3]) * size * 0.6
        for ln in lines[:3]:
            d.text(((img.width - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill="white")
            y += size * 1.2
    radius = max(12, int(min(img.size) * 0.06))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    pad = int(min(img.size) * 0.12)
    card = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("L", card.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        (pad, pad + pad // 3, pad + img.width, pad + img.height + pad // 3), radius, fill=150)
    shadow = shadow.filter(ImageFilter.GaussianBlur(pad // 2.5))
    card.paste(Image.new("RGBA", card.size, (0, 0, 0, 255)), (0, 0), shadow)
    card.paste(img, (pad, pad), mask)
    return card


# --- per-frame composition (NumPy + OpenCV for speed, sub-pixel smooth) ------
def _blend_rgba(frame: np.ndarray, layer: np.ndarray, scale: float, cx: float, cy: float) -> None:
    """Scale an RGBA layer about its centre, place it at (cx, cy) and alpha-blend
    it into `frame` in place. Only the covered region is touched."""
    h, w = frame.shape[:2]
    lh, lw = layer.shape[:2]
    x0, y0 = int(math.floor(cx - lw * scale / 2)), int(math.floor(cy - lh * scale / 2))
    x1, y1 = int(math.ceil(cx + lw * scale / 2)), int(math.ceil(cy + lh * scale / 2))
    cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    m = np.float32([[scale, 0, cx - lw * scale / 2 - cx0], [0, scale, cy - lh * scale / 2 - cy0]])
    warped = cv2.warpAffine(layer, m, (cx1 - cx0, cy1 - cy0), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    alpha = warped[..., 3].astype(np.float32) * (1 / 255)
    roi = frame[cy0:cy1, cx0:cx1]
    roi[:] = cv2.blendLinear(np.ascontiguousarray(warped[..., :3]), np.ascontiguousarray(roi), alpha, 1 - alpha)


def make_button(text: str, w: int, h: int, theme: Theme, font: str) -> np.ndarray:
    fp = _font_path(font, "ExtraBold")
    f = ImageFont.truetype(fp, int(min(w, h) * 0.052)) if fp else ImageFont.load_default()
    fs = getattr(f, "size", 20)
    tw = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=f)
    bw, bh = int(tw + fs * 2.2), int(fs * 2.1)
    pad = int(fs * 0.6)
    img = Image.new("RGBA", (bw + 2 * pad, bh + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle((pad, pad + fs // 4, pad + bw, pad + bh + fs // 4), bh // 2, fill=110)
    img.paste(Image.new("RGBA", img.size, (0, 0, 0, 255)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(fs // 4)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad, pad, pad + bw, pad + bh), bh // 2, fill=(*theme.accent, 255))
    d.text((pad + bw / 2, pad + bh / 2), text, font=f, fill="white", anchor="mm")
    return np.asarray(img)


class SceneRenderer:
    def __init__(self, bg: Image.Image, card: Image.Image, move: str, duration: float, w: int, h: int,
                 hook: bool, button: np.ndarray | None):
        self.bg = np.asarray(bg.convert("RGB"))
        self.card = np.asarray(card.convert("RGBA"))
        self.move, self.duration, self.w, self.h = move, duration, w, h
        self.hook, self.button = hook, button
        self.base = 1 / 1.15  # card headroom

    def frame(self, t: float, zoom_extra: float = 1.0) -> np.ndarray:
        """t is local time, starting half a transition before the scene's cut."""
        w, h = self.w, self.h
        since_cut = t - tl.TRANSITION / 2
        p = ease_io(t / max(self.duration, 0.01))
        scale, dx, dy = 1.0, 0.0, 0.0
        if self.move == "push":
            scale = 1.0 + 0.07 * p
        elif self.move == "pull":
            scale = 1.07 - 0.07 * p
        elif self.move == "pan_left":
            dx, scale = (0.5 - p) * w * 0.07, 1.03
        elif self.move == "pan_right":
            dx, scale = (p - 0.5) * w * 0.07, 1.03
        elif self.move == "rise":
            dy, scale = (0.5 - p) * h * 0.04, 1.02 + 0.03 * p
        if self.hook:  # punch-in: product starts big and snaps into place
            scale *= 1.0 + 0.2 * (1 - ease_out_back(since_cut / 0.45, 1.2))
        scale *= zoom_extra
        float_y = math.sin(t * 1.7) * h * 0.004

        # background: slower and opposite, for parallax depth
        bh, bw = self.bg.shape[:2]
        bs = (w / bw) * 1.3 * (1 + (scale - 1) * 0.4)
        m = np.float32([[bs, 0, w / 2 - bs * (bw / 2 - dx * 0.35)], [0, bs, h / 2 - bs * (bh / 2 - dy * 0.35)]])
        frame = cv2.warpAffine(self.bg, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        cta = self.button is not None
        _blend_rgba(frame, self.card, self.base * scale * (0.86 if cta else 1.0),
                    w / 2 + dx, h * (0.40 if cta else 0.43) + dy + float_y)
        if cta:
            appear = ease_out_back((since_cut - 0.25) / 0.45)
            if appear > 0.01:
                pulse = 1 + 0.025 * math.sin((since_cut - 0.7) * 5.5) if since_cut > 0.7 else 1.0
                _blend_rgba(frame, self.button, appear * pulse, w / 2, h * 0.70)
        return frame


def blend_transition(a: np.ndarray, b: np.ndarray, kind: str, p: float) -> np.ndarray:
    p = ease_io(p)
    h, w = a.shape[:2]
    if kind == "slide_up":
        k = int(round(p * h))
        return np.concatenate([a[k:], b[: k]], axis=0) if 0 < k < h else (a if k <= 0 else b)
    if kind == "slide_left":
        k = int(round(p * w))
        return np.concatenate([a[:, k:], b[:, :k]], axis=1) if 0 < k < w else (a if k <= 0 else b)
    return cv2.addWeighted(a, 1 - p, b, p, 0)  # zoom-through: scaling done by the caller


def build_ass(data: RenderInput, line: tl.Timeline, theme: Theme, font: str) -> str:
    w, h = data.width, data.height
    vertical = h > w
    cap = int(h * (0.046 if vertical else 0.066))
    head = int(h * (0.036 if vertical else 0.058))
    tag = int(h * 0.02)
    margin_v = int(h * (0.215 if vertical else 0.1))
    head_margin = int(h * (0.105 if vertical else 0.07))
    side = int(w * 0.07)
    out = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font} Black,{cap},&H00FFFFFF,&H00FFFFFF,&H00101010,&H78000000,-1,0,0,0,100,100,0.5,0,1,{max(3, cap // 8)},{max(2, cap // 18)},2,{side},{side},{margin_v},1",
        f"Style: Headline,{font} ExtraBold,{head},&H00FFFFFF,&H00FFFFFF,{theme.ass_accent},{theme.ass_accent},-1,0,0,0,100,100,0.3,0,3,{head // 3},0,8,{side},{side},{head_margin},1",
        f"Style: Tag,{font} SemiBold,{tag},&H00FFFFFF,&H00FFFFFF,&H64000000,&H64000000,0,0,0,0,100,100,0,0,3,{tag // 3},0,9,{int(w * 0.04)},{int(w * 0.04)},{int(h * 0.035)},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 3,{_ass_time(0)},{_ass_time(line.total)},Tag,,0,0,0,,Ad",
    ]
    hi = "&H004DE1FF&"  # warm yellow highlight reads on any background
    for i, (scene, audio) in enumerate(zip(data.script.scenes, data.scene_audio)):
        s0, s1 = line.starts[i], line.starts[i] + line.durations[i]
        if scene.on_screen and scene.kind != "cta":
            anim = "" if s0 == 0 else "\\fad(90,0)\\fscx70\\fscy70\\t(0,200,\\fscx104\\fscy104)\\t(200,280,\\fscx100\\fscy100)"
            out.append(f"Dialogue: 2,{_ass_time(s0 + (0 if s0 == 0 else 0.08))},{_ass_time(s1 - 0.12)},Headline,,0,0,0,,"
                       f"{{{anim}}}{_ass_escape(scene.on_screen)}")
        v0 = line.voice_at[i]
        for chunk in _chunks(audio.words):
            for j, word in enumerate(chunk):
                start = v0 + word.start
                end = v0 + (chunk[j + 1].start if j + 1 < len(chunk) else word.end + 0.12)
                parts = []
                for k, cw in enumerate(chunk):
                    txt = _ass_escape(cw.text)
                    if k == j:
                        parts.append(f"{{\\c{hi}\\fscx88\\fscy88\\t(0,90,\\fscx112\\fscy112)\\t(90,170,\\fscx106\\fscy106)}}"
                                     f"{txt}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}")
                    else:
                        parts.append(txt)
                out.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{' '.join(parts)}")
    return "\n".join(out) + "\n"


class StudioRenderer(RenderPlugin):
    name = "studio"
    priority = 5
    license = "MIT (this project); FFmpeg invoked as a separate binary"
    description = "Motion-graphics engine: brand theme, parallax, punch-in hook, whoosh transitions, CTA button, studio audio."

    def __init__(self, font: str = "Inter", preset: str = "fast", crf: int = 19):
        self.font, self.preset, self.crf = font, preset, crf

    def available(self) -> tuple[bool, str]:
        return (True, "") if shutil.which("ffmpeg") else (False, "ffmpeg not found on PATH")

    def render(self, data: RenderInput, out_dir: Path) -> RenderOutput:
        out_dir.mkdir(parents=True, exist_ok=True)
        w, h = data.width, data.height
        scenes = data.script.scenes
        line = tl.plan([a.duration for a in data.scene_audio])
        theme = Theme(pick_accent(data.product.images))
        seed = zlib.crc32(data.script.title.encode()) % 10_000  # stable across runs

        # --- audio ---
        sfx = audio_studio.sfx_track(
            line.total, line.starts[1:],
            [s + 0.08 for s, sc in zip(line.starts, scenes) if sc.on_screen and sc.kind != "cta"],
            line.starts[-1] + 0.3 if scenes[-1].kind == "cta" else None,
            out_dir / "sfx.wav", seed,
        )
        audio = audio_studio.master(
            [(a.path, t) for a, t in zip(data.scene_audio, line.voice_at)], line.total,
            out_dir / "mix.wav", music=data.music_path, sfx=str(sfx),
        )

        # --- picture ---
        imgs = data.product.images
        price = _price(data.product)
        renderers = []
        for i, sc in enumerate(scenes):
            src = imgs[sc.image_index] if imgs else None
            button = None
            if sc.kind == "cta":
                button = make_button(f"Shop now  ·  {price}" if price else "Shop now", w, h, theme, self.font)
            renderers.append(SceneRenderer(
                make_background(src, w, h, theme), make_card(src, w, h, data.product.title, theme, self.font),
                MOVES[i % len(MOVES)], line.durations[i] + tl.TRANSITION, w, h, hook=(i == 0), button=button,
            ))

        ass = out_dir / "captions.ass"
        ass.write_text(build_ass(data, line, theme, self.font), encoding="utf-8")
        video = out_dir / "ad.mp4"
        log = open(out_dir / "ffmpeg.log", "w")
        proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
             "-i", str(audio),
             "-vf", f"ass={ass.name},format=yuv420p",
             "-map", "0:v", "-map", "1:a", "-shortest",
             "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf), "-profile:v", "high",
             "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", video.name],
            cwd=out_dir, stdin=subprocess.PIPE, stderr=log,
        )
        bar_h = max(4, int(h * 0.0055))
        half = tl.TRANSITION / 2
        try:
            for n in range(int(round(line.total * FPS))):
                t = n / FPS
                i = line.scene_at(t)
                local = t - line.starts[i] + half
                frame = renderers[i].frame(local)
                # transition into the next scene, centred on the boundary
                if i + 1 < len(scenes) and t > line.starts[i + 1] - half:
                    p = (t - (line.starts[i + 1] - half)) / tl.TRANSITION
                    kind = TRANSITIONS[i % len(TRANSITIONS)]
                    nxt = renderers[i + 1].frame(t - line.starts[i + 1] + half,
                                                 zoom_extra=(1.12 - 0.12 * ease_io(p)) if kind == "zoom" else 1.0)
                    if kind == "zoom":
                        frame = renderers[i].frame(local, zoom_extra=1 + 0.18 * ease_io(p))
                    frame = blend_transition(frame, nxt, kind, p)
                elif i > 0 and t < line.starts[i] + half:
                    p = (t - (line.starts[i] - half)) / tl.TRANSITION
                    kind = TRANSITIONS[(i - 1) % len(TRANSITIONS)]
                    prev = renderers[i - 1].frame(t - line.starts[i - 1] + half,
                                                  zoom_extra=(1 + 0.18 * ease_io(p)) if kind == "zoom" else 1.0)
                    cur = renderers[i].frame(local, zoom_extra=(1.12 - 0.12 * ease_io(p)) if kind == "zoom" else 1.0)
                    frame = blend_transition(prev, cur, kind, p)
                frame[:bar_h] = (255, 255, 255)
                frame[:bar_h, : int(w * t / line.total)] = theme.accent
                proc.stdin.write(np.ascontiguousarray(frame).tobytes())
            proc.stdin.close()
            code = proc.wait(timeout=600)
        finally:
            log.close()
            if proc.poll() is None:
                proc.kill()
        if code != 0:
            raise RuntimeError("ffmpeg encode failed: " + (out_dir / "ffmpeg.log").read_text()[-1200:])

        thumb = out_dir / "thumbnail.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.2", "-i", video.name, "-frames:v", "1", "-q:v", "2", thumb.name],
                       cwd=out_dir, check=True)
        return RenderOutput(video=str(video), thumbnail=str(thumb), duration=round(line.total, 2))
