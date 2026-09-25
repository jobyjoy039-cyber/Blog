package com.productvideostudio.audio;

import android.content.Context;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Narration with the phone's built-in text-to-speech engine (offline with most voices).
 * Call from a background thread; it blocks until every line is synthesized.
 */
public final class VoiceOver {
    private static final String TAG = "VoiceOver";

    private VoiceOver() {}

    /** Returns one clip per line (null entries for lines that failed). */
    public static List<Pcm> synthesize(Context ctx, List<String> lines, File workDir) {
        List<Pcm> out = new ArrayList<>();
        CountDownLatch ready = new CountDownLatch(1);
        final int[] status = {TextToSpeech.ERROR};
        TextToSpeech tts = new TextToSpeech(ctx.getApplicationContext(), s -> {
            status[0] = s;
            ready.countDown();
        });
        try {
            if (!ready.await(10, TimeUnit.SECONDS) || status[0] != TextToSpeech.SUCCESS) {
                Log.w(TAG, "TTS engine unavailable");
                for (int i = 0; i < lines.size(); i++) out.add(null);
                return out;
            }
            int lang = tts.setLanguage(Locale.getDefault());
            if (lang == TextToSpeech.LANG_MISSING_DATA || lang == TextToSpeech.LANG_NOT_SUPPORTED) tts.setLanguage(Locale.US);
            tts.setSpeechRate(0.98f);
            tts.setPitch(1.0f);
            for (int i = 0; i < lines.size(); i++) {
                File wav = new File(workDir, "vo_" + i + ".wav");
                CountDownLatch done = new CountDownLatch(1);
                final boolean[] ok = {false};
                String id = "line" + i;
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String utteranceId) {}
                    @Override public void onDone(String utteranceId) { ok[0] = true; done.countDown(); }
                    @Override public void onError(String utteranceId) { done.countDown(); }
                });
                int r = tts.synthesizeToFile(lines.get(i), new Bundle(), wav, id);
                if (r != TextToSpeech.SUCCESS || !done.await(20, TimeUnit.SECONDS) || !ok[0]) {
                    out.add(null);
                    continue;
                }
                try {
                    out.add(readWav(wav));
                } catch (IOException e) {
                    Log.w(TAG, "bad TTS output", e);
                    out.add(null);
                }
                //noinspection ResultOfMethodCallIgnored
                wav.delete();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            tts.shutdown();
        }
        while (out.size() < lines.size()) out.add(null);
        return out;
    }

    /** Minimal PCM WAV reader (8/16-bit, mono/stereo). */
    static Pcm readWav(File f) throws IOException {
        try (RandomAccessFile raf = new RandomAccessFile(f, "r")) {
            byte[] all = new byte[(int) raf.length()];
            raf.readFully(all);
            if (all.length < 44 || all[0] != 'R' || all[1] != 'I' || all[2] != 'F' || all[3] != 'F') throw new IOException("not RIFF");
            int pos = 12, channels = 1, rate = 22050, bits = 16, dataPos = -1, dataLen = 0;
            while (pos + 8 <= all.length) {
                String id = new String(all, pos, 4, "US-ASCII");
                int len = le32(all, pos + 4);
                if (id.equals("fmt ")) {
                    channels = le16(all, pos + 10);
                    rate = le32(all, pos + 12);
                    bits = le16(all, pos + 22);
                } else if (id.equals("data")) {
                    dataPos = pos + 8;
                    dataLen = Math.min(len < 0 ? Integer.MAX_VALUE : len, all.length - dataPos);
                    break;
                }
                pos += 8 + len + (len & 1);
            }
            if (dataPos < 0) throw new IOException("no data chunk");
            int bytesPer = bits / 8;
            int frames = dataLen / (bytesPer * channels);
            float[] l = new float[frames], r = new float[frames];
            for (int i = 0; i < frames; i++) {
                int base = dataPos + i * bytesPer * channels;
                float a = bits == 8 ? ((all[base] & 0xFF) - 128) / 128f : (short) le16(all, base) / 32768f;
                float b = a;
                if (channels > 1) {
                    int b2 = base + bytesPer;
                    b = bits == 8 ? ((all[b2] & 0xFF) - 128) / 128f : (short) le16(all, b2) / 32768f;
                }
                l[i] = a;
                r[i] = b;
            }
            return AudioDecoder.resample(l, r, frames, rate);
        }
    }

    static int le16(byte[] b, int p) {
        return (b[p] & 0xFF) | ((b[p + 1] & 0xFF) << 8);
    }

    static int le32(byte[] b, int p) {
        return (b[p] & 0xFF) | ((b[p + 1] & 0xFF) << 8) | ((b[p + 2] & 0xFF) << 16) | ((b[p + 3] & 0xFF) << 24);
    }
}
