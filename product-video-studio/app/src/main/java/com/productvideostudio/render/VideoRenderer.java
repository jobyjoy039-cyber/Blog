package com.productvideostudio.render;

import android.content.Context;
import android.graphics.Bitmap;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.opengl.GLES20;
import android.util.Log;
import android.view.Surface;

import com.productvideostudio.analysis.Bitmaps;
import com.productvideostudio.audio.AudioComposer;
import com.productvideostudio.audio.Pcm;
import com.productvideostudio.director.CreativeDirector;
import com.productvideostudio.model.Enums.SceneType;
import com.productvideostudio.model.ImageAnalysis;
import com.productvideostudio.model.Project;
import com.productvideostudio.model.Storyboard;
import com.productvideostudio.model.Storyboard.Scene;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CancellationException;

/**
 * Renders a storyboard to a publish-ready MP4: 1080×1920 H.264 (High profile when available),
 * 30 or 60 fps, AAC stereo audio. Frames are drawn with OpenGL straight into the hardware
 * encoder's input surface, so nothing is copied through the CPU.
 */
public final class VideoRenderer {
    private static final String TAG = "VideoRenderer";
    private static final String VIDEO_MIME = MediaFormat.MIMETYPE_VIDEO_AVC;
    private static final String AUDIO_MIME = MediaFormat.MIMETYPE_AUDIO_AAC;

    public interface Listener {
        void onProgress(String stage, float fraction);
        boolean isCancelled();
    }

    private final Context ctx;
    private final Project project;
    private final Storyboard board;
    private final File projectDir;
    private final Listener listener;

    private MediaCodec encoder;
    private MediaMuxer muxer;
    private int videoTrack = -1, audioTrack = -1;
    private boolean muxerStarted;
    private MediaFormat audioFormat;
    private final List<AudioSample> audioSamples = new ArrayList<>();
    private int audioCursor;
    private final MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();

    private final Map<Integer, SceneAssets> assets = new HashMap<>();
    private Gl.Texture logo;
    private int maxTexture = 2048;

    private static final class AudioSample {
        final byte[] data;
        final long pts;
        final int flags;
        AudioSample(byte[] data, long pts, int flags) { this.data = data; this.pts = pts; this.flags = flags; }
    }

    private VideoRenderer(Context ctx, Project project, File projectDir, Listener listener) {
        this.ctx = ctx;
        this.project = project;
        this.board = project.storyboard;
        this.projectDir = projectDir;
        this.listener = listener;
    }

    public static void render(Context ctx, Project project, File projectDir, File out, Listener listener) throws IOException {
        if (project.storyboard == null || project.storyboard.scenes.isEmpty()) throw new IllegalStateException("No storyboard");
        new VideoRenderer(ctx, project, projectDir, listener).run(out);
    }

    private void run(File out) throws IOException {
        File work = new File(ctx.getCacheDir(), "render");
        //noinspection ResultOfMethodCallIgnored
        work.mkdirs();
        File partial = new File(out.getParentFile(), out.getName() + ".part");

        listener.onProgress("Composing music and sound", 0.01f);
        Pcm audio = AudioComposer.compose(ctx, project, board, projectDir, work);
        checkCancel();
        listener.onProgress("Encoding audio", 0.05f);
        encodeAudio(audio);
        checkCancel();

        int[] size = chooseSize();
        int width = size[0], height = size[1];
        int fps = board.fps;
        int frames = Math.round(board.totalSec * fps);

        Surface input = createEncoder(width, height, fps);
        muxer = new MediaMuxer(partial.getAbsolutePath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
        Gl.Egl egl = null;
        Compositor comp = null;
        boolean ok = false;
        try {
            egl = new Gl.Egl(input);
            int[] mt = new int[1];
            GLES20.glGetIntegerv(GLES20.GL_MAX_TEXTURE_SIZE, mt, 0);
            maxTexture = Math.max(1024, Math.min(4096, mt[0]));
            comp = new Compositor(width, height, board);
            loadLogo();

            float beat = board.beatSec();
            Compositor.Frame fa = new Compositor.Frame(), fb = new Compositor.Frame();
            for (int f = 0; f < frames; f++) {
                checkCancel();
                float t = f / (float) fps;
                drainEncoder(false);

                int cur = sceneAt(t);
                Scene a = board.scenes.get(cur), b = null;
                int ia = cur, ib = -1;
                float p = 0;
                if (cur > 0) {
                    float half = transition(cur - 1) / 2f;
                    if (half > 0 && t < a.start + half) {
                        ia = cur - 1;
                        ib = cur;
                        p = (t - (a.start - half)) / (2 * half);
                    }
                }
                if (ib < 0 && cur < board.scenes.size() - 1) {
                    float half = transition(cur) / 2f;
                    if (half > 0 && t >= a.end() - half) {
                        ia = cur;
                        ib = cur + 1;
                        p = (t - (a.end() - half)) / (2 * half);
                    }
                }
                a = board.scenes.get(ia);
                timing(ia, t, fps, beat, fa);
                SceneAssets aa = ensure(ia, width);
                SceneAssets ab = null;
                if (ib >= 0) {
                    b = board.scenes.get(ib);
                    timing(ib, t, fps, beat, fb);
                    ab = ensure(ib, width);
                }
                comp.frame(a, aa, fa, b, ab, fb, p, t);
                evictBefore(ia - 1);

                egl.presentationTime(f * 1_000_000_000L / fps);
                egl.swap();
                if (f % 3 == 0) listener.onProgress("Rendering frame " + (f + 1) + " of " + frames, 0.06f + 0.9f * f / frames);
            }
            drainEncoder(true);
            writeRemainingAudio();
            ok = true;
        } finally {
            for (SceneAssets s : assets.values()) s.release();
            assets.clear();
            if (logo != null) logo.release();
            if (comp != null) comp.release();
            if (egl != null) egl.release();
            input.release();
            try { encoder.stop(); } catch (RuntimeException ignored) {}
            encoder.release();
            if (muxerStarted) {
                try { muxer.stop(); } catch (RuntimeException e) { ok = false; Log.e(TAG, "muxer stop", e); }
            }
            muxer.release();
            if (!ok) //noinspection ResultOfMethodCallIgnored
                partial.delete();
        }
        if (out.exists()) //noinspection ResultOfMethodCallIgnored
            out.delete();
        if (!partial.renameTo(out)) throw new IOException("Could not save video");
        listener.onProgress("Done", 1f);
    }

    private void checkCancel() {
        if (listener.isCancelled()) throw new CancellationException("Cancelled");
    }

    // ------------------------------------------------------------------------------------
    // Timeline

    private float transition(int i) {
        return CreativeDirector.transitionSeconds(board.scenes.get(i));
    }

    private int sceneAt(float t) {
        for (int i = board.scenes.size() - 1; i >= 0; i--) if (t >= board.scenes.get(i).start) return i;
        return 0;
    }

    private void timing(int i, float t, int fps, float beat, Compositor.Frame out) {
        Scene sc = board.scenes.get(i);
        float visStart = sc.start - (i > 0 ? transition(i - 1) / 2f : 0);
        float visEnd = sc.end() + (i < board.scenes.size() - 1 ? transition(i) / 2f : 0);
        float span = Math.max(0.01f, visEnd - visStart);
        out.u = (t - visStart) / span;
        out.local = t - sc.start;
        out.time = t;
        out.pose = CameraRig.pose(sc, out.u, out.local, t, beat);
        float tp = t - 1f / fps;
        out.previous = CameraRig.pose(sc, (tp - visStart) / span, tp - sc.start, tp, beat);
    }

    // ------------------------------------------------------------------------------------
    // Assets

    private SceneAssets ensure(int i, int width) {
        SceneAssets s = assets.get(i);
        if (s != null) return s;
        Scene sc = board.scenes.get(i);
        int img = Math.max(0, Math.min(project.images.size() - 1, sc.image));
        String file = project.images.get(img);
        ImageAnalysis a = project.analysisFor(file);
        s = SceneAssets.load(sc, new File(projectDir, file), a, maxTexture);
        s.texts = new Gl.Texture[sc.texts.size()];
        for (int k = 0; k < sc.texts.size(); k++) {
            Bitmap bmp = TextPainter.render(sc.texts.get(k), board, width);
            s.texts[k] = Gl.upload(bmp, false, maxTexture);
            bmp.recycle();
        }
        if (sc.type == SceneType.CALL_TO_ACTION) s.logo = logo;
        assets.put(i, s);
        return s;
    }

    private void evictBefore(int i) {
        Iterator<Map.Entry<Integer, SceneAssets>> it = assets.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<Integer, SceneAssets> e = it.next();
            if (e.getKey() < i) {
                e.getValue().release();
                it.remove();
            }
        }
    }

    private void loadLogo() {
        if (project.logo == null) return;
        File f = new File(projectDir, project.logo);
        if (!f.exists()) return;
        Bitmap bmp = Bitmaps.decode(f.getAbsolutePath(), 640);
        if (bmp != null) {
            logo = Gl.upload(bmp, false, maxTexture);
            bmp.recycle();
        }
    }

    // ------------------------------------------------------------------------------------
    // Encoding

    /** 1080×1920 when the device's encoder supports it, otherwise 720×1280. */
    private static int[] chooseSize() {
        try {
            MediaCodecList list = new MediaCodecList(MediaCodecList.REGULAR_CODECS);
            for (MediaCodecInfo ci : list.getCodecInfos()) {
                if (!ci.isEncoder()) continue;
                for (String type : ci.getSupportedTypes()) {
                    if (!type.equalsIgnoreCase(VIDEO_MIME)) continue;
                    MediaCodecInfo.VideoCapabilities vc = ci.getCapabilitiesForType(type).getVideoCapabilities();
                    if (vc != null && vc.isSizeSupported(1080, 1920)) return new int[]{1080, 1920};
                }
            }
        } catch (RuntimeException e) {
            Log.w(TAG, "codec query failed", e);
        }
        return new int[]{720, 1280};
    }

    private Surface createEncoder(int width, int height, int fps) throws IOException {
        int bitrate = (int) (width * height * fps * (fps >= 60 ? 0.14f : 0.19f));
        MediaFormat f = baseVideoFormat(width, height, fps, bitrate);
        f.setInteger(MediaFormat.KEY_PROFILE, MediaCodecInfo.CodecProfileLevel.AVCProfileHigh);
        f.setInteger(MediaFormat.KEY_LEVEL, fps >= 60 ? MediaCodecInfo.CodecProfileLevel.AVCLevel42 : MediaCodecInfo.CodecProfileLevel.AVCLevel41);
        f.setInteger(MediaFormat.KEY_COLOR_STANDARD, MediaFormat.COLOR_STANDARD_BT709);
        f.setInteger(MediaFormat.KEY_COLOR_RANGE, MediaFormat.COLOR_RANGE_LIMITED);
        f.setInteger(MediaFormat.KEY_COLOR_TRANSFER, MediaFormat.COLOR_TRANSFER_SDR_VIDEO);
        encoder = MediaCodec.createEncoderByType(VIDEO_MIME);
        try {
            encoder.configure(f, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        } catch (RuntimeException e) {
            Log.i(TAG, "High profile not accepted, using encoder defaults", e);
            encoder.release();
            encoder = MediaCodec.createEncoderByType(VIDEO_MIME);
            encoder.configure(baseVideoFormat(width, height, fps, bitrate), null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        }
        Surface s = encoder.createInputSurface();
        encoder.start();
        return s;
    }

    private static MediaFormat baseVideoFormat(int w, int h, int fps, int bitrate) {
        MediaFormat f = MediaFormat.createVideoFormat(VIDEO_MIME, w, h);
        f.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
        f.setInteger(MediaFormat.KEY_BIT_RATE, bitrate);
        f.setInteger(MediaFormat.KEY_FRAME_RATE, fps);
        f.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
        return f;
    }

    private void drainEncoder(boolean endOfStream) {
        if (endOfStream) encoder.signalEndOfInputStream();
        long deadline = System.currentTimeMillis() + 10_000;
        while (true) {
            int idx = encoder.dequeueOutputBuffer(info, endOfStream ? 10_000 : 0);
            if (idx == MediaCodec.INFO_TRY_AGAIN_LATER) {
                if (!endOfStream || System.currentTimeMillis() > deadline) break;
            } else if (idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                if (muxerStarted) throw new IllegalStateException("format changed twice");
                videoTrack = muxer.addTrack(encoder.getOutputFormat());
                if (audioFormat != null) audioTrack = muxer.addTrack(audioFormat);
                muxer.start();
                muxerStarted = true;
            } else if (idx >= 0) {
                ByteBuffer data = encoder.getOutputBuffer(idx);
                if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) info.size = 0;
                if (info.size > 0 && muxerStarted && data != null) {
                    data.position(info.offset);
                    data.limit(info.offset + info.size);
                    muxer.writeSampleData(videoTrack, data, info);
                    writeAudioUpTo(info.presentationTimeUs);
                }
                encoder.releaseOutputBuffer(idx, false);
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) break;
            }
        }
    }

    private void writeAudioUpTo(long ptsUs) {
        if (audioTrack < 0) return;
        MediaCodec.BufferInfo ai = new MediaCodec.BufferInfo();
        while (audioCursor < audioSamples.size() && audioSamples.get(audioCursor).pts <= ptsUs) {
            AudioSample s = audioSamples.get(audioCursor++);
            ai.set(0, s.data.length, s.pts, s.flags);
            muxer.writeSampleData(audioTrack, ByteBuffer.wrap(s.data), ai);
        }
    }

    private void writeRemainingAudio() {
        writeAudioUpTo(Long.MAX_VALUE);
    }

    /** Encodes the whole soundtrack to AAC up front; samples are interleaved with video later. */
    private void encodeAudio(Pcm pcm) throws IOException {
        MediaFormat f = MediaFormat.createAudioFormat(AUDIO_MIME, Pcm.RATE, 2);
        f.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC);
        f.setInteger(MediaFormat.KEY_BIT_RATE, 192_000);
        f.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 16384);
        MediaCodec codec = MediaCodec.createEncoderByType(AUDIO_MIME);
        codec.configure(f, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        codec.start();
        byte[] bytes = pcm.toPcm16();
        int offset = 0;
        boolean inputDone = false;
        MediaCodec.BufferInfo bi = new MediaCodec.BufferInfo();
        try {
            while (true) {
                if (!inputDone) {
                    int in = codec.dequeueInputBuffer(10_000);
                    if (in >= 0) {
                        ByteBuffer buf = codec.getInputBuffer(in);
                        buf.clear();
                        int chunk = Math.min(Math.min(buf.capacity(), 8192), bytes.length - offset);
                        long pts = (offset / 4) * 1_000_000L / Pcm.RATE;
                        if (chunk <= 0) {
                            codec.queueInputBuffer(in, 0, 0, pts, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            buf.put(bytes, offset, chunk);
                            codec.queueInputBuffer(in, 0, chunk, pts, 0);
                            offset += chunk;
                        }
                    }
                }
                int out = codec.dequeueOutputBuffer(bi, 10_000);
                if (out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    audioFormat = codec.getOutputFormat();
                } else if (out >= 0) {
                    ByteBuffer buf = codec.getOutputBuffer(out);
                    if ((bi.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0 && bi.size > 0 && buf != null) {
                        byte[] data = new byte[bi.size];
                        buf.position(bi.offset);
                        buf.get(data, 0, bi.size);
                        audioSamples.add(new AudioSample(data, bi.presentationTimeUs, bi.flags & ~MediaCodec.BUFFER_FLAG_END_OF_STREAM));
                    }
                    codec.releaseOutputBuffer(out, false);
                    if ((bi.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) break;
                }
            }
        } finally {
            codec.stop();
            codec.release();
        }
    }
}
