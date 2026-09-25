package com.productvideostudio.audio;

/**
 * Estimates tempo and the first downbeat of a music track so scene cuts can follow the user's
 * own song: an onset-strength envelope, autocorrelation for the period, then phase alignment.
 */
public final class BeatDetector {
    public int bpm;
    /** Seconds from the start of the analyzed audio to the first strong beat. */
    public float offset;
    /** 0..1, how periodic the track is. Low values mean "don't trust the grid". */
    public float confidence;

    private static final int HOP = 441; // 10 ms at 44.1 kHz

    public static BeatDetector analyze(Pcm pcm) {
        BeatDetector d = new BeatDetector();
        int frames = pcm.frames();
        int n = frames / HOP;
        if (n < 400) {
            d.bpm = 0;
            return d;
        }
        // Onset strength: rectified rise in log energy of a high-passed mono mix.
        float[] energy = new float[n];
        float prevSample = 0;
        for (int h = 0; h < n; h++) {
            double e = 0;
            for (int i = h * HOP; i < (h + 1) * HOP; i++) {
                float m = 0.5f * (pcm.left[i] + pcm.right[i]);
                float hp = m - prevSample;
                prevSample = m;
                e += hp * hp + 0.2 * m * m;
            }
            energy[h] = (float) Math.log(1e-6 + e);
        }
        float[] onset = new float[n];
        for (int h = 1; h < n; h++) onset[h] = Math.max(0, energy[h] - energy[h - 1]);
        // Remove the local mean so sustained loudness doesn't count as a beat.
        float[] o = new float[n];
        int w = 15;
        for (int h = 0; h < n; h++) {
            float s = 0;
            int c = 0;
            for (int k = Math.max(0, h - w); k < Math.min(n, h + w); k++) { s += onset[k]; c++; }
            o[h] = Math.max(0, onset[h] - s / c);
        }

        // Autocorrelation over 70..180 BPM, weighted toward ~115 BPM.
        int minLag = Math.round(60f / 180f * 100f), maxLag = Math.round(60f / 70f * 100f);
        double best = -1, zero = 0;
        int bestLag = 0;
        for (int h = 0; h < n; h++) zero += o[h] * o[h];
        for (int lag = minLag; lag <= maxLag; lag++) {
            double s = 0;
            for (int h = lag; h < n; h++) s += o[h] * o[h - lag];
            double bpm = 6000.0 / lag;
            double weight = Math.exp(-Math.pow(Math.log(bpm / 115.0) / 0.5, 2) / 2);
            s *= weight;
            if (s > best) { best = s; bestLag = lag; }
        }
        if (bestLag == 0 || zero <= 0) return d;
        d.confidence = (float) Math.min(1, best / zero * 2.5);
        d.bpm = Math.round(6000f / bestLag);

        // Phase: the offset whose comb of beats collects the most onset energy.
        double bestPhase = -1;
        int phase = 0;
        for (int ph = 0; ph < bestLag; ph++) {
            double s = 0;
            for (int h = ph; h < n; h += bestLag) s += o[h];
            if (s > bestPhase) { bestPhase = s; phase = ph; }
        }
        d.offset = phase / 100f;
        return d;
    }
}
