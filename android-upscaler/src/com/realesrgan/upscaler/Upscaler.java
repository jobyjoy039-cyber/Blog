package com.realesrgan.upscaler;

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
     * @param outScale final scale, 4 or 2 (2 = the 4x result box-filtered down by half)
     */
    public Bitmap upscale(Bitmap src, int outScale, int tile, int pad, Listener listener)
            throws OrtException, CancelledException {
        final int w = src.getWidth();
        final int h = src.getHeight();
        final int div = NET_SCALE / outScale;
        final boolean alpha = src.hasAlpha();
        Bitmap out = Bitmap.createBitmap(w * outScale, h * outScale, Bitmap.Config.ARGB_8888);

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
                float[] chw = new float[3 * pw * ph];
                int plane = pw * ph;
                for (int i = 0; i < plane; i++) {
                    int c = in[i];
                    chw[i] = ((c >> 16) & 0xff) / 255f;
                    chw[plane + i] = ((c >> 8) & 0xff) / 255f;
                    chw[2 * plane + i] = (c & 0xff) / 255f;
                }

                float[] res;
                OnnxTensor t = OnnxTensor.createTensor(env, FloatBuffer.wrap(chw), new long[]{1, 3, ph, pw});
                try {
                    OrtSession.Result r = session.run(Collections.singletonMap(inputName, t));
                    try {
                        FloatBuffer fb = ((OnnxTensor) r.get(0)).getFloatBuffer();
                        res = new float[fb.remaining()];
                        fb.get(res);
                    } finally {
                        r.close();
                    }
                } finally {
                    t.close();
                }

                // Copy the un-padded part of the tile into the output.
                int ow = pw * NET_SCALE, oh = ph * NET_SCALE, oplane = ow * oh;
                int tw = (x1 - x0) * outScale, th = (y1 - y0) * outScale;
                int offX = (x0 - px0) * NET_SCALE, offY = (y0 - py0) * NET_SCALE;
                int[] pix = new int[tw * th];
                float inv = 1f / (div * div);
                for (int oy = 0; oy < th; oy++) {
                    for (int ox = 0; ox < tw; ox++) {
                        float r = 0, g = 0, b = 0;
                        for (int dy = 0; dy < div; dy++) {
                            int row = (offY + oy * div + dy) * ow + offX + ox * div;
                            for (int dx = 0; dx < div; dx++) {
                                int k = row + dx;
                                r += res[k];
                                g += res[oplane + k];
                                b += res[2 * oplane + k];
                            }
                        }
                        int a = 255;
                        if (alpha) {
                            // Bilinear upsample of the source alpha channel (RealESRGANer uses a
                            // resize for alpha too when the alpha model isn't used).
                            float sx = (x0 + (ox + 0.5f) / outScale) - 0.5f - px0;
                            float sy = (y0 + (oy + 0.5f) / outScale) - 0.5f - py0;
                            a = bilinearAlpha(in, pw, ph, sx, sy);
                        }
                        pix[oy * tw + ox] = (a << 24) | (clamp(r * inv) << 16) | (clamp(g * inv) << 8) | clamp(b * inv);
                    }
                }
                out.setPixels(pix, 0, tw, x0 * outScale, y0 * outScale, tw, th);

                done++;
                if (listener != null) listener.onProgress(done, total);
            }
        }
        return out;
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
