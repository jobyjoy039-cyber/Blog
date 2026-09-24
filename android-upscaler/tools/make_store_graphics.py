"""Builds the Play Store feature graphic and captioned phone screenshots.

Usage: python3 tools/make_store_graphics.py <samples dir>
Needs store/screenshots/*.png from screenshots/run.sh, plus onnxruntime and Pillow.
"""
import os
import sys

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
STORE = os.path.join(ROOT, 'store')
NAVY = (24, 32, 56)
ACCENT = (120, 160, 255)
FONTS = '/usr/share/fonts/truetype/'


def font(size, bold=True):
    for f in (['noto/NotoSans-Bold.ttf', 'dejavu/DejaVuSans-Bold.ttf'] if bold
              else ['noto/NotoSans-Regular.ttf', 'dejavu/DejaVuSans.ttf']):
        if os.path.exists(FONTS + f):
            return ImageFont.truetype(FONTS + f, size)
    return ImageFont.load_default()


def upscale(img, model='realesr-general-x4v3'):
    s = ort.InferenceSession(os.path.join(ROOT, 'assets', model + '.onnx'))
    x = np.asarray(img.convert('RGB'), np.float32).transpose(2, 0, 1)[None] / 255
    y = s.run(None, {'input': x})[0][0]
    return Image.fromarray((np.clip(y, 0, 1) * 255).round().astype(np.uint8).transpose(1, 2, 0))


def feature_graphic(samples):
    W, H = 1024, 500
    im = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(im)
    # Right side: real before/after of the same low-res photo.
    low = Image.open(os.path.join(samples, 'chelsea.jpg')).convert('RGB')
    box = (60, 10, 200, 150)  # cat's face in the 240x160 sample
    crop = low.crop(box)
    ai = upscale(crop).resize((420, 420), Image.LANCZOS)
    before = crop.resize((420, 420), Image.NEAREST)
    card = before.copy()
    card.paste(ai.crop((210, 0, 420, 420)), (210, 0))
    cd = ImageDraw.Draw(card)
    cd.rectangle([207, 0, 212, 420], fill='white')
    cd.ellipse([186, 186, 234, 234], fill='white')
    cd.polygon([(206, 198), (192, 210), (206, 222)], fill=NAVY)
    cd.polygon([(214, 198), (228, 210), (214, 222)], fill=NAVY)
    mask = Image.new('L', card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 419, 419], radius=28, fill=255)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([556, 52, 976, 472], radius=28, fill=(0, 0, 0, 140))
    im = Image.alpha_composite(im.convert('RGBA'), sh.filter(ImageFilter.GaussianBlur(14))).convert('RGB')
    im.paste(card, (560, 40), mask)
    d = ImageDraw.Draw(im)
    for text, xy in (('BEFORE', (580, 56)), ('AFTER', (900, 56))):
        f = font(20)
        tw = d.textlength(text, font=f)
        x = xy[0] if text == 'BEFORE' else 560 + 420 - 20 - tw
        d.rounded_rectangle([x - 10, xy[1] - 4, x + tw + 10, xy[1] + 26], radius=8, fill=(0, 0, 0, 160))
        d.text((x, xy[1]), text, font=f, fill='white')
    d.text((56, 120), 'PixelBoost', font=font(70), fill='white')
    d.text((60, 215), 'AI photo upscaler', font=font(34, False), fill=ACCENT)
    y = 290
    for line in ('Sharper, bigger photos: 2x, 4x, 4K, 8K', 'Works offline. Nothing is uploaded.'):
        d.text((60, y), '•  ' + line, font=font(24, False), fill=(220, 226, 240))
        y += 42
    im.save(os.path.join(STORE, 'feature-graphic-1024x500.png'))


CAPTIONS = {
    '1-choose.png': ('Pick any photo', 'or drawing from your gallery'),
    '2-result.png': ('Get the detail back', 'AI rebuilds edges and texture'),
    '3-progress.png': ('Go up to 4K or 8K', 'big jobs run in two passes'),
    '4-4k-result.png': ('A tiny photo, now 4K', '240 × 160  →  3240 × 2160'),
    '5-best-quality.png': ('Best-quality mode', 'for your favourite shots'),
    '6-about.png': ('100% private', 'processing never leaves your phone'),
}


def framed_screenshots():
    src = os.path.join(STORE, 'screenshots')
    out = os.path.join(STORE, 'phone-screenshots')
    os.makedirs(out, exist_ok=True)
    W, H = 1080, 1920
    for name, (title, sub) in CAPTIONS.items():
        shot = Image.open(os.path.join(src, name)).convert('RGB')
        canvas = Image.new('RGB', (W, H), NAVY)
        d = ImageDraw.Draw(canvas)
        f1, f2 = font(76), font(42, False)
        d.text(((W - d.textlength(title, font=f1)) / 2, 90), title, font=f1, fill='white')
        d.text(((W - d.textlength(sub, font=f2)) / 2, 200), sub, font=f2, fill=ACCENT)
        # Phone-like frame holding the real screenshot.
        sw = 840
        sh_ = int(shot.height * sw / shot.width)
        top = 320
        shot = shot.resize((sw, sh_), Image.LANCZOS)
        x = (W - sw) // 2
        frame = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(frame)
        fd.rounded_rectangle([x - 22, top - 22, x + sw + 22, top + sh_ + 22], radius=70, fill=(10, 12, 20, 255))
        canvas = Image.alpha_composite(canvas.convert('RGBA'), frame).convert('RGB')
        m = Image.new('L', (sw, sh_), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh_ - 1], radius=50, fill=255)
        canvas.paste(shot, (x, top), m)
        canvas.save(os.path.join(out, name))


if __name__ == '__main__':
    feature_graphic(sys.argv[1])
    framed_screenshots()
