package com.jobyjoy.pixelboost;

import android.graphics.Bitmap;

import java.nio.FloatBuffer;
import java.util.Collections;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtException;
import ai.onnxruntime.OrtSession;

/**
 * Runs a Real-ESRGAN SRVGGNetCompact model (exported to ONNX) over a bitmap tile by tile,
 * mirroring the tile/tile_pad logic of RealESRGANer in realesrgan/utils.py.
 */
public final class Upscaler implements AutoCloseable {

    /** The network always upsamples by this factor. */
    public static final int NET_SCALE = 4;

    public interface Listener {
        void onProgress(int doneTiles, int totalTiles);

        boolean isCancelled();
    }

    public static final class CancelledException extends Exception {
    }

    private final OrtEnvironment env;
    private final OrtSession session;
    private final String inputName;

    public Upscaler(byte[] model) throws OrtException {
        env = OrtEnvironment.getEnvironment();
        OrtSession.SessionOptions options = new OrtSession.SessionOptions();
        options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);
        session = env.createSession(model, options);
        inputName = session.getInputNames().iterator().next();
    }

    /**
     * Upscales {@code src} to exactly {@code outW} x {@code outH}, which must be at most 4x the source.
     * Each tile's 4x network output is area-averaged down to the target grid straight away, so the
     * full 4x image never has to exist in memory.
     */
    public Bitmap upscale(Bitmap src, int outW, int outH, int tile, int pad, Listener listener)
            throws OrtException, CancelledException {
        final int w = src.getWidth();
        final int h = src.getHeight();
        if (outW > w * NET_SCALE || outH > h * NET_SCALE) {
            throw new IllegalArgumentException("a single pass can upscale at most " + NET_SCALE + "x");
        }
        final boolean alpha = src.hasAlpha();
        // Size of one output pixel measured in network-output (4x) pixels.
        final double spanX = NET_SCALE * (double) w / outW;
        final double spanY = NET_SCALE * (double) h / outH;
        Bitmap out = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);
        // New ARGB bitmaps report hasAlpha() == true; keep the source's answer so opaque results
        // are saved as JPEG and a second pass skips the alpha work.
        out.setHasAlpha(alpha);

        int tilesX = (w + tile - 1) / tile;
        int tilesY = (h + tile - 1) / tile;
        int total = tilesX * tilesY;
        int done = 0;

        for (int ty = 0; ty < tilesY; ty++) {
            for (int tx = 0; tx < tilesX; tx++) {
                if (listener != null && listener.isCancelled()) {
                    out.recycle();
                    throw new CancelledException();
                }
                int x0 = tx * tile, y0 = ty * tile;
                int x1 = Math.min(x0 + tile, w), y1 = Math.min(y0 + tile, h);
                int px0 = Math.max(x0 - pad, 0), py0 = Math.max(y0 - pad, 0);
                int px1 = Math.min(x1 + pad, w), py1 = Math.min(y1 + pad, h);
                int pw = px1 - px0, ph = py1 - py0;

                int[] in = new int[pw * ph];
                src.getPixels(in, 0, pw, px0, py0, pw, ph);
                float[] res = run(in, pw, ph);

                // Output pixels whose centre falls in this (un-padded) tile.
                int ox0 = (int) ((long) x0 * outW / w), ox1 = (int) ((long) x1 * outW / w);
                int oy0 = (int) ((long) y0 * outH / h), oy1 = (int) ((long) y1 * outH / h);
                int tw = ox1 - ox0, th = oy1 - oy0;
                if (tw <= 0 || th <= 0) {
                    done++;
                    continue;
                }
                int ow = pw * NET_SCALE, oh = ph * NET_SCALE, oplane = ow * oh;
                int[] colA = new int[tw], colB = new int[tw];
                for (int i = 0; i < tw; i++) {
                    double s0 = (ox0 + i) * spanX - px0 * NET_SCALE;
                    colA[i] = clampI((int) Math.floor(s0 + 1e-6), 0, ow - 1);
                    colB[i] = clampI((int) Math.ceil(s0 + spanX - 1e-6), colA[i] + 1, ow);
                }
                int[] pix = new int[tw * th];
                for (int j = 0; j < th; j++) {
                    double t0 = (oy0 + j) * spanY - py0 * NET_SCALE;
                    int ra = clampI((int) Math.floor(t0 + 1e-6), 0, oh - 1);
                    int rb = clampI((int) Math.ceil(t0 + spanY - 1e-6), ra + 1, oh);
                    for (int i = 0; i < tw; i++) {
                        float r = 0, g = 0, b = 0;
                        int ca = colA[i], cb = colB[i];
                        for (int yy = ra; yy < rb; yy++) {
                            int row = yy * ow;
                            for (int xx = ca; xx < cb; xx++) {
                                int k = row + xx;
                                r += res[k];
                                g += res[oplane + k];
                                b += res[2 * oplane + k];
                            }
                        }
                        float inv = 1f / ((rb - ra) * (cb - ca));
                        int a = 255;
                        if (alpha) {
                            // Bilinear upsample of the source alpha channel (RealESRGANer uses a
                            // resize for alpha too when the alpha model isn't used).
                            float sx = (float) ((ox0 + i + 0.5) * w / outW - 0.5 - px0);
                            float sy = (float) ((oy0 + j + 0.5) * h / outH - 0.5 - py0);
                            a = bilinearAlpha(in, pw, ph, sx, sy);
                        }
                        pix[j * tw + i] = (a << 24) | (clamp(r * inv) << 16) | (clamp(g * inv) << 8) | clamp(b * inv);
                    }
                }
                out.setPixels(pix, 0, tw, ox0, oy0, tw, th);

                done++;
                if (listener != null) listener.onProgress(done, total);
            }
        }
        return out;
    }

    /** Runs the network on one ARGB tile; returns the planar RGB 4x output. */
    private float[] run(int[] in, int pw, int ph) throws OrtException {
        int plane = pw * ph;
        float[] chw = new float[3 * plane];
        for (int i = 0; i < plane; i++) {
            int c = in[i];
            chw[i] = ((c >> 16) & 0xff) / 255f;
            chw[plane + i] = ((c >> 8) & 0xff) / 255f;
            chw[2 * plane + i] = (c & 0xff) / 255f;
        }
        OnnxTensor t = OnnxTensor.createTensor(env, FloatBuffer.wrap(chw), new long[]{1, 3, ph, pw});
        try {
            OrtSession.Result r = session.run(Collections.singletonMap(inputName, t));
            try {
                FloatBuffer fb = ((OnnxTensor) r.get(0)).getFloatBuffer();
                float[] res = new float[fb.remaining()];
                fb.get(res);
                return res;
            } finally {
                r.close();
            }
        } finally {
            t.close();
        }
    }

    private static int clampI(int v, int lo, int hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    private static int bilinearAlpha(int[] in, int w, int h, float x, float y) {
        if (x < 0) x = 0;
        if (y < 0) y = 0;
        if (x > w - 1) x = w - 1;
        if (y > h - 1) y = h - 1;
        int xa = (int) x, ya = (int) y;
        int xb = Math.min(xa + 1, w - 1), yb = Math.min(ya + 1, h - 1);
        float fx = x - xa, fy = y - ya;
        float top = (in[ya * w + xa] >>> 24) * (1 - fx) + (in[ya * w + xb] >>> 24) * fx;
        float bot = (in[yb * w + xa] >>> 24) * (1 - fx) + (in[yb * w + xb] >>> 24) * fx;
        return Math.round(top * (1 - fy) + bot * fy);
    }

    private static int clamp(float v) {
        int i = Math.round(v * 255f);
        return i < 0 ? 0 : (i > 255 ? 255 : i);
    }

    @Override
    public void close() {
        try {
            session.close();
        } catch (OrtException ignored) {
        }
    }
}
