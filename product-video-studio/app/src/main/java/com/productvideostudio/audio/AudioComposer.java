package com.productvideostudio.audio;

import android.content.Context;
import android.util.Log;

import com.productvideostudio.model.Project;
import com.productvideostudio.model.Storyboard;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Builds the final soundtrack: music (generated or the user's track, looped if short), sound
 * effects at the director's cue points, voice-over, and ducking of the music under the voice.
 */
public final class AudioComposer {
    private static final String TAG = "AudioComposer";

    private AudioComposer() {}

    /** Tempo and downbeat of a user track, or null if it has no clear beat. */
    public static BeatDetector detectBeats(File music) {
        try {
            Pcm pcm = AudioDecoder.decode(music.getAbsolutePath(), 40f);
            BeatDetector d = BeatDetector.analyze(pcm);
            return d.bpm > 0 && d.confidence > 0.12f ? d : null;
        } catch (IOException | RuntimeException e) {
            Log.w(TAG, "beat detection failed", e);
            return null;
        }
    }

    public static Pcm compose(Context ctx, Project p, Storyboard b, File projectDir, File workDir) {
        float total = b.totalSec;
        Pcm mix = Pcm.ofSeconds(total);

        // Music.
        Pcm music = null;
        if (Project.MUSIC_FILE.equals(p.musicMode) && p.musicFile != null) {
            try {
                music = AudioDecoder.decode(new File(projectDir, p.musicFile).getAbsolutePath(), total + 5);
                music = loopTo(music, total);
            } catch (IOException | RuntimeException e) {
                Log.w(TAG, "could not decode music, using generated score", e);
            }
        }
        if (music == null && !Project.MUSIC_NONE.equals(p.musicMode)) {
            music = MusicGenerator.generate(b.mood, b.bpm, total, p.seed);
            music.master(1f);
        }
        if (music != null) {
            float peak = music.peak();
            mix.mix(music, 0, peak > 0 ? 0.55f / peak : 0f, 0f);
        }

        // Voice-over.
        Pcm voice = Pcm.ofSeconds(total);
        boolean hasVoice = false;
        if (Project.VOICE_FILE.equals(p.voiceMode) && p.voiceFile != null) {
            try {
                Pcm v = AudioDecoder.decode(new File(projectDir, p.voiceFile).getAbsolutePath(), total);
                voice.mix(v, 0.3f, normGain(v, 0.9f), 0f);
                hasVoice = true;
            } catch (IOException | RuntimeException e) {
                Log.w(TAG, "could not decode voice-over", e);
            }
        } else if (Project.VOICE_TTS.equals(p.voiceMode) && !b.voice.isEmpty()) {
            List<String> lines = new ArrayList<>();
            for (Storyboard.VoiceLine l : b.voice) lines.add(l.text);
            List<Pcm> clips = VoiceOver.synthesize(ctx, lines, workDir);
            float cursor = 0;
            for (int i = 0; i < clips.size(); i++) {
                Pcm c = clips.get(i);
                if (c == null) continue;
                float len = c.frames() / (float) Pcm.RATE;
                float at = Math.max(b.voice.get(i).time, cursor + 0.15f);
                if (at + len > total - 0.1f) {
                    // The closing line matters most: pull it earlier if it fits at all.
                    if (i == clips.size() - 1 && len < total * 0.4f) at = Math.max(cursor + 0.1f, total - 0.15f - len);
                    else continue;
                }
                voice.mix(c, at, normGain(c, 0.9f), 0f);
                cursor = at + len;
                hasVoice = true;
            }
        }
        if (hasVoice) duck(mix, voice, 0.62f);

        // Sound effects.
        long seed = p.seed * 31;
        for (Storyboard.SfxCue cue : b.sfx) {
            Pcm s = SfxSynth.make(cue.type, cue.length, seed++);
            mix.mix(s, Math.max(0, cue.time), cue.gain, cue.pan);
        }
        if (hasVoice) mix.mix(voice, 0, 1f, 0f);

        mix.fadeIn(0.03f);
        mix.fadeOut(Math.min(1.2f, total * 0.1f));
        mix.master(0.89f);
        return mix;
    }

    /** Repeats a short track with a 1 s crossfade until it covers {@code seconds}. */
    static Pcm loopTo(Pcm src, float seconds) {
        int need = Math.round(seconds * Pcm.RATE);
        if (src.frames() >= need) return src;
        int xf = Math.min(Pcm.RATE, src.frames() / 4);
        Pcm out = new Pcm(need);
        int pos = 0;
        while (pos < need) {
            for (int i = 0; i < src.frames() && pos + i < need; i++) {
                float g = 1;
                if (pos > 0 && i < xf) g = i / (float) xf;
                out.left[pos + i] = out.left[pos + i] * (1 - g) + src.left[i] * g;
                out.right[pos + i] = out.right[pos + i] * (1 - g) + src.right[i] * g;
            }
            pos += src.frames() - xf;
        }
        return out;
    }

    static float normGain(Pcm p, float target) {
        float peak = p.peak();
        return peak > 1e-4f ? target / peak : 0f;
    }

    /** Lowers {@code music} wherever {@code voice} is active (attack 40 ms, release 350 ms). */
    static void duck(Pcm music, Pcm voice, float depth) {
        float attack = (float) Math.exp(-1.0 / (0.04 * Pcm.RATE));
        float release = (float) Math.exp(-1.0 / (0.35 * Pcm.RATE));
        float env = 0;
        int n = Math.min(music.frames(), voice.frames());
        for (int i = 0; i < n; i++) {
            float level = Math.max(Math.abs(voice.left[i]), Math.abs(voice.right[i]));
            float target = Math.min(1f, level * 6f);
            env = target > env ? attack * env + (1 - attack) * target : release * env + (1 - release) * target;
            float g = 1 - depth * env;
            music.left[i] *= g;
            music.right[i] *= g;
        }
    }
}
