package com.productvideostudio.audio;

import com.productvideostudio.model.Enums.SfxType;

import java.util.Random;

/**
 * Synthesizes the sound-effect library at render time, so the app ships no audio files and every
 * effect can be sized to the moment (a whoosh as long as its transition, for example).
 */
public final class SfxSynth {
    private SfxSynth() {}

    private static final float R = Pcm.RATE;

    public static Pcm make(SfxType type, float length, long seed) {
        Random rnd = new Random(seed);
        switch (type) {
            case WHOOSH: return whoosh(Math.max(0.25f, length), rnd, 1.0f, 380, 4200);
            case SWOOSH_SOFT: return whoosh(Math.max(0.4f, length), rnd, 0.6f, 250, 1800);
            case CLICK: return click(rnd);
            case POP: return pop();
            case SHIMMER: return shimmer(Math.max(1f, length), rnd);
            case TECH_BLIP: return blip();
            case IMPACT: return impact(Math.max(0.6f, length), rnd);
            case RISER: return riser(Math.max(0.5f, length), rnd);
            case NATURE_AMBIENCE: return ambience(length, rnd);
            case CAMERA_SHUTTER: return shutter(rnd);
            default: return new Pcm(1);
        }
    }

    /** Band-passed noise sweeping up then down, with a pan sweep. */
    static Pcm whoosh(float len, Random rnd, float bright, float fLow, float fHigh) {
        Pcm p = Pcm.ofSeconds(len);
        int n = p.frames();
        Svf fl = new Svf(), fr = new Svf();
        for (int i = 0; i < n; i++) {
            float t = i / (float) n;
            float env = (float) Math.pow(Math.sin(Math.PI * Math.pow(t, 0.7)), 2);
            float f = fLow + (fHigh - fLow) * (float) Math.sin(Math.PI * t) * bright;
            float nl = rnd.nextFloat() * 2 - 1, nr = rnd.nextFloat() * 2 - 1;
            float l = fl.bandpass(nl, f, 1.6f), r = fr.bandpass(nr * 0.7f + nl * 0.3f, f * 1.05f, 1.6f);
            float pan = t * 2 - 1;
            p.left[i] = l * env * 0.9f * (1 - pan * 0.4f);
            p.right[i] = r * env * 0.9f * (1 + pan * 0.4f);
        }
        return p;
    }

    static Pcm click(Random rnd) {
        Pcm p = Pcm.ofSeconds(0.05f);
        for (int i = 0; i < p.frames(); i++) {
            float t = i / R;
            float s = (float) Math.sin(2 * Math.PI * 1900 * t) * (float) Math.exp(-t * 180);
            s += (rnd.nextFloat() * 2 - 1) * (float) Math.exp(-t * 900) * 0.5f;
            p.left[i] = p.right[i] = s * 0.6f;
        }
        return p;
    }

    static Pcm pop() {
        Pcm p = Pcm.ofSeconds(0.14f);
        double phase = 0;
        for (int i = 0; i < p.frames(); i++) {
            float t = i / R;
            float f = 300 + 900 * (float) Math.exp(-t * 45);
            phase += 2 * Math.PI * f / R;
            float env = (float) (Math.exp(-t * 28) * Math.min(1, t * 900));
            p.left[i] = p.right[i] = (float) Math.sin(phase) * env * 0.8f;
        }
        return p;
    }

    /** Bell partials with slow shimmer and a stereo spread. */
    static Pcm shimmer(float len, Random rnd) {
        Pcm p = Pcm.ofSeconds(len);
        float[] notes = {1318.5f, 1760f, 2093f, 2637f};
        float[] ratios = {1f, 2.76f, 5.4f};
        for (int k = 0; k < notes.length; k++) {
            float start = k * 0.07f;
            float pan = (k % 2 == 0 ? -0.5f : 0.5f);
            for (int i = Math.round(start * R); i < p.frames(); i++) {
                float t = i / R - start;
                float s = 0;
                for (int r = 0; r < ratios.length; r++) {
                    s += (float) Math.sin(2 * Math.PI * notes[k] * ratios[r] * t) * (float) Math.exp(-t * (2.5f + r * 3f)) / (r + 1);
                }
                s *= Math.min(1, t * 400) * 0.18f * (1 + 0.2f * (float) Math.sin(2 * Math.PI * 5 * t));
                p.left[i] += s * (1 - pan);
                p.right[i] += s * (1 + pan);
            }
        }
        return p;
    }

    static Pcm blip() {
        Pcm p = Pcm.ofSeconds(0.12f);
        for (int i = 0; i < p.frames(); i++) {
            float t = i / R;
            float f = t < 0.045f ? 1250 : 1870;
            float sq = Math.signum((float) Math.sin(2 * Math.PI * f * t));
            float env = (float) Math.exp(-((t < 0.045f ? t : t - 0.045f)) * 60) * Math.min(1, t * 2000);
            p.left[i] = p.right[i] = sq * env * 0.22f;
        }
        return p;
    }

    /** Sub-bass hit with a noisy transient: the "drop" on the hero reveal. */
    static Pcm impact(float len, Random rnd) {
        Pcm p = Pcm.ofSeconds(len);
        double phase = 0;
        Svf lp = new Svf();
        for (int i = 0; i < p.frames(); i++) {
            float t = i / R;
            float f = 42 + 80 * (float) Math.exp(-t * 18);
            phase += 2 * Math.PI * f / R;
            float body = (float) Math.sin(phase) * (float) Math.exp(-t * 3.2);
            float noise = lp.lowpass(rnd.nextFloat() * 2 - 1, 1800, 0.7f) * (float) Math.exp(-t * 22);
            float s = (body * 0.9f + noise * 0.6f) * Math.min(1, t * 3000);
            p.left[i] = p.right[i] = s;
        }
        return p;
    }

    static Pcm riser(float len, Random rnd) {
        Pcm p = Pcm.ofSeconds(len);
        Svf fl = new Svf(), fr = new Svf();
        double phase = 0;
        for (int i = 0; i < p.frames(); i++) {
            float t = i / (float) p.frames();
            float f = 300 + 5000 * t * t;
            phase += 2 * Math.PI * (180 + 500 * t) / R;
            float env = t * t;
            float tone = (float) Math.sin(phase) * 0.25f;
            p.left[i] = (fl.bandpass(rnd.nextFloat() * 2 - 1, f, 2f) * 0.8f + tone) * env;
            p.right[i] = (fr.bandpass(rnd.nextFloat() * 2 - 1, f * 1.03f, 2f) * 0.8f + tone) * env;
        }
        return p;
    }

    /** Soft wind (filtered brown noise) with occasional bird chirps. */
    static Pcm ambience(float len, Random rnd) {
        Pcm p = Pcm.ofSeconds(Math.max(1f, len));
        Svf fl = new Svf(), fr = new Svf();
        float bl = 0, br = 0;
        for (int i = 0; i < p.frames(); i++) {
            float t = i / R;
            bl = bl * 0.995f + (rnd.nextFloat() * 2 - 1) * 0.03f;
            br = br * 0.995f + (rnd.nextFloat() * 2 - 1) * 0.03f;
            float gust = 0.6f + 0.4f * (float) Math.sin(2 * Math.PI * 0.11 * t) * (float) Math.sin(2 * Math.PI * 0.037 * t + 1);
            p.left[i] = fl.lowpass(bl * 4, 700, 0.6f) * gust * 0.6f;
            p.right[i] = fr.lowpass(br * 4, 760, 0.6f) * gust * 0.6f;
        }
        float t = 0.8f + rnd.nextFloat();
        while (t < len - 0.5f) {
            float base = 2600 + rnd.nextFloat() * 1600;
            float pan = rnd.nextFloat() * 1.4f - 0.7f;
            int chirps = 2 + rnd.nextInt(3);
            for (int c = 0; c < chirps; c++) {
                float start = t + c * 0.11f;
                int s0 = Math.round(start * R), s1 = Math.min(p.frames(), s0 + Math.round(0.07f * R));
                double phase = 0;
                for (int i = s0; i < s1; i++) {
                    float u = (i - s0) / (float) (s1 - s0);
                    phase += 2 * Math.PI * (base + 1400 * u) / R;
                    float s = (float) Math.sin(phase) * (float) Math.sin(Math.PI * u) * 0.08f;
                    p.left[i] += s * (1 - pan);
                    p.right[i] += s * (1 + pan);
                }
            }
            t += 1.6f + rnd.nextFloat() * 2.2f;
        }
        return p;
    }

    static Pcm shutter(Random rnd) {
        Pcm p = Pcm.ofSeconds(0.16f);
        Svf f = new Svf();
        for (int i = 0; i < p.frames(); i++) {
            float t = i / R;
            float e1 = (float) Math.exp(-t * 160), e2 = t > 0.07f ? (float) Math.exp(-(t - 0.07f) * 140) : 0;
            float s = f.bandpass(rnd.nextFloat() * 2 - 1, 3200, 1.2f) * (e1 + e2 * 0.8f);
            p.left[i] = p.right[i] = s * 1.2f;
        }
        return p;
    }

    /** Chamberlin state-variable filter. */
    static final class Svf {
        float low, band;

        float bandpass(float in, float freq, float q) {
            step(in, freq, q);
            return band;
        }

        float lowpass(float in, float freq, float q) {
            step(in, freq, q);
            return low;
        }

        private void step(float in, float freq, float q) {
            float f = (float) (2 * Math.sin(Math.PI * Math.min(freq, R / 6) / R));
            float damp = 1f / q;
            low += f * band;
            float high = in - low - damp * band;
            band += f * high;
        }
    }
}
