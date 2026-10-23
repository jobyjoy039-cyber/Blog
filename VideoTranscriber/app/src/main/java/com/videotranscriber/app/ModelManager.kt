package com.videotranscriber.app

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

data class WhisperModel(
    val id: String,
    val label: String,
    val sizeMb: Int,
    val description: String,
) {
    val fileName get() = "ggml-$id.bin"
    val url get() = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$fileName"
}

/** Downloads, imports and stores ggml Whisper models in app-private storage. */
class ModelManager(context: Context) {
    private val dir = File(context.filesDir, "models").apply { mkdirs() }
    private val resolver = context.contentResolver

    val models = listOf(
        WhisperModel("tiny-q5_1", "Tiny", 31, "Fastest, lowest accuracy"),
        WhisperModel("base-q5_1", "Base", 57, "Fast, good for clear speech"),
        WhisperModel("small-q5_1", "Small", 181, "Recommended balance"),
        WhisperModel("medium-q5_0", "Medium", 514, "Accurate, slow on phones"),
        WhisperModel("large-v3-turbo-q5_0", "Large v3 Turbo", 547, "Most accurate, needs a fast phone"),
        WhisperModel("base.en", "Base (English only)", 142, "Better for English-only audio"),
    )

    fun fileFor(model: WhisperModel) = File(dir, model.fileName)

    fun isDownloaded(model: WhisperModel) = fileFor(model).let { it.exists() && it.length() > 0 }

    /** Custom models the user imported from a file. */
    fun importedModels(): List<File> {
        val known = models.map { it.fileName }.toSet()
        return dir.listFiles { f -> f.name.endsWith(".bin") && f.name !in known }?.sortedBy { it.name } ?: emptyList()
    }

    fun delete(file: File) {
        file.delete()
    }

    suspend fun download(model: WhisperModel, onProgress: (Float) -> Unit) = withContext(Dispatchers.IO) {
        val target = fileFor(model)
        val part = File(dir, "${model.fileName}.part")
        val connection = URL(model.url).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 15_000
            connection.readTimeout = 30_000
            connection.instanceFollowRedirects = true
            connection.connect()
            if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                throw IOException("Download failed: HTTP ${connection.responseCode}")
            }
            val total = connection.contentLengthLong
            connection.inputStream.use { input ->
                part.outputStream().use { output ->
                    val buffer = ByteArray(256 * 1024)
                    var done = 0L
                    while (true) {
                        ensureActive()
                        val n = input.read(buffer)
                        if (n < 0) break
                        output.write(buffer, 0, n)
                        done += n
                        if (total > 0) onProgress(done.toFloat() / total)
                    }
                }
            }
            if (!part.renameTo(target)) throw IOException("Could not save model")
        } finally {
            connection.disconnect()
            part.delete()
        }
    }

    /** Copies a .bin model picked by the user into app storage. */
    suspend fun import(uri: Uri, displayName: String): File = withContext(Dispatchers.IO) {
        val safeName = displayName.replace(Regex("[^A-Za-z0-9._-]"), "_")
            .let { if (it.endsWith(".bin")) it else "$it.bin" }
        val target = File(dir, safeName)
        val part = File(dir, "$safeName.part")
        try {
            resolver.openInputStream(uri)?.use { input ->
                part.outputStream().use { input.copyTo(it) }
            } ?: throw IOException("Could not open file")
            if (!part.renameTo(target)) throw IOException("Could not save model")
        } finally {
            part.delete()
        }
        target
    }
}
