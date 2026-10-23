package com.videotranscriber.app

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import kotlinx.coroutines.ensureActive
import java.nio.ByteOrder
import kotlin.coroutines.coroutineContext

/**
 * Decodes the audio track of a video (or audio) file into 16 kHz mono float PCM,
 * which is what whisper expects.
 */
object AudioDecoder {
    const val SAMPLE_RATE = 16_000

    class NoAudioTrackException : Exception("This file has no audio track")

    suspend fun decode(context: Context, uri: Uri, onProgress: (Float) -> Unit): FloatArray {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(context, uri, null)
            val track = (0 until extractor.trackCount).firstOrNull { i ->
                extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
            } ?: throw NoAudioTrackException()
            extractor.selectTrack(track)

            val inputFormat = extractor.getTrackFormat(track)
            val mime = inputFormat.getString(MediaFormat.KEY_MIME)!!
            val durationUs = if (inputFormat.containsKey(MediaFormat.KEY_DURATION)) {
                inputFormat.getLong(MediaFormat.KEY_DURATION)
            } else 0L

            codec = MediaCodec.createDecoderByType(mime)
            codec.configure(inputFormat, null, null, 0)
            codec.start()

            var channels = inputFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var sampleRate = inputFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var floatPcm = false
            var resampler = Resampler(sampleRate, SAMPLE_RATE)
            val out = FloatArrayBuilder(
                if (durationUs > 0) (durationUs / 1_000_000L * SAMPLE_RATE + SAMPLE_RATE).toInt() else SAMPLE_RATE * 60
            )

            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
            while (!outputDone) {
                coroutineContext.ensureActive()

                if (!inputDone) {
                    val inIndex = codec.dequeueInputBuffer(10_000)
                    if (inIndex >= 0) {
                        val buffer = codec.getInputBuffer(inIndex)!!
                        val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(inIndex, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(inIndex, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }

                val outIndex = codec.dequeueOutputBuffer(info, 10_000)
                when {
                    outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val format = codec.outputFormat
                        channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        val newRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        if (newRate != sampleRate) {
                            sampleRate = newRate
                            resampler = Resampler(sampleRate, SAMPLE_RATE)
                        }
                        floatPcm = format.containsKey(MediaFormat.KEY_PCM_ENCODING) &&
                            format.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                    }
                    outIndex >= 0 -> {
                        val buffer = codec.getOutputBuffer(outIndex)!!
                        buffer.position(info.offset)
                        buffer.limit(info.offset + info.size)
                        buffer.order(ByteOrder.nativeOrder())
                        if (floatPcm) {
                            val fb = buffer.asFloatBuffer()
                            while (fb.remaining() >= channels) {
                                var sum = 0f
                                repeat(channels) { sum += fb.get() }
                                resampler.push(sum / channels, out)
                            }
                        } else {
                            val sb = buffer.asShortBuffer()
                            while (sb.remaining() >= channels) {
                                var sum = 0f
                                repeat(channels) { sum += sb.get() }
                                resampler.push(sum / channels / 32768f, out)
                            }
                        }
                        codec.releaseOutputBuffer(outIndex, false)
                        if (durationUs > 0) {
                            onProgress((info.presentationTimeUs.toFloat() / durationUs).coerceIn(0f, 1f))
                        }
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                    }
                }
            }
            resampler.flush(out)
            onProgress(1f)
            return out.toArray()
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            extractor.release()
        }
    }

    /**
     * Streaming resampler. Downsampling averages every input sample that falls into
     * an output sample's window (a box low-pass filter, which keeps aliasing down);
     * upsampling interpolates linearly.
     */
    private class Resampler(inRate: Int, outRate: Int) {
        private val ratio = inRate.toDouble() / outRate
        private val down = ratio >= 1.0
        private var inIndex = 0L

        private var bucket = 0L
        private var acc = 0.0
        private var accCount = 0

        private var prev = 0f
        private var nextOutPos = 0.0

        fun push(sample: Float, out: FloatArrayBuilder) {
            if (down) {
                val b = (inIndex / ratio).toLong()
                if (b != bucket && accCount > 0) {
                    out.add((acc / accCount).toFloat())
                    acc = 0.0
                    accCount = 0
                }
                bucket = b
                acc += sample
                accCount++
            } else {
                while (nextOutPos <= inIndex) {
                    val frac = (nextOutPos - (inIndex - 1)).toFloat()
                    out.add(if (inIndex == 0L) sample else prev + (sample - prev) * frac)
                    nextOutPos += ratio
                }
                prev = sample
            }
            inIndex++
        }

        fun flush(out: FloatArrayBuilder) {
            if (down && accCount > 0) {
                out.add((acc / accCount).toFloat())
                accCount = 0
            }
        }
    }

    private class FloatArrayBuilder(initialCapacity: Int) {
        private var data = FloatArray(initialCapacity.coerceAtLeast(1024))
        private var size = 0

        fun add(value: Float) {
            if (size == data.size) data = data.copyOf(data.size + data.size / 2)
            data[size++] = value
        }

        fun toArray(): FloatArray = if (size == data.size) data else data.copyOf(size)
    }
}
