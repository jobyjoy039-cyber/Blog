package com.example.moviestream.data

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** "My List" and resume positions, persisted on device and shared by every screen in the process. */
class UserLibrary private constructor(context: Context) {

    private val prefs = context.getSharedPreferences("user_library", Context.MODE_PRIVATE)

    private val _myList = MutableStateFlow(prefs.getStringSet(KEY_MY_LIST, emptySet())!!.toSet())
    val myList: StateFlow<Set<String>> = _myList.asStateFlow()

    private val _progress = MutableStateFlow(readProgress())
    val progress: StateFlow<Map<String, WatchProgress>> = _progress.asStateFlow()

    fun toggleMyList(movieId: String) {
        _myList.update { if (movieId in it) it - movieId else it + movieId }
        prefs.edit().putStringSet(KEY_MY_LIST, _myList.value).apply()
    }

    fun saveProgress(movieId: String, positionMs: Long, durationMs: Long) {
        val progress = WatchProgress(positionMs, durationMs)
        _progress.update { it + (movieId to progress) }
        prefs.edit().putString(PROGRESS_PREFIX + movieId, "$positionMs,$durationMs").apply()
    }

    fun clearProgress(movieId: String) {
        _progress.update { it - movieId }
        prefs.edit().remove(PROGRESS_PREFIX + movieId).apply()
    }

    private fun readProgress(): Map<String, WatchProgress> =
        prefs.all.mapNotNull { (key, value) ->
            if (!key.startsWith(PROGRESS_PREFIX) || value !is String) return@mapNotNull null
            val parts = value.split(',')
            val position = parts.getOrNull(0)?.toLongOrNull() ?: return@mapNotNull null
            val duration = parts.getOrNull(1)?.toLongOrNull() ?: return@mapNotNull null
            key.removePrefix(PROGRESS_PREFIX) to WatchProgress(position, duration)
        }.toMap()

    companion object {
        private const val KEY_MY_LIST = "my_list"
        private const val PROGRESS_PREFIX = "progress_"

        @Volatile
        private var instance: UserLibrary? = null

        fun get(context: Context): UserLibrary =
            instance ?: synchronized(this) {
                instance ?: UserLibrary(context.applicationContext).also { instance = it }
            }
    }
}
