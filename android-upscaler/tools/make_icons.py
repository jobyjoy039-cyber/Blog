"""Draws the PixelBoost launcher icons (legacy + adaptive) and the 512px Play Store icon."""
import os
from PIL import Image, ImageDraw, ImageFilter

BG = (24, 32, 56)
N = 1024  # working resolution


def scene(size):
    """A small landscape: sky gradient, sun, two mountains."""
    im = Image.new('RGB', (size, size))
    d = ImageDraw.Draw(im)
    for y in range(size):
        t = y / size
        d.line([(0, y), (size, y)], fill=(int(70 + 90 * t), int(140 + 60 * t), int(255 - 40 * t)))
    s = size / 100
    d.ellipse([62 * s, 16 * s, 84 * s, 38 * s], fill=(255, 196, 70))
    d.polygon([(-5 * s, 100 * s), (35 * s, 42 * s), (75 * s, 100 * s)], fill=(46, 96, 170))
    d.polygon([(30 * s, 100 * s), (68 * s, 52 * s), (110 * s, 100 * s)], fill=(30, 70, 135))
    d.polygon([(35 * s, 42 * s), (27 * s, 54 * s), (43 * s, 54 * s)], fill=(235, 242, 255))
    d.rectangle([0, 86 * s, size, size], fill=(40, 150, 110))
    return im


def foreground(size):
    """Before/after card: pixelated left half, smooth right half, slider in the middle."""
    card = int(size * 0.62)
    sm = scene(card)
    px = sm.resize((10, 10), Image.BILINEAR).resize((card, card), Image.NEAREST)
    comp = sm.copy()
    comp.paste(px.crop((0, 0, card // 2, card)), (0, 0))
    mask = Image.new('L', (card, card), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card - 1, card - 1], radius=card // 7, fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    o = (size - card) // 2
    # soft shadow
    sh = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([o, o + size // 60, o + card, o + card + size // 60],
                                         radius=card // 7, fill=(0, 0, 0, 110))
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(size // 60)))
    out.paste(comp, (o, o), mask)
    d = ImageDraw.Draw(out)
    cx = size // 2
    w = max(2, size // 90)
    d.rectangle([cx - w, o - size // 40, cx + w, o + card + size // 40], fill=(255, 255, 255, 255))
    r = size // 16
    d.ellipse([cx - r, size // 2 - r, cx + r, size // 2 + r], fill=(255, 255, 255, 255))
    a = r // 2
    d.polygon([(cx - a // 3, size // 2 - a), (cx - a // 3 - a, size // 2), (cx - a // 3, size // 2 + a)], fill=BG)
    d.polygon([(cx + a // 3, size // 2 - a), (cx + a // 3 + a, size // 2), (cx + a // 3, size // 2 + a)], fill=BG)
    return out


def full_icon(size, rounded, scale=1.3):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    bg = Image.new('RGBA', (size, size), BG + (255,))
    if rounded:
        m = Image.new('L', (size, size), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=255)
        im.paste(bg, (0, 0), m)
    else:
        im = bg
    # The foreground is designed on the 108dp adaptive canvas; scale it up for the legacy icon.
    fg = foreground(N).resize((int(size * scale), int(size * scale)), Image.LANCZOS)
    o = (size - fg.width) // 2
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    layer.paste(fg, (o, o), fg)
    return Image.alpha_composite(im, layer)


if __name__ == '__main__':
    root = os.path.join(os.path.dirname(__file__), '..')
    dens = {'mdpi': 1, 'hdpi': 1.5, 'xhdpi': 2, 'xxhdpi': 3, 'xxxhdpi': 4}
    big_fg = foreground(N)
    legacy = full_icon(N, True)
    for k, f in dens.items():
        d = os.path.join(root, 'res', f'mipmap-{k}')
        os.makedirs(d, exist_ok=True)
        legacy.resize((int(48 * f), int(48 * f)), Image.LANCZOS).save(os.path.join(d, 'ic_launcher.png'))
        big_fg.resize((int(108 * f), int(108 * f)), Image.LANCZOS).save(os.path.join(d, 'ic_launcher_foreground.png'))
    full_icon(512, False, 1.12).convert('RGBA').save(os.path.join(root, 'store', 'icon-512.png'))
