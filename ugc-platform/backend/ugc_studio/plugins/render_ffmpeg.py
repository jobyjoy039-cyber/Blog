"""FFmpeg renderer: stills + voice + captions -> platform-ready MP4.

Per scene: the product shot is composed over a blurred fill of itself (so any
image fits any aspect ratio), animated with a Ken Burns push, and crossfaded to
the next scene exactly when that scene's voice line starts. Captions are
word-by-word highlighted ASS subtitles; scene headlines and an "Ad" disclosure
label are drawn on top. Optional music is ducked under the voice and the mix is
loudness-normalised to -14 LUFS (the common target for social platforms).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..domain import RenderInput, RenderOutput, Word
from .base import RenderPlugin

FPS = 30
XFADE = 0.3
SCENE_PAD = 0.25
END_HOLD = 0.8
OVERSCAN = 1.5  # source frames are rendered larger than output for smooth zoom


def _font_path(family: str, weight: str = "Black") -> str | None:
    for query in (f"{family}:style={weight}", f"{family}:bold", family, "DejaVu Sans:bold"):
        try:
            out = subprocess.run(["fc-match", "-f", "%{file}", query], capture_output=True, text=True)
            if out.returncode == 0 and Path(out.stdout).exists():
                return out.stdout
        except FileNotFoundError:
            return None
    return None


def compose_frame(src: str | None, w: int, h: int, title: str, font: str, dest: Path) -> Path:
    """Fit the product shot over a blurred, darkened cover-fill of itself."""
    W, H = int(w * OVERSCAN), int(h * OVERSCAN)
    if src:
        img = Image.open(src).convert("RGB")
        scale = max(W / img.width, H / img.height)
        bg = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
        left, top = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(W // 30))
        bg = Image.blend(bg, Image.new("RGB", (W, H), (12, 12, 16)), 0.35)
        fit = min(W * 0.86 / img.width, H * 0.5 / img.height)
        fg = img.resize((max(1, int(img.width * fit)), max(1, int(img.height * fit))), Image.LANCZOS)
        bg.paste(fg, ((W - fg.width) // 2, int(H * 0.43 - fg.height / 2)))
    else:  # no product images: branded gradient card with the product name
        bg = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(bg)
        for y in range(H):
            t = y / H
            draw.line([(0, y), (W, y)], fill=(int(229 - 120 * t), int(72 - 40 * t), int(77 + 60 * t)))
        fp = _font_path(font)
        size = W // 11
        f = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
        lines, line = [], ""
        for word in title.split():
            if len(line + " " + word) > 14 and line:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        lines.append(line)
        y = H * 0.42 - len(lines) * size * 0.6
        for ln in lines[:4]:
            tw = draw.textlength(ln, font=f)
            draw.text(((W - tw) / 2, y), ln, font=f, fill="white")
            y += size * 1.2
    bg.save(dest, "JPEG", quality=90)
    return dest


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ass_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _chunks(words: list[Word], max_words: int = 3) -> list[list[Word]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or re.search(r"[.!?,;:]$", w.text):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build_ass(data: RenderInput, starts: list[float], total: float, font: str) -> str:
    w, h = data.width, data.height
    vertical = h > w
    cap_size = int(h * (0.045 if vertical else 0.065))
    head_size = int(h * (0.038 if vertical else 0.06))
    tag_size = int(h * 0.022)
    margin_v = int(h * (0.2 if vertical else 0.1))  # above the platform caption/UI area
    head_margin = int(h * (0.12 if vertical else 0.08))
    side = int(w * 0.07)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font} Black,{cap_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{max(3, cap_size // 9)},2,2,{side},{side},{margin_v},1",
        f"Style: Headline,{font} ExtraBold,{head_size},&H00FFFFFF,&H00FFFFFF,&H004D48E5,&H004D48E5,-1,0,0,0,100,100,0,0,3,{head_size // 4},0,8,{side},{side},{head_margin},1",
        f"Style: Tag,{font} SemiBold,{tag_size},&H00FFFFFF,&H00FFFFFF,&H50000000,&H50000000,0,0,0,0,100,100,0,0,3,{tag_size // 3},0,9,{int(w * 0.04)},{int(w * 0.04)},{int(h * 0.04)},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 2,{_ass_time(0)},{_ass_time(total)},Tag,,0,0,0,,Ad",
    ]
    highlight = "&H004DE1FF&"  # warm yellow (ASS colours are BGR)
    for scene, audio, t0 in zip(data.script.scenes, data.scene_audio, starts):
        if scene.on_screen:
            end = t0 + audio.duration + SCENE_PAD
            lines.append(
                f"Dialogue: 1,{_ass_time(t0 + 0.05)},{_ass_time(end)},Headline,,0,0,0,,"
                f"{{\\fad(120,80)\\fscx85\\fscy85\\t(0,180,\\fscx100\\fscy100)}}{_ass_escape(scene.on_screen)}"
            )
        for chunk in _chunks(audio.words):
            for i, word in enumerate(chunk):
                start = t0 + word.start
                end = t0 + (chunk[i + 1].start if i + 1 < len(chunk) else word.end)
                parts = []
                for j, cw in enumerate(chunk):
                    txt = _ass_escape(cw.text)
                    parts.append(f"{{\\c{highlight}\\fscx108\\fscy108}}{txt}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}" if j == i else txt)
                lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{' '.join(parts)}")
    return "\n".join(lines) + "\n"


class FFmpegRenderer(RenderPlugin):
    name = "ffmpeg"
    priority = 10
    license = "FFmpeg LGPL/GPL (invoked as a separate binary)"
    description = "Ken Burns stills, crossfades, word-highlight captions, headlines, ducked music, -14 LUFS."

    def __init__(self, font: str = "Inter", preset: str = "veryfast"):
        self.font = font
        self.preset = preset

    def available(self) -> tuple[bool, str]:
        if not shutil.which("ffmpeg"):
            return False, "ffmpeg not found on PATH"
        return True, ""

    def render(self, data: RenderInput, out_dir: Path) -> RenderOutput:
        out_dir.mkdir(parents=True, exist_ok=True)
        w, h = data.width, data.height
        n = len(data.script.scenes)
        durs = [a.duration + SCENE_PAD for a in data.scene_audio]
        durs[-1] += END_HOLD
        starts = [sum(durs[:i]) for i in range(n)]
        total = sum(durs)

        inputs: list[str] = []
        filters: list[str] = []
        for i, scene in enumerate(data.script.scenes):
            img = data.product.images[scene.image_index] if data.product.images else None
            frame = compose_frame(img, w, h, data.product.title, self.font, out_dir / f"scene_{i}.jpg")
            clip = durs[i] + (XFADE if i < n - 1 else 0)
            frames = max(2, round(clip * FPS))
            zoom = f"1+0.10*on/{frames}" if i % 2 == 0 else f"1.10-0.10*on/{frames}"
            inputs += ["-i", frame.name]
            filters.append(
                f"[{i}:v]zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={w}x{h}:fps={FPS},setsar=1,format=yuv420p[v{i}]"
            )
        prev = "v0"
        for i in range(1, n):
            filters.append(f"[{prev}][v{i}]xfade=transition=fade:duration={XFADE}:offset={starts[i]:.3f}[x{i}]")
            prev = f"x{i}"

        ass = out_dir / "captions.ass"
        ass.write_text(build_ass(data, starts, total, self.font), encoding="utf-8")
        filters.append(f"[{prev}]ass={ass.name}[vout]")

        for i, audio in enumerate(data.scene_audio):
            idx = n + i
            inputs += ["-i", str(Path(audio.path).resolve())]
            filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=mono,apad=whole_dur={durs[i]:.3f}[a{i}]")
        filters.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[voice]")
        if data.music_path:
            m = 2 * n
            inputs += ["-stream_loop", "-1", "-i", str(Path(data.music_path).resolve())]
            filters += [
                "[voice]asplit=2[vmix][vkey]",
                f"[{m}:a]aresample=48000,aformat=channel_layouts=mono,volume=0.35[music]",
                "[music][vkey]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[ducked]",
                "[vmix][ducked]amix=inputs=2:duration=first:normalize=0[mixed]",
            ]
            last_audio = "mixed"
        else:
            last_audio = "voice"
        filters.append(f"[{last_audio}]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")

        script = out_dir / "filtergraph.txt"
        script.write_text(";\n".join(filters), encoding="utf-8")
        video = out_dir / "ad.mp4"
        cmd = [
            "ffmpeg", "-v", "error", "-y", *inputs,
            "-filter_complex_script", script.name,
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", self.preset, "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-movflags", "+faststart",
            video.name,
        ]
        proc = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr[-1500:]}")
        thumb = out_dir / "thumbnail.jpg"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{min(1.0, total / 2):.2f}", "-i", video.name,
             "-frames:v", "1", "-q:v", "3", thumb.name],
            cwd=out_dir, check=True,
        )
        return RenderOutput(video=str(video), thumbnail=str(thumb), duration=round(total, 2))
