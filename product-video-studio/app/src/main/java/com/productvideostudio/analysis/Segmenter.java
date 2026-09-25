package com.productvideostudio.analysis;

/**
 * Separates a product from a plain (studio) background by flood-filling from the image border.
 * No model download needed, and it works offline. Callers must check {@link #coverage} and fall
 * back to showing the whole photo when the result looks wrong.
 */
public final class Segmenter {
    private Segmenter() {}

    /** Perceptual-ish RGB distance, roughly 0..255. */
    public static float colorDistance(int a, int b) {
        int dr = ((a >> 16) & 0xFF) - ((b >> 16) & 0xFF);
        int dg = ((a >> 8) & 0xFF) - ((b >> 8) & 0xFF);
        int db = (a & 0xFF) - (b & 0xFF);
        return (float) Math.sqrt((2 * dr * dr + 4 * dg * dg + 3 * db * db) / 9.0);
    }

    /**
     * Returns a mask (255 = product, 0 = background) of the same size as {@code px}.
     * Background is everything connected to the border whose color is within {@code threshold}
     * of {@code bg}, plus large enclosed pockets of the same color (e.g. the hole in a mug handle).
     */
    public static byte[] productMask(int[] px, int w, int h, int bg, float threshold) {
        int n = w * h;
        boolean[] bgLike = new boolean[n];
        for (int i = 0; i < n; i++) bgLike[i] = colorDistance(px[i], bg) < threshold;

        byte[] mask = new byte[n];
        for (int i = 0; i < n; i++) mask[i] = (byte) 255;

        int[] stack = new int[n];
        int sp = 0;
        boolean[] seen = new boolean[n];
        for (int x = 0; x < w; x++) {
            sp = push(stack, sp, seen, bgLike, x);
            sp = push(stack, sp, seen, bgLike, (h - 1) * w + x);
        }
        for (int y = 0; y < h; y++) {
            sp = push(stack, sp, seen, bgLike, y * w);
            sp = push(stack, sp, seen, bgLike, y * w + w - 1);
        }
        while (sp > 0) {
            int i = stack[--sp];
            mask[i] = 0;
            int x = i % w, y = i / w;
            if (x > 0) sp = push(stack, sp, seen, bgLike, i - 1);
            if (x < w - 1) sp = push(stack, sp, seen, bgLike, i + 1);
            if (y > 0) sp = push(stack, sp, seen, bgLike, i - w);
            if (y < h - 1) sp = push(stack, sp, seen, bgLike, i + w);
        }

        // Enclosed pockets that closely match the background and are big enough to be real gaps.
        float tight = threshold * 0.7f;
        int minPocket = Math.max(16, n / 250);
        int[] component = new int[n];
        for (int start = 0; start < n; start++) {
            if (seen[start] || !bgLike[start] || colorDistance(px[start], bg) >= tight) continue;
            int count = 0;
            sp = 0;
            stack[sp++] = start;
            seen[start] = true;
            while (sp > 0) {
                int i = stack[--sp];
                component[count++] = i;
                int x = i % w, y = i / w;
                int[] nb = {x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, y > 0 ? i - w : -1, y < h - 1 ? i + w : -1};
                for (int j : nb) {
                    if (j >= 0 && !seen[j] && bgLike[j] && colorDistance(px[j], bg) < tight) {
                        seen[j] = true;
                        stack[sp++] = j;
                    }
                }
            }
            if (count >= minPocket) {
                for (int k = 0; k < count; k++) mask[component[k]] = 0;
            }
        }
        return mask;
    }

    private static int push(int[] stack, int sp, boolean[] seen, boolean[] bgLike, int i) {
        if (!seen[i] && bgLike[i]) {
            seen[i] = true;
            stack[sp++] = i;
        }
        return sp;
    }

    /** Fraction of pixels marked as product. */
    public static float coverage(byte[] mask) {
        long c = 0;
        for (byte b : mask) if (b != 0) c++;
        return c / (float) mask.length;
    }

    /** Shrinks the product by one pixel (removes the background-colored halo), then feathers the edge. */
    public static byte[] refine(byte[] mask, int w, int h) {
        byte[] eroded = new byte[mask.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int i = y * w + x;
                int v = mask[i] & 0xFF;
                if (v != 0) {
                    if ((x > 0 && mask[i - 1] == 0) || (x < w - 1 && mask[i + 1] == 0)
                            || (y > 0 && mask[i - w] == 0) || (y < h - 1 && mask[i + w] == 0)) {
                        v = 0;
                    }
                }
                eroded[i] = (byte) v;
            }
        }
        return boxBlur(eroded, w, h, 1);
    }

    static byte[] boxBlur(byte[] src, int w, int h, int r) {
        int[] tmp = new int[src.length];
        byte[] out = new byte[src.length];
        int span = 2 * r + 1;
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int s = 0;
                for (int k = -r; k <= r; k++) {
                    int xx = Math.min(w - 1, Math.max(0, x + k));
                    s += src[y * w + xx] & 0xFF;
                }
                tmp[y * w + x] = s / span;
            }
        }
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int s = 0;
                for (int k = -r; k <= r; k++) {
                    int yy = Math.min(h - 1, Math.max(0, y + k));
                    s += tmp[yy * w + x];
                }
                out[y * w + x] = (byte) (s / span);
            }
        }
        return out;
    }
}
