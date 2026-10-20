package com.example.moviestream.data

data class Movie(
    val id: String,
    val title: String,
    val year: Int,
    val durationMinutes: Int,
    val rating: String,
    val genres: List<String>,
    val featured: Boolean,
    val description: String,
    val posterUrl: String?,
    val streamUrl: String,
    val credit: String,
)

data class WatchProgress(val positionMs: Long, val durationMs: Long) {
    val fraction: Float
        get() = if (durationMs > 0) (positionMs.toFloat() / durationMs).coerceIn(0f, 1f) else 0f

    /** Worth offering "resume": started, but not effectively finished. */
    val isResumable: Boolean
        get() = positionMs > 5_000 && fraction < 0.95f
}
