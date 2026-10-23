package com.videotranscriber.app

import java.io.File

/** Thin wrapper over the native whisper.cpp bindings in whisper_jni.cpp. */
object WhisperLib {
    init {
        System.loadLibrary("whisper_jni")
    }

    interface Listener {
        /** Called with 0..100 as whisper works through the audio. */
        fun onProgress(percent: Int)

        /** Called for every new segment; [utf8] is the segment text as UTF-8. */
        fun onSegment(startMs: Long, endMs: Long, utf8: ByteArray)
    }

    external fun initContext(modelPath: String): Long
    external fun freeContext(ctx: Long)
    external fun systemInfo(): String
    external fun requestAbort()
    external fun transcribe(
        ctx: Long,
        samples: FloatArray,
        language: String,
        translate: Boolean,
        threads: Int,
        listener: Listener,
    ): Int
    external fun detectedLanguage(ctx: Long): String

    /**
     * Thread count for big.LITTLE CPUs: only the faster cores help, the slow ones
     * hold everything back. Counts cores whose max frequency is above the slowest.
     */
    fun preferredThreadCount(): Int {
        val cores = Runtime.getRuntime().availableProcessors()
        val freqs = (0 until cores).mapNotNull { i ->
            File("/sys/devices/system/cpu/cpu$i/cpufreq/cpuinfo_max_freq")
                .takeIf { it.canRead() }
                ?.readText()?.trim()?.toLongOrNull()
        }
        if (freqs.size != cores || freqs.isEmpty()) return (cores - 2).coerceIn(2, 8)
        val minFreq = freqs.min()
        val fast = freqs.count { it > minFreq }
        return (if (fast == 0) cores else fast).coerceIn(2, 8)
    }
}
