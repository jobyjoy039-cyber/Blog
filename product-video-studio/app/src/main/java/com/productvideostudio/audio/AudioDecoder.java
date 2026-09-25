package com.productvideostudio.audio;

import android.media.AudioFormat;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.ShortBuffer;

/** Decodes any audio file Android supports (MP3, AAC, M4A, OGG, WAV, FLAC…) to 44.1 kHz stereo. */
public final class AudioDecoder {
    private AudioDecoder() {}

    /**
     * @param maxSeconds stop after this much audio (keeps memory bounded for long songs)
     */
    public static Pcm decode(String path, float maxSeconds) throws IOException {
        MediaExtractor ex = new MediaExtractor();
        ex.setDataSource(path);
        int track = -1;
        MediaFormat format = null;
        for (int i = 0; i < ex.getTrackCount(); i++) {
            MediaFormat f = ex.getTrackFormat(i);
            String mime = f.getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.startsWith("audio/")) { track = i; format = f; break; }
        }
        if (track < 0) {
            ex.release();
            throw new IOException("No audio track in " + path);
        }
        ex.selectTrack(track);
        int srcRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE);
        int channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
        MediaCodec codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));
        codec.configure(format, null, null, 0);
        codec.start();

        int maxFrames = Math.round(maxSeconds * srcRate);
        float[] l = new float[Math.min(maxFrames, srcRate * 30)];
        float[] r = new float[l.length];
        int frames = 0;
        boolean floatPcm = false;
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        boolean inputDone = false, outputDone = false;
        try {
            while (!outputDone && frames < maxFrames) {
                if (!inputDone) {
                    int in = codec.dequeueInputBuffer(10000);
                    if (in >= 0) {
                        ByteBuffer buf = codec.getInputBuffer(in);
                        int size = ex.readSampleData(buf, 0);
                        if (size < 0) {
                            codec.queueInputBuffer(in, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            codec.queueInputBuffer(in, 0, size, ex.getSampleTime(), 0);
                            ex.advance();
                        }
                    }
                }
                int out = codec.dequeueOutputBuffer(info, 10000);
                if (out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    MediaFormat of = codec.getOutputFormat();
                    srcRate = of.getInteger(MediaFormat.KEY_SAMPLE_RATE);
                    channels = of.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
                    floatPcm = of.containsKey(MediaFormat.KEY_PCM_ENCODING)
                            && of.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT;
                    maxFrames = Math.round(maxSeconds * srcRate);
                } else if (out >= 0) {
                    ByteBuffer buf = codec.getOutputBuffer(out);
                    buf.position(info.offset);
                    buf.limit(info.offset + info.size);
                    buf.order(ByteOrder.nativeOrder());
                    int samples = info.size / (floatPcm ? 4 : 2);
                    int n = samples / Math.max(1, channels);
                    if (frames + n > l.length) {
                        int cap = Math.max(frames + n, l.length * 2);
                        l = java.util.Arrays.copyOf(l, cap);
                        r = java.util.Arrays.copyOf(r, cap);
                    }
                    if (floatPcm) {
                        java.nio.FloatBuffer fb = buf.asFloatBuffer();
                        for (int i = 0; i < n; i++) {
                            float a = fb.get(i * channels);
                            l[frames + i] = a;
                            r[frames + i] = channels > 1 ? fb.get(i * channels + 1) : a;
                        }
                    } else {
                        ShortBuffer sb = buf.asShortBuffer();
                        for (int i = 0; i < n; i++) {
                            float a = sb.get(i * channels) / 32768f;
                            l[frames + i] = a;
                            r[frames + i] = channels > 1 ? sb.get(i * channels + 1) / 32768f : a;
                        }
                    }
                    frames += n;
                    codec.releaseOutputBuffer(out, false);
                    if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) outputDone = true;
                }
            }
        } finally {
            codec.stop();
            codec.release();
            ex.release();
        }
        return resample(l, r, Math.min(frames, maxFrames), srcRate);
    }

    /** Linear-interpolation resampler to {@link Pcm#RATE}. */
    static Pcm resample(float[] l, float[] r, int frames, int srcRate) {
        if (frames <= 0) return new Pcm(1);
        if (srcRate == Pcm.RATE) {
            Pcm p = new Pcm(Math.max(1, frames));
            System.arraycopy(l, 0, p.left, 0, frames);
            System.arraycopy(r, 0, p.right, 0, frames);
            return p;
        }
        double ratio = srcRate / (double) Pcm.RATE;
        int outFrames = Math.max(1, (int) (frames / ratio));
        Pcm p = new Pcm(outFrames);
        for (int i = 0; i < outFrames; i++) {
            double pos = i * ratio;
            int j = (int) pos;
            float f = (float) (pos - j);
            int k = Math.min(frames - 1, j + 1);
            j = Math.min(frames - 1, j);
            p.left[i] = l[j] + (l[k] - l[j]) * f;
            p.right[i] = r[j] + (r[k] - r[j]) * f;
        }
        return p;
    }
}
