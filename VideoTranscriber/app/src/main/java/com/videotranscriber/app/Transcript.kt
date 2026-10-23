package com.videotranscriber.app

import java.util.Locale

data class Segment(val startMs: Long, val endMs: Long, val text: String)

enum class ExportFormat(val extension: String, val mimeType: String) {
    TXT("txt", "text/plain"),
    SRT("srt", "application/x-subrip"),
    VTT("vtt", "text/vtt"),
}

object TranscriptFormatter {
    fun plainText(segments: List<Segment>, withTimestamps: Boolean = false): String =
        segments.joinToString("\n") { s ->
            if (withTimestamps) "[${clock(s.startMs)}] ${s.text}" else s.text
        }

    fun format(segments: List<Segment>, format: ExportFormat): String = when (format) {
        ExportFormat.TXT -> plainText(segments) + "\n"
        ExportFormat.SRT -> buildString {
            segments.forEachIndexed { i, s ->
                append(i + 1).append('\n')
                append(timestamp(s.startMs, ',')).append(" --> ").append(timestamp(s.endMs, ',')).append('\n')
                append(s.text).append("\n\n")
            }
        }
        ExportFormat.VTT -> buildString {
            append("WEBVTT\n\n")
            segments.forEach { s ->
                append(timestamp(s.startMs, '.')).append(" --> ").append(timestamp(s.endMs, '.')).append('\n')
                append(s.text).append("\n\n")
            }
        }
    }

    /** HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT). */
    private fun timestamp(ms: Long, separator: Char): String {
        val h = ms / 3_600_000
        val m = ms / 60_000 % 60
        val s = ms / 1000 % 60
        val milli = ms % 1000
        return "%02d:%02d:%02d%c%03d".format(Locale.ROOT, h, m, s, separator, milli)
    }

    /** Short clock for on-screen display, e.g. 1:05 or 1:02:05. */
    fun clock(ms: Long): String {
        val h = ms / 3_600_000
        val m = ms / 60_000 % 60
        val s = ms / 1000 % 60
        return if (h > 0) "%d:%02d:%02d".format(Locale.ROOT, h, m, s) else "%d:%02d".format(Locale.ROOT, m, s)
    }
}

/** Languages offered in the picker; whisper supports ~100, these are the common ones. */
val LANGUAGES = listOf(
    "auto" to "Auto-detect",
    "en" to "English",
    "hi" to "Hindi",
    "ml" to "Malayalam",
    "ta" to "Tamil",
    "te" to "Telugu",
    "kn" to "Kannada",
    "bn" to "Bengali",
    "mr" to "Marathi",
    "ur" to "Urdu",
    "ar" to "Arabic",
    "es" to "Spanish",
    "fr" to "French",
    "de" to "German",
    "it" to "Italian",
    "pt" to "Portuguese",
    "ru" to "Russian",
    "tr" to "Turkish",
    "zh" to "Chinese",
    "ja" to "Japanese",
    "ko" to "Korean",
    "id" to "Indonesian",
)
