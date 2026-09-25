package com.productvideostudio.render;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffXfermode;
import android.graphics.Rect;
import android.util.Log;

import com.productvideostudio.analysis.Bitmaps;
import com.productvideostudio.analysis.Segmenter;
import com.productvideostudio.model.Enums.Layout;
import com.productvideostudio.model.ImageAnalysis;
import com.productvideostudio.model.Storyboard.Scene;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/** GPU textures for one scene: the (cut-out) product or photo crop and a blurred backdrop. */
final class SceneAssets {
    private static final String TAG = "SceneAssets";

    Gl.Texture product;
    Gl.Texture backdrop;
    /** One texture per {@code scene.texts} entry. */
    Gl.Texture[] texts;
    /** Shared brand logo (owned by the renderer, not released here). */
    Gl.Texture logo;
    /** Pixel aspect (w/h) of the product crop. */
    float aspect = 1f;
    boolean cutout;
    /** Where the product touches the floor, as v (0 top .. 1 bottom) within the product texture. */
    float contactV = 0.95f;

    static SceneAssets load(Scene sc, File imageFile, ImageAnalysis a, int maxTex) {
        SceneAssets s = new SceneAssets();
        String path = imageFile.getAbsolutePath();
        int side = sc.layout == Layout.FULL_BLEED ? 2048 : 1600;
        Bitmap crop = Bitmaps.decodeRegion(path, sc.crop, Math.min(side, maxTex));
        if (crop == null) crop = Bitmap.createBitmap(new int[]{0xFF808080}, 1, 1, Bitmap.Config.ARGB_8888);
        s.aspect = crop.getWidth() / (float) crop.getHeight();

        if (sc.layout == Layout.STUDIO) {
            Bitmap cut = cutOut(crop, s);
            if (cut != null) {
                crop.recycle();
                crop = cut;
                s.cutout = true;
            }
        }
        s.product = Gl.upload(crop, true, maxTex);

        if (!s.cutout) {
            Bitmap whole = Bitmaps.decode(path, 256);
            if (whole != null) {
                Bitmap blurred = Bitmaps.blurred(whole, 256, 3);
                whole.recycle();
                s.backdrop = Gl.upload(blurred, false, maxTex);
                blurred.recycle();
            }
        }
        crop.recycle();
        return s;
    }

    /** Removes a plain background. Returns null (keep the photo as a card) if the result looks unreliable. */
    private static Bitmap cutOut(Bitmap crop, SceneAssets out) {
        int w = crop.getWidth(), h = crop.getHeight();
        float s = Math.min(1f, 420f / Math.max(w, h));
        int mw = Math.max(8, Math.round(w * s)), mh = Math.max(8, Math.round(h * s));
        Bitmap small = Bitmap.createScaledBitmap(crop, mw, mh, true);
        int[] px = new int[mw * mh];
        small.getPixels(px, 0, mw, 0, 0, mw, mh);
        if (small != crop) small.recycle();

        // Background color and noise from the crop's border.
        List<Integer> border = new ArrayList<>();
        int bw = Math.max(2, Math.min(mw, mh) / 25);
        for (int y = 0; y < mh; y++) {
            for (int x = 0; x < mw; x++) {
                if (x < bw || y < bw || x >= mw - bw || y >= mh - bw) border.add(px[y * mw + x]);
            }
        }
        int bg = median(border);
        double dev = 0;
        for (int c : border) dev += Segmenter.colorDistance(c, bg);
        dev /= border.size();
        float thr = (float) Math.max(24, dev * 3 + 10);

        byte[] mask = Segmenter.productMask(px, mw, mh, bg, thr);
        float cov = Segmenter.coverage(mask);
        if (cov < 0.05f || cov > 0.97f) {
            Log.i(TAG, "cutout rejected, coverage " + cov);
            return null;
        }
        mask = Segmenter.refine(mask, mw, mh);

        int bottom = mh - 1;
        for (int y = mh - 1; y >= 0; y--) {
            int count = 0;
            for (int x = 0; x < mw; x++) if ((mask[y * mw + x] & 0xFF) > 128) count++;
            if (count > mw / 60 + 1) { bottom = y; break; }
        }
        out.contactV = (bottom + 1f) / mh;

        int[] alpha = new int[mw * mh];
        for (int i = 0; i < alpha.length; i++) alpha[i] = (mask[i] & 0xFF) << 24;
        Bitmap maskBmp = Bitmap.createBitmap(alpha, mw, mh, Bitmap.Config.ARGB_8888);
        Bitmap result = crop.copy(Bitmap.Config.ARGB_8888, true);
        Canvas cv = new Canvas(result);
        Paint p = new Paint(Paint.FILTER_BITMAP_FLAG);
        p.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.DST_IN));
        cv.drawBitmap(maskBmp, null, new Rect(0, 0, w, h), p);
        maskBmp.recycle();
        return result;
    }

    private static int median(List<Integer> colors) {
        int m = colors.size();
        int[] r = new int[m], g = new int[m], b = new int[m];
        for (int i = 0; i < m; i++) {
            int c = colors.get(i);
            r[i] = (c >> 16) & 0xFF; g[i] = (c >> 8) & 0xFF; b[i] = c & 0xFF;
        }
        java.util.Arrays.sort(r);
        java.util.Arrays.sort(g);
        java.util.Arrays.sort(b);
        return 0xFF000000 | (r[m / 2] << 16) | (g[m / 2] << 8) | b[m / 2];
    }

    void release() {
        if (product != null) product.release();
        if (backdrop != null) backdrop.release();
        if (texts != null) for (Gl.Texture t : texts) if (t != null) t.release();
        product = null;
        backdrop = null;
        texts = null;
    }
}
