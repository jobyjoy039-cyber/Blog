package com.productvideostudio.audio;

/** Stereo float PCM at a fixed sample rate, with mixing helpers. */
public final class Pcm {
    public static final int RATE = 44100;

    public final float[] left;
    public final float[] right;

    public Pcm(int frames) {
        left = new float[frames];
        right = new float[frames];
    }

    public static Pcm ofSeconds(float seconds) {
        return new Pcm(Math.max(1, Math.round(seconds * RATE)));
    }

    public int frames() {
        return left.length;
    }

    /** Mixes {@code src} in at {@code atSec} with gain and equal-power pan (-1..1). */
    public void mix(Pcm src, float atSec, float gain, float pan) {
        int offset = Math.round(atSec * RATE);
        double angle = (pan + 1) * Math.PI / 4;
        float gl = (float) (Math.cos(angle) * Math.sqrt(2)) * gain;
        float gr = (float) (Math.sin(angle) * Math.sqrt(2)) * gain;
        for (int i = 0; i < src.frames(); i++) {
            int j = offset + i;
            if (j < 0) continue;
            if (j >= frames()) break;
            left[j] += src.left[i] * gl;
            right[j] += src.right[i] * gr;
        }
    }

    public void fadeIn(float seconds) {
        int n = Math.min(frames(), Math.round(seconds * RATE));
        for (int i = 0; i < n; i++) {
            float g = i / (float) n;
            left[i] *= g;
            right[i] *= g;
        }
    }

    public void fadeOut(float seconds) {
        int n = Math.min(frames(), Math.round(seconds * RATE));
        int start = frames() - n;
        for (int i = 0; i < n; i++) {
            float g = 1f - i / (float) n;
            g *= g;
            left[start + i] *= g;
            right[start + i] *= g;
        }
    }

    public float peak() {
        float p = 0;
        for (int i = 0; i < frames(); i++) p = Math.max(p, Math.max(Math.abs(left[i]), Math.abs(right[i])));
        return p;
    }

    /** Gentle soft clip followed by normalization to {@code target} peak. */
    public void master(float target) {
        for (int i = 0; i < frames(); i++) {
            left[i] = soft(left[i]);
            right[i] = soft(right[i]);
        }
        float p = peak();
        if (p > 1e-4f) {
            float g = target / p;
            for (int i = 0; i < frames(); i++) {
                left[i] *= g;
                right[i] *= g;
            }
        }
    }

    private static float soft(float x) {
        float a = Math.abs(x);
        if (a < 0.8f) return x;
        float y = 0.8f + (float) Math.tanh((a - 0.8f) / 0.2f) * 0.2f;
        return Math.signum(x) * y;
    }

    /** Interleaved 16-bit little-endian PCM. */
    public byte[] toPcm16() {
        byte[] out = new byte[frames() * 4];
        for (int i = 0; i < frames(); i++) {
            int l = Math.round(Math.max(-1f, Math.min(1f, left[i])) * 32767f);
            int r = Math.round(Math.max(-1f, Math.min(1f, right[i])) * 32767f);
            out[i * 4] = (byte) l;
            out[i * 4 + 1] = (byte) (l >> 8);
            out[i * 4 + 2] = (byte) r;
            out[i * 4 + 3] = (byte) (r >> 8);
        }
        return out;
    }
}
