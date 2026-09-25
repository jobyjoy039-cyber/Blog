package com.productvideostudio.analysis;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapRegionDecoder;
import android.graphics.Matrix;
import android.graphics.Rect;
import android.media.ExifInterface;

import java.io.IOException;

/** Memory-conscious image decoding that honours EXIF orientation. */
public final class Bitmaps {
    private Bitmaps() {}

    /** Pixel size after EXIF rotation. */
    public static int[] size(String path) {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(path, o);
        int rot = rotation(path);
        return rot == 90 || rot == 270 ? new int[]{o.outHeight, o.outWidth} : new int[]{o.outWidth, o.outHeight};
    }

    public static int rotation(String path) {
        try {
            ExifInterface exif = new ExifInterface(path);
            switch (exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                case ExifInterface.ORIENTATION_ROTATE_90: return 90;
                case ExifInterface.ORIENTATION_ROTATE_180: return 180;
                case ExifInterface.ORIENTATION_ROTATE_270: return 270;
                default: return 0;
            }
        } catch (IOException | RuntimeException e) {
            return 0;
        }
    }

    /** Decodes the whole image so that its longer side is at most {@code maxSide}. */
    public static Bitmap decode(String path, int maxSide) {
        return decodeRegion(path, new float[]{0, 0, 1, 1}, maxSide);
    }

    /**
     * Decodes a region (normalized l,t,r,b in the upright image) at up to {@code maxSide} pixels,
     * reading only the pixels needed so macro crops stay sharp without loading the full photo.
     */
    public static Bitmap decodeRegion(String path, float[] crop, int maxSide) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(path, bounds);
        int rawW = bounds.outWidth, rawH = bounds.outHeight;
        if (rawW <= 0 || rawH <= 0) return null;
        int rot = rotation(path);

        // Map the upright crop into raw (un-rotated) coordinates.
        float l = crop[0], t = crop[1], r = crop[2], b = crop[3];
        float rl, rt, rr, rb;
        switch (rot) {
            case 90: rl = t; rt = 1 - r; rr = b; rb = 1 - l; break;
            case 180: rl = 1 - r; rt = 1 - b; rr = 1 - l; rb = 1 - t; break;
            case 270: rl = 1 - b; rt = l; rr = 1 - t; rb = r; break;
            default: rl = l; rt = t; rr = r; rb = b;
        }
        Rect region = new Rect(
                clamp(Math.round(rl * rawW), 0, rawW - 1), clamp(Math.round(rt * rawH), 0, rawH - 1),
                clamp(Math.round(rr * rawW), 1, rawW), clamp(Math.round(rb * rawH), 1, rawH));
        if (region.width() < 2 || region.height() < 2) region.set(0, 0, rawW, rawH);

        int longest = Math.max(region.width(), region.height());
        int sample = 1;
        while (longest / (sample * 2) >= maxSide) sample *= 2;
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inSampleSize = sample;
        o.inPreferredConfig = Bitmap.Config.ARGB_8888;

        Bitmap bmp = null;
        boolean full = region.left == 0 && region.top == 0 && region.right == rawW && region.bottom == rawH;
        if (!full) {
            try {
                BitmapRegionDecoder dec = BitmapRegionDecoder.newInstance(path, false);
                bmp = dec.decodeRegion(region, o);
                dec.recycle();
            } catch (IOException | RuntimeException e) {
                bmp = null;
            }
        }
        if (bmp == null) {
            Bitmap whole = BitmapFactory.decodeFile(path, o);
            if (whole == null) return null;
            if (full) {
                bmp = whole;
            } else {
                int x = region.left / sample, y = region.top / sample;
                int w = Math.max(1, Math.min(whole.getWidth() - x, region.width() / sample));
                int h = Math.max(1, Math.min(whole.getHeight() - y, region.height() / sample));
                bmp = Bitmap.createBitmap(whole, x, y, w, h);
                if (bmp != whole) whole.recycle();
            }
        }

        float scale = Math.min(1f, maxSide / (float) Math.max(bmp.getWidth(), bmp.getHeight()));
        if (rot != 0 || scale < 1f) {
            Matrix m = new Matrix();
            m.postScale(scale, scale);
            m.postRotate(rot);
            Bitmap t2 = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);
            if (t2 != bmp) bmp.recycle();
            bmp = t2;
        }
        if (bmp.getConfig() != Bitmap.Config.ARGB_8888) {
            Bitmap c = bmp.copy(Bitmap.Config.ARGB_8888, false);
            bmp.recycle();
            bmp = c;
        }
        return bmp;
    }

    static int clamp(int v, int lo, int hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    /** Fast approximate blur by downscaling, box blurring and scaling back to {@code outSize}. */
    public static Bitmap blurred(Bitmap src, int outLongSide, int radius) {
        int small = 48;
        float s = small / (float) Math.max(src.getWidth(), src.getHeight());
        int w = Math.max(2, Math.round(src.getWidth() * s)), h = Math.max(2, Math.round(src.getHeight() * s));
        Bitmap tiny = Bitmap.createScaledBitmap(src, w, h, true);
        int[] px = new int[w * h];
        tiny.getPixels(px, 0, w, 0, 0, w, h);
        tiny.recycle();
        for (int pass = 0; pass < 3; pass++) px = boxBlurRgb(px, w, h, radius);
        Bitmap out = Bitmap.createBitmap(px, w, h, Bitmap.Config.ARGB_8888);
        float up = outLongSide / (float) Math.max(w, h);
        Bitmap big = Bitmap.createScaledBitmap(out, Math.round(w * up), Math.round(h * up), true);
        if (big != out) out.recycle();
        return big;
    }

    static int[] boxBlurRgb(int[] px, int w, int h, int r) {
        int[] tmp = new int[px.length];
        int[] out = new int[px.length];
        for (int pass = 0; pass < 2; pass++) {
            int[] src = pass == 0 ? px : tmp;
            int[] dst = pass == 0 ? tmp : out;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rs = 0, gs = 0, bs = 0, n = 0;
                    for (int k = -r; k <= r; k++) {
                        int xx = pass == 0 ? clamp(x + k, 0, w - 1) : x;
                        int yy = pass == 0 ? y : clamp(y + k, 0, h - 1);
                        int c = src[yy * w + xx];
                        rs += (c >> 16) & 0xFF; gs += (c >> 8) & 0xFF; bs += c & 0xFF; n++;
                    }
                    dst[y * w + x] = 0xFF000000 | ((rs / n) << 16) | ((gs / n) << 8) | (bs / n);
                }
            }
        }
        return out;
    }
}
