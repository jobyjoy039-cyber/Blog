package com.productvideostudio.audio;

import com.productvideostudio.model.Enums.Mood;

import java.util.Random;

/**
 * Composes an original backing track for the video: chords, bass, a melodic layer and drums,
 * arranged for the product's mood and locked to the storyboard's tempo so cuts land on beats.
 * The first two beats are an intro; the groove drops in exactly when the hero is revealed.
 */
public final class MusicGenerator {
    private static final float R = Pcm.RATE;

    /** Beats of intro before the drums drop (matches the director's hero reveal). */
    public static final int INTRO_BEATS = 2;

    private static final int[] MAJOR = {0, 2, 4, 5, 7, 9, 11};
    private static final int[] MINOR = {0, 2, 3, 5, 7, 8, 10};

    private enum Drums { NONE, SOFT, FOUR_ON_FLOOR, HOUSE, DRIVING, LOFI }
    private enum Lead { PLUCK, EPIANO, MARIMBA, NONE }

    private final Mood mood;
    private final float beat;
    private final float total;
    private final Random rnd;
    private final Pcm out;
    private int[] scale;
    private int[] progression;
    private int root;
    private Drums drums;
    private Lead lead;
    private boolean pump;
    private float padBright;

    private MusicGenerator(Mood mood, int bpm, float total, long seed) {
        this.mood = mood;
        this.beat = 60f / bpm;
        this.total = total;
        this.rnd = new Random(seed);
        this.out = Pcm.ofSeconds(total + 1f);
    }

    public static Pcm generate(Mood mood, int bpm, float totalSec, long seed) {
        MusicGenerator g = new MusicGenerator(mood, bpm, totalSec, seed);
        g.arrange();
        g.render();
        return g.out;
    }

    private void arrange() {
        int[] roots = {57, 60, 62, 55, 53, 58};
        root = roots[rnd.nextInt(roots.length)];
        switch (mood) {
            case LUXURY: scale = MINOR; progression = new int[]{0, 5, 2, 6}; drums = Drums.SOFT; lead = Lead.EPIANO; padBright = 0.5f; break;
            case TECH: scale = MAJOR; progression = new int[]{5, 3, 0, 4}; drums = Drums.FOUR_ON_FLOOR; lead = Lead.PLUCK; pump = true; padBright = 0.9f; break;
            case NATURE: scale = MAJOR; progression = new int[]{0, 4, 5, 3}; drums = Drums.NONE; lead = Lead.MARIMBA; padBright = 0.45f; break;
            case PLAYFUL: scale = MAJOR; progression = new int[]{0, 4, 5, 3}; drums = Drums.FOUR_ON_FLOOR; lead = Lead.MARIMBA; padBright = 0.7f; break;
            case FASHION: scale = MINOR; progression = new int[]{0, 5, 6, 4}; drums = Drums.HOUSE; lead = Lead.EPIANO; pump = true; padBright = 0.6f; break;
            case BEAUTY: scale = MAJOR; progression = new int[]{0, 2, 3, 4}; drums = Drums.SOFT; lead = Lead.EPIANO; padBright = 0.5f; break;
            case FOOD: scale = MAJOR; progression = new int[]{0, 3, 4, 3}; drums = Drums.LOFI; lead = Lead.PLUCK; padBright = 0.6f; break;
            case SPORT: scale = MINOR; progression = new int[]{0, 5, 2, 6}; drums = Drums.DRIVING; lead = Lead.PLUCK; pump = true; padBright = 0.8f; break;
            default: scale = MAJOR; progression = new int[]{0, 4, 5, 3}; drums = Drums.LOFI; lead = Lead.EPIANO; padBright = 0.45f;
        }
    }

    private void render() {
        int beats = (int) Math.ceil(total / beat) + 1;
        int bars = beats / 4 + 1;
        float drop = INTRO_BEATS * beat;

        for (int bar = 0; bar < bars; bar++) {
            float barStart = bar * 4 * beat;
            if (barStart > total + 0.5f) break;
            int degree = progression[bar % progression.length];
            int[] chord = chord(degree);
            pad(chord, barStart, 4 * beat, bar == 0 ? 0.6f : 1f);
            if (barStart + 4 * beat > drop) bassBar(chord[0] - 12, barStart, drop);
            leadBar(chord, barStart, drop, bar);
        }
        if (drums != Drums.NONE) {
            for (int b = INTRO_BEATS; b < beats; b++) drumBeat(b * beat, b);
            crash(drop);
        } else {
            for (int b = INTRO_BEATS; b < beats; b++) {
                shaker(b * beat + beat / 2, 0.25f);
                if (b % 4 == 0) shaker(b * beat, 0.15f);
            }
        }
    }

    // ------------------------------------------------------------------------------------
    // Harmony

    private int[] chord(int degree) {
        int[] notes = new int[4];
        for (int k = 0; k < 4; k++) {
            int idx = degree + k * 2;
            notes[k] = root + scale[idx % 7] + 12 * (idx / 7);
        }
        return notes;
    }

    static float hz(int midi) {
        return (float) (440.0 * Math.pow(2, (midi - 69) / 12.0));
    }

    /** Warm detuned-saw pad through a gentle low-pass, with optional sidechain pump. */
    private void pad(int[] chord, float start, float len, float level) {
        int s0 = Math.round(start * R), n = Math.round((len + 0.3f) * R);
        SfxSynth.Svf fl = new SfxSynth.Svf(), fr = new SfxSynth.Svf();
        double[] ph = new double[6];
        float cutoff = 700 + 1500 * padBright;
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float env = Math.min(1, t / 0.35f) * (t > len ? Math.max(0, 1 - (t - len) / 0.3f) : 1);
            float l = 0, r = 0;
            for (int v = 0; v < 3; v++) {
                float f = hz(chord[v]);
                ph[v * 2] += f * 1.003 / R;
                ph[v * 2 + 1] += f * 0.997 / R;
                float s1 = (float) (2 * (ph[v * 2] % 1.0) - 1);
                float s2 = (float) (2 * (ph[v * 2 + 1] % 1.0) - 1);
                l += s1 * 0.7f + s2 * 0.3f;
                r += s2 * 0.7f + s1 * 0.3f;
            }
            float lfo = 1 + 0.25f * (float) Math.sin(2 * Math.PI * 0.2 * (start + t));
            float gain = env * level * 0.05f;
            if (pump && start + t > INTRO_BEATS * beat) {
                float since = (start + t) % beat;
                gain *= 1 - 0.55f * (float) Math.exp(-since * 9);
            }
            out.left[s0 + i] += fl.lowpass(l, cutoff * lfo, 0.8f) * gain;
            out.right[s0 + i] += fr.lowpass(r, cutoff * lfo, 0.8f) * gain;
        }
    }

    private void bassBar(int note, float barStart, float drop) {
        float[] pattern;
        switch (drums) {
            case DRIVING: pattern = new float[]{0, 0.5f, 1, 1.5f, 2, 2.5f, 3, 3.5f}; break;
            case HOUSE: pattern = new float[]{0.5f, 1.5f, 2.5f, 3.5f}; break;
            case FOUR_ON_FLOOR: pattern = new float[]{0, 0.75f, 1.5f, 2, 2.75f, 3.5f}; break;
            case NONE: pattern = new float[]{0, 2}; break;
            default: pattern = new float[]{0, 1.5f, 2, 3.25f};
        }
        for (float p : pattern) {
            float at = barStart + p * beat;
            if (at < drop - 0.001f) continue;
            float len = drums == Drums.DRIVING ? beat * 0.45f : beat * (drums == Drums.NONE ? 1.8f : 0.8f);
            bassNote(note, at, len);
        }
    }

    private void bassNote(int note, float start, float len) {
        int s0 = Math.round(start * R), n = Math.round((len + 0.05f) * R);
        float f = hz(note);
        double ph = 0;
        SfxSynth.Svf lp = new SfxSynth.Svf();
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            ph += f / R;
            float saw = (float) (2 * (ph % 1.0) - 1);
            float sine = (float) Math.sin(2 * Math.PI * ph);
            float env = Math.min(1, t * 400) * (t < len ? 1 : Math.max(0, 1 - (t - len) / 0.05f)) * (float) Math.exp(-t * 1.5);
            float cutoff = 180 + 900 * (float) Math.exp(-t * 12);
            float s = lp.lowpass(saw * 0.5f + sine * 0.8f, cutoff, 0.9f) * env * 0.32f;
            out.left[s0 + i] += s;
            out.right[s0 + i] += s;
        }
    }

    private void leadBar(int[] chord, float barStart, float drop, int bar) {
        if (lead == Lead.NONE) return;
        int[] arp = {chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12, chord[3] + 12, chord[2] + 12, chord[1] + 12, chord[2] + 12};
        switch (lead) {
            case PLUCK: {
                float step = beat / 2;
                for (int k = 0; k < 8; k++) {
                    float at = barStart + k * step;
                    float vel = (k % 2 == 0 ? 0.16f : 0.11f) * (at < drop ? 0.5f : 1f);
                    pluck(arp[k], at, vel, (k % 2 == 0 ? -0.3f : 0.3f));
                }
                break;
            }
            case MARIMBA: {
                float step = beat / 2;
                for (int k = 0; k < 8; k++) {
                    if (rnd.nextFloat() < 0.2f && k % 2 == 1) continue;
                    float at = barStart + k * step;
                    marimba(arp[k] + (k == 4 ? 12 : 0), at, 0.2f * (at < drop ? 0.6f : 1f), (k % 3 - 1) * 0.35f);
                }
                break;
            }
            case EPIANO: {
                // Sparse chord hits and a simple top-line.
                float[] hits = {0, 1.5f, 2.5f};
                for (float h : hits) {
                    float at = barStart + h * beat;
                    for (int v = 1; v < 4; v++) epiano(chord[v], at, beat * 1.2f, 0.07f, (v - 2) * 0.3f);
                }
                if (bar % 2 == 1) epiano(chord[2] + 12, barStart + 3 * beat, beat, 0.08f, 0.2f);
                break;
            }
            default:
        }
    }

    /** Karplus-Strong plucked string. */
    private void pluck(int note, float start, float vel, float pan) {
        float f = hz(note);
        int period = Math.max(2, Math.round(R / f));
        float[] buf = new float[period];
        for (int i = 0; i < period; i++) buf[i] = rnd.nextFloat() * 2 - 1;
        int s0 = Math.round(start * R), n = Math.round(0.6f * R);
        int idx = 0;
        float prev = 0;
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float v = buf[idx];
            float next = buf[(idx + 1) % period];
            float filtered = 0.996f * 0.5f * (v + next);
            buf[idx] = filtered;
            idx = (idx + 1) % period;
            float s = (v * 0.6f + prev * 0.4f) * vel;
            prev = v;
            out.left[s0 + i] += s * (1 - pan);
            out.right[s0 + i] += s * (1 + pan);
        }
    }

    private void marimba(int note, float start, float vel, float pan) {
        float f = hz(note);
        int s0 = Math.round(start * R), n = Math.round(0.5f * R);
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float s = (float) (Math.sin(2 * Math.PI * f * t) * Math.exp(-t * 9)
                    + 0.35 * Math.sin(2 * Math.PI * f * 4 * t) * Math.exp(-t * 40)
                    + 0.1 * Math.sin(2 * Math.PI * f * 9.2 * t) * Math.exp(-t * 90));
            s *= vel * Math.min(1, t * 1500);
            out.left[s0 + i] += s * (1 - pan);
            out.right[s0 + i] += s * (1 + pan);
        }
    }

    /** Two-operator FM electric piano. */
    private void epiano(int note, float start, float len, float vel, float pan) {
        float f = hz(note);
        int s0 = Math.round(start * R), n = Math.round((len + 0.6f) * R);
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            double index = 1.6 * Math.exp(-t * 5);
            double mod = Math.sin(2 * Math.PI * f * t) * index;
            double s = Math.sin(2 * Math.PI * f * t + mod) * Math.exp(-t * 2.2)
                    + 0.2 * Math.sin(2 * Math.PI * f * 14 * t) * Math.exp(-t * 30);
            float env = (float) (Math.min(1, t * 800) * (t < len ? 1 : Math.max(0, 1 - (t - len) / 0.6)));
            float v = (float) s * env * vel;
            out.left[s0 + i] += v * (1 - pan);
            out.right[s0 + i] += v * (1 + pan);
        }
    }

    // ------------------------------------------------------------------------------------
    // Drums

    private void drumBeat(float at, int b) {
        int inBar = b % 4;
        switch (drums) {
            case SOFT:
                if (inBar == 0 || inBar == 2) kick(at, 0.55f);
                if (inBar == 1 || inBar == 3) snap(at, 0.25f);
                hat(at + beat / 2, 0.08f, false);
                break;
            case FOUR_ON_FLOOR:
                kick(at, 0.8f);
                if (inBar == 1 || inBar == 3) clap(at, 0.35f);
                hat(at + beat / 2, 0.14f, false);
                hat(at + beat / 4, 0.05f, false);
                hat(at + 3 * beat / 4, 0.05f, false);
                break;
            case HOUSE:
                kick(at, 0.85f);
                if (inBar == 1 || inBar == 3) clap(at, 0.3f);
                hat(at + beat / 2, 0.16f, true);
                break;
            case DRIVING:
                kick(at, 0.9f);
                if (inBar == 1 || inBar == 3) snare(at, 0.45f);
                for (int k = 0; k < 4; k++) hat(at + k * beat / 4, k % 2 == 0 ? 0.1f : 0.06f, false);
                break;
            case LOFI:
                if (inBar == 0) kick(at, 0.6f);
                if (inBar == 2) { kick(at + beat / 2, 0.45f); }
                if (inBar == 1 || inBar == 3) snare(at, 0.28f);
                hat(at, 0.06f, false);
                hat(at + beat * 0.58f, 0.05f, false);
                break;
            default:
        }
    }

    private void kick(float start, float vel) {
        int s0 = Math.round(start * R), n = Math.round(0.4f * R);
        double ph = 0;
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float f = 45 + 110 * (float) Math.exp(-t * 30);
            ph += 2 * Math.PI * f / R;
            float s = (float) Math.sin(ph) * (float) Math.exp(-t * 7) + (t < 0.004f ? 0.3f * (1 - t / 0.004f) : 0);
            out.left[s0 + i] += s * vel * 0.6f;
            out.right[s0 + i] += s * vel * 0.6f;
        }
    }

    private void snare(float start, float vel) {
        int s0 = Math.round(start * R), n = Math.round(0.22f * R);
        SfxSynth.Svf bp = new SfxSynth.Svf();
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float noise = bp.bandpass(rnd.nextFloat() * 2 - 1, 2200, 0.9f) * (float) Math.exp(-t * 16);
            float tone = (float) Math.sin(2 * Math.PI * 190 * t) * (float) Math.exp(-t * 30);
            float s = (noise * 1.2f + tone * 0.5f) * vel;
            out.left[s0 + i] += s;
            out.right[s0 + i] += s;
        }
    }

    private void clap(float start, float vel) {
        SfxSynth.Svf bp = new SfxSynth.Svf();
        int s0 = Math.round(start * R), n = Math.round(0.2f * R);
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float env = 0;
            for (int k = 0; k < 3; k++) {
                float tk = t - k * 0.011f;
                if (tk >= 0) env += (float) Math.exp(-tk * (k == 2 ? 20 : 90));
            }
            float s = bp.bandpass(rnd.nextFloat() * 2 - 1, 1500, 1.1f) * env * vel;
            out.left[s0 + i] += s * 0.9f;
            out.right[s0 + i] += s * 1.1f;
        }
    }

    private void snap(float start, float vel) {
        SfxSynth.Svf bp = new SfxSynth.Svf();
        int s0 = Math.round(start * R), n = Math.round(0.08f * R);
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float s = bp.bandpass(rnd.nextFloat() * 2 - 1, 2800, 2f) * (float) Math.exp(-t * 60) * vel * 1.4f;
            out.left[s0 + i] += s;
            out.right[s0 + i] += s;
        }
    }

    private void hat(float start, float vel, boolean open) {
        int s0 = Math.round(start * R), n = Math.round((open ? 0.3f : 0.06f) * R);
        SfxSynth.Svf lp = new SfxSynth.Svf();
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float noise = rnd.nextFloat() * 2 - 1;
            float high = noise - lp.lowpass(noise, 7000, 0.7f);
            float s = high * (float) Math.exp(-t * (open ? 12 : 70)) * vel;
            out.left[s0 + i] += s * 0.85f;
            out.right[s0 + i] += s;
        }
    }

    private void shaker(float start, float vel) {
        int s0 = Math.round(start * R), n = Math.round(0.09f * R);
        SfxSynth.Svf bp = new SfxSynth.Svf();
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float env = Math.min(1, t * 120) * (float) Math.exp(-t * 45);
            float s = bp.bandpass(rnd.nextFloat() * 2 - 1, 6500, 1.5f) * env * vel;
            out.left[s0 + i] += s;
            out.right[s0 + i] += s * 0.8f;
        }
    }

    private void crash(float start) {
        int s0 = Math.round(start * R), n = Math.round(1.6f * R);
        SfxSynth.Svf lp = new SfxSynth.Svf(), lp2 = new SfxSynth.Svf();
        for (int i = 0; i < n && s0 + i < out.frames(); i++) {
            float t = i / R;
            float nl = rnd.nextFloat() * 2 - 1, nr = rnd.nextFloat() * 2 - 1;
            float env = (float) Math.exp(-t * 2.6) * 0.1f;
            out.left[s0 + i] += (nl - lp.lowpass(nl, 4000, 0.7f)) * env;
            out.right[s0 + i] += (nr - lp2.lowpass(nr, 4000, 0.7f)) * env;
        }
    }
}
