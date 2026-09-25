package com.productvideostudio.render;

/** Easing curves used by camera moves, text animation and transitions. */
public final class Easing {
    private Easing() {}

    public static float clamp01(float x) {
        return x < 0 ? 0 : (x > 1 ? 1 : x);
    }

    public static float smoothstep(float e0, float e1, float x) {
        float t = clamp01((x - e0) / (e1 - e0));
        return t * t * (3 - 2 * t);
    }

    public static float inOutSine(float t) {
        t = clamp01(t);
        return (float) (-(Math.cos(Math.PI * t) - 1) / 2);
    }

    public static float inOutCubic(float t) {
        t = clamp01(t);
        return t < 0.5f ? 4 * t * t * t : 1 - (float) Math.pow(-2 * t + 2, 3) / 2;
    }

    public static float outCubic(float t) {
        t = clamp01(t);
        return 1 - (1 - t) * (1 - t) * (1 - t);
    }

    public static float inQuad(float t) {
        t = clamp01(t);
        return t * t;
    }

    public static float outBack(float t) {
        t = clamp01(t);
        float c1 = 1.70158f, c3 = c1 + 1;
        return 1 + c3 * (float) Math.pow(t - 1, 3) + c1 * (float) Math.pow(t - 1, 2);
    }

    /** Springy overshoot that settles at 1 (subtle bounce). */
    public static float outBounceSoft(float t) {
        t = clamp01(t);
        if (t >= 1) return 1;
        return (float) (1 - Math.exp(-6.5 * t) * Math.cos(9.5 * t));
    }

    /** Speed ramp: fast, slow motion in the middle, fast again. Monotonic. */
    public static float speedRamp(float t) {
        t = clamp01(t);
        return (float) (t - 0.13 * Math.sin(2 * Math.PI * t));
    }

    /** Linear progress with a hold between {@code a} and {@code b} (freeze frame). */
    public static float freeze(float t, float a, float b) {
        t = clamp01(t);
        float span = 1 - (b - a);
        if (t < a) return t / span;
        if (t < b) return a / span;
        return (t - (b - a)) / span;
    }

    /** Smooth pseudo-random noise in -1..1, continuous in {@code x}. */
    public static float noise(float x, int seed) {
        int i = (int) Math.floor(x);
        float f = x - i;
        float a = hash(i, seed), b = hash(i + 1, seed);
        float u = f * f * (3 - 2 * f);
        return a + (b - a) * u;
    }

    private static float hash(int i, int seed) {
        int h = i * 374761393 + seed * 668265263;
        h = (h ^ (h >>> 13)) * 1274126177;
        h ^= h >>> 16;
        return (h & 0xFFFF) / 32767.5f - 1f;
    }
}
