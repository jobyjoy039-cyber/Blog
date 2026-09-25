package com.productvideostudio.analysis;

import android.graphics.Bitmap;
import android.graphics.Color;

import com.productvideostudio.model.Enums;
import com.productvideostudio.model.ImageAnalysis;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Pixel-level analysis of a product photo: palette, background, subject position, detail,
 * sharpness, shape and likely camera angle. Pure CPU and fully offline.
 */
public final class ImageAnalyzer {
    /** Analysis resolution (longer side). Plenty for statistics, fast on any phone. */
    public static final int SIZE = 320;

    private ImageAnalyzer() {}

    public static ImageAnalysis analyze(String path, String fileName) {
        ImageAnalysis a = new ImageAnalysis();
        a.file = fileName;
        int[] size = Bitmaps.size(path);
        a.width = size[0];
        a.height = size[1];
        Bitmap bmp = Bitmaps.decode(path, SIZE);
        if (bmp == null) return a;
        int w = bmp.getWidth(), h = bmp.getHeight();
        int[] px = new int[w * h];
        bmp.getPixels(px, 0, w, 0, 0, w, h);
        bmp.recycle();
        analyzePixels(a, px, w, h);
        return a;
    }

    static void analyzePixels(ImageAnalysis a, int[] px, int w, int h) {
        int n = w * h;
        float[] luma = new float[n];
        double lumSum = 0;
        for (int i = 0; i < n; i++) {
            int c = px[i];
            luma[i] = 0.2126f * ((c >> 16) & 0xFF) + 0.7152f * ((c >> 8) & 0xFF) + 0.0722f * (c & 0xFF);
            lumSum += luma[i];
        }
        a.brightness = (float) (lumSum / n / 255.0);

        // --- Background: statistics of a thin border ---
        int bw = Math.max(2, Math.min(w, h) / 16);
        List<Integer> border = new ArrayList<>();
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                if (x < bw || y < bw || x >= w - bw || y >= h - bw) border.add(px[y * w + x]);
            }
        }
        int bg = medianColor(border);
        a.backgroundColor = bg;
        int close = 0;
        double devSum = 0;
        for (int c : border) {
            float d = Segmenter.colorDistance(c, bg);
            devSum += d;
            if (d < 26) close++;
        }
        float borderDev = (float) (devSum / border.size());
        boolean plain = close > border.size() * 0.86f && borderDev < 16f;

        // --- Gradient energy (for saliency, detail and sharpness) ---
        float[] grad = new float[n];
        double lapSum = 0, lapSq = 0;
        int lapN = 0;
        for (int y = 1; y < h - 1; y++) {
            for (int x = 1; x < w - 1; x++) {
                int i = y * w + x;
                float gx = luma[i + 1] - luma[i - 1];
                float gy = luma[i + w] - luma[i - w];
                grad[i] = (float) Math.sqrt(gx * gx + gy * gy);
                float lap = luma[i + 1] + luma[i - 1] + luma[i + w] + luma[i - w] - 4 * luma[i];
                lapSum += lap;
                lapSq += lap * lap;
                lapN++;
            }
        }
        double lapMean = lapSum / Math.max(1, lapN);
        double lapVar = lapSq / Math.max(1, lapN) - lapMean * lapMean;
        a.sharpness = (float) Math.min(1.0, Math.sqrt(Math.max(0, lapVar)) / 28.0);

        // --- Subject ---
        byte[] mask = null;
        if (plain) {
            float thr = Math.max(24f, borderDev * 3f + 10f);
            mask = Segmenter.productMask(px, w, h, bg, thr);
            float cov = Segmenter.coverage(mask);
            if (cov < 0.03f || cov > 0.93f) {
                plain = false;
                mask = null;
            }
        }
        a.plainBackground = plain;

        if (mask != null) {
            int minX = w, minY = h, maxX = 0, maxY = 0;
            double sx = 0, sy = 0;
            int count = 0;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    if (mask[y * w + x] != 0) {
                        if (x < minX) minX = x;
                        if (x > maxX) maxX = x;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                        sx += x; sy += y; count++;
                    }
                }
            }
            a.subjectBox = new float[]{minX / (float) w, minY / (float) h, (maxX + 1) / (float) w, (maxY + 1) / (float) h};
            a.focusX = (float) (sx / count / w);
            a.focusY = (float) (sy / count / h);
            float boxArea = (maxX - minX + 1f) * (maxY - minY + 1f);
            a.fillRatio = count / boxArea;
        } else {
            // Saliency: blurred gradient energy; box holds the central 80% of the energy mass.
            float[] e = blur(grad, w, h, 4);
            double[] colMass = new double[w], rowMass = new double[h];
            double total = 0, sx = 0, sy = 0;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    // Mild center bias: photographers frame the product near the middle.
                    float dx = (x / (float) w - 0.5f), dy = (y / (float) h - 0.5f);
                    double v = e[y * w + x] * e[y * w + x] * (1.0 - 0.9 * (dx * dx + dy * dy));
                    colMass[x] += v; rowMass[y] += v; total += v;
                    sx += v * x; sy += v * y;
                }
            }
            if (total > 0) {
                a.focusX = (float) (sx / total / w);
                a.focusY = (float) (sy / total / h);
                a.subjectBox = new float[]{
                        quantile(colMass, total, 0.1) / (float) w, quantile(rowMass, total, 0.1) / (float) h,
                        (quantile(colMass, total, 0.9) + 1) / (float) w, (quantile(rowMass, total, 0.9) + 1) / (float) h};
            }
            a.fillRatio = 1f;
        }

        // --- Most detailed window (macro target), restricted to the subject ---
        int win = Math.max(8, Math.min(w, h) / 4);
        double[] integral = new double[(w + 1) * (h + 1)];
        for (int y = 0; y < h; y++) {
            double row = 0;
            for (int x = 0; x < w; x++) {
                row += grad[y * w + x];
                integral[(y + 1) * (w + 1) + x + 1] = integral[y * (w + 1) + x + 1] + row;
            }
        }
        int x0 = (int) (a.subjectBox[0] * w), y0 = (int) (a.subjectBox[1] * h);
        int x1 = (int) (a.subjectBox[2] * w) - win, y1 = (int) (a.subjectBox[3] * h) - win;
        double best = -1;
        for (int y = y0; y <= Math.max(y0, y1); y += 2) {
            for (int x = x0; x <= Math.max(x0, x1); x += 2) {
                int xa = Math.min(x, w - win), ya = Math.min(y, h - win);
                if (xa < 0 || ya < 0) continue;
                double s = integral[(ya + win) * (w + 1) + xa + win] - integral[ya * (w + 1) + xa + win]
                        - integral[(ya + win) * (w + 1) + xa] + integral[ya * (w + 1) + xa];
                if (s > best) {
                    best = s;
                    a.detailX = (xa + win / 2f) / w;
                    a.detailY = (ya + win / 2f) / h;
                }
            }
        }

        // --- Palette (k-means on the product pixels when we have a mask) ---
        List<Integer> sample = new ArrayList<>();
        int step = Math.max(1, n / 6000);
        for (int i = 0; i < n; i += step) {
            if (mask == null || mask[i] != 0) sample.add(px[i]);
        }
        int[][] clusters = kmeans(sample, 5);
        a.palette.clear();
        int accent = clusters.length > 0 ? clusters[0][0] : 0xFF888888;
        float bestAccent = -1;
        for (int[] cl : clusters) {
            a.palette.add(cl[0]);
            float share = cl[1] / (float) Math.max(1, sample.size());
            float[] hsv = new float[3];
            Color.colorToHSV(cl[0], hsv);
            float score = hsv[1] * (0.35f + hsv[2]) * (float) Math.sqrt(share);
            if (share > 0.03f && score > bestAccent) {
                bestAccent = score;
                accent = cl[0];
            }
        }
        a.accentColor = accent;

        // --- Colorfulness (Hasler & Süsstrunk) and specular highlights ---
        double rgSum = 0, rgSq = 0, ybSum = 0, ybSq = 0;
        int spec = 0, subj = 0;
        for (int i = 0; i < n; i += 2) {
            if (mask != null && mask[i] == 0) continue;
            int c = px[i];
            int r = (c >> 16) & 0xFF, g = (c >> 8) & 0xFF, b = c & 0xFF;
            double rg = r - g, yb = 0.5 * (r + g) - b;
            rgSum += rg; rgSq += rg * rg; ybSum += yb; ybSq += yb * yb;
            subj++;
            int mx = Math.max(r, Math.max(g, b)), mn = Math.min(r, Math.min(g, b));
            if (luma[i] > 240 && mx - mn < 30) spec++;
        }
        if (subj > 0) {
            double mrg = rgSum / subj, myb = ybSum / subj;
            double srg = Math.sqrt(Math.max(0, rgSq / subj - mrg * mrg)), syb = Math.sqrt(Math.max(0, ybSq / subj - myb * myb));
            double cf = Math.sqrt(srg * srg + syb * syb) + 0.3 * Math.sqrt(mrg * mrg + myb * myb);
            a.colorfulness = (float) Math.min(1.0, cf / 110.0);
            a.specular = spec / (float) subj;
        }

        // --- Shape and view angle ---
        float bwPx = (a.subjectBox[2] - a.subjectBox[0]) * a.width;
        float bhPx = (a.subjectBox[3] - a.subjectBox[1]) * a.height;
        float aspect = bwPx / Math.max(1f, bhPx);
        if (plain && a.fillRatio < 0.84f && aspect > 0.8f && aspect < 1.25f) a.shape = "round";
        else if (aspect > 1.35f) a.shape = "wide";
        else if (aspect < 0.74f) a.shape = "tall";
        else a.shape = "square";

        a.kind = plain ? "packshot" : "lifestyle";
        if (!plain) {
            a.viewAngle = Enums.CameraAngle.EYE_LEVEL;
        } else {
            switch (a.shape) {
                case "round": a.viewAngle = Enums.CameraAngle.TOP_DOWN; break;
                case "wide": a.viewAngle = Enums.CameraAngle.SIDE_PROFILE; break;
                case "tall": a.viewAngle = Enums.CameraAngle.FRONT; break;
                default: a.viewAngle = a.fillRatio > 0.9f ? Enums.CameraAngle.ANGLE_45 : Enums.CameraAngle.FRONT;
            }
        }
    }

    static int quantile(double[] mass, double total, double q) {
        double acc = 0;
        for (int i = 0; i < mass.length; i++) {
            acc += mass[i];
            if (acc >= total * q) return i;
        }
        return mass.length - 1;
    }

    static float[] blur(float[] src, int w, int h, int r) {
        float[] tmp = new float[src.length], out = new float[src.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                float s = 0;
                int c = 0;
                for (int k = -r; k <= r; k++) {
                    int xx = x + k;
                    if (xx >= 0 && xx < w) { s += src[y * w + xx]; c++; }
                }
                tmp[y * w + x] = s / c;
            }
        }
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                float s = 0;
                int c = 0;
                for (int k = -r; k <= r; k++) {
                    int yy = y + k;
                    if (yy >= 0 && yy < h) { s += tmp[yy * w + x]; c++; }
                }
                out[y * w + x] = s / c;
            }
        }
        return out;
    }

    static int medianColor(List<Integer> colors) {
        int m = colors.size();
        if (m == 0) return 0xFFFFFFFF;
        int[] r = new int[m], g = new int[m], b = new int[m];
        for (int i = 0; i < m; i++) {
            int c = colors.get(i);
            r[i] = (c >> 16) & 0xFF; g[i] = (c >> 8) & 0xFF; b[i] = c & 0xFF;
        }
        Arrays.sort(r); Arrays.sort(g); Arrays.sort(b);
        return 0xFF000000 | (r[m / 2] << 16) | (g[m / 2] << 8) | b[m / 2];
    }

    /** Returns clusters as {color, count}, most populous first. */
    static int[][] kmeans(List<Integer> colors, int k) {
        int m = colors.size();
        if (m == 0) return new int[0][];
        k = Math.min(k, m);
        // Initialize from luminance quantiles for stable, deterministic results.
        Integer[] sorted = colors.toArray(new Integer[0]);
        Arrays.sort(sorted, (x, y) -> Float.compare(lum(x), lum(y)));
        float[][] c = new float[k][3];
        for (int j = 0; j < k; j++) {
            int col = sorted[(int) ((j + 0.5f) / k * m)];
            c[j][0] = (col >> 16) & 0xFF; c[j][1] = (col >> 8) & 0xFF; c[j][2] = col & 0xFF;
        }
        int[] assign = new int[m];
        int[] counts = new int[k];
        for (int iter = 0; iter < 10; iter++) {
            double[][] sum = new double[k][3];
            Arrays.fill(counts, 0);
            for (int i = 0; i < m; i++) {
                int col = colors.get(i);
                float r = (col >> 16) & 0xFF, g = (col >> 8) & 0xFF, b = col & 0xFF;
                int bestJ = 0;
                float bestD = Float.MAX_VALUE;
                for (int j = 0; j < k; j++) {
                    float dr = r - c[j][0], dg = g - c[j][1], db = b - c[j][2];
                    float d = 2 * dr * dr + 4 * dg * dg + 3 * db * db;
                    if (d < bestD) { bestD = d; bestJ = j; }
                }
                assign[i] = bestJ;
                sum[bestJ][0] += r; sum[bestJ][1] += g; sum[bestJ][2] += b;
                counts[bestJ]++;
            }
            for (int j = 0; j < k; j++) {
                if (counts[j] > 0) {
                    c[j][0] = (float) (sum[j][0] / counts[j]);
                    c[j][1] = (float) (sum[j][1] / counts[j]);
                    c[j][2] = (float) (sum[j][2] / counts[j]);
                }
            }
        }
        List<int[]> out = new ArrayList<>();
        for (int j = 0; j < k; j++) {
            if (counts[j] == 0) continue;
            int col = 0xFF000000 | (Math.round(c[j][0]) << 16) | (Math.round(c[j][1]) << 8) | Math.round(c[j][2]);
            out.add(new int[]{col, counts[j]});
        }
        out.sort((x, y) -> Integer.compare(y[1], x[1]));
        return out.toArray(new int[0][]);
    }

    static float lum(int c) {
        return 0.2126f * ((c >> 16) & 0xFF) + 0.7152f * ((c >> 8) & 0xFF) + 0.0722f * (c & 0xFF);
    }
}
