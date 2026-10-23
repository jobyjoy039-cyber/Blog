package com.videotranscriber.app

import android.app.Application
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** A model the user can pick: one of the downloadable ones, or an imported file. */
data class ModelItem(
    val key: String,
    val label: String,
    val detail: String,
    val file: File,
    val downloadable: WhisperModel?,
    val available: Boolean,
)

sealed interface Phase {
    data object Idle : Phase
    data class ExtractingAudio(val progress: Float) : Phase
    data object LoadingModel : Phase
    data class Transcribing(val progress: Float) : Phase
    data class Done(val seconds: Long) : Phase
    data class Failed(val message: String) : Phase
}

data class UiState(
    val models: List<ModelItem> = emptyList(),
    val selectedKey: String? = null,
    val downloadingKey: String? = null,
    val downloadProgress: Float = 0f,
    val videoUri: Uri? = null,
    val videoName: String? = null,
    val language: String = "auto",
    val translate: Boolean = false,
    val phase: Phase = Phase.Idle,
    val segments: List<Segment> = emptyList(),
    val detectedLanguage: String? = null,
    val showTimestamps: Boolean = true,
    val message: String? = null,
) {
    val selectedModel get() = models.firstOrNull { it.key == selectedKey }
    val busy get() = phase is Phase.ExtractingAudio || phase is Phase.LoadingModel || phase is Phase.Transcribing
    val canTranscribe get() = !busy && videoUri != null && selectedModel?.available == true
}

class TranscribeViewModel(app: Application) : AndroidViewModel(app) {
    private val modelManager = ModelManager(app)
    private val prefs = app.getSharedPreferences("settings", Context.MODE_PRIVATE)

    private val _state = MutableStateFlow(
        UiState(
            selectedKey = prefs.getString("model", "small-q5_1"),
            language = prefs.getString("language", "auto") ?: "auto",
            translate = prefs.getBoolean("translate", false),
        )
    )
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var downloadJob: Job? = null
    private var transcribeJob: Job? = null

    // The loaded whisper context is kept between runs; loading a model takes a while.
    private var whisperCtx = 0L
    private var whisperCtxPath: String? = null

    init {
        refreshModels()
    }

    private fun refreshModels() {
        val builtin = modelManager.models.map { m ->
            ModelItem(
                key = m.id,
                label = m.label,
                detail = "${m.sizeMb} MB · ${m.description}",
                file = modelManager.fileFor(m),
                downloadable = m,
                available = modelManager.isDownloaded(m),
            )
        }
        val imported = modelManager.importedModels().map { f ->
            ModelItem(
                key = "file:${f.name}",
                label = f.nameWithoutExtension,
                detail = "${f.length() / 1_000_000} MB · Imported",
                file = f,
                downloadable = null,
                available = true,
            )
        }
        _state.update { s ->
            val all = builtin + imported
            s.copy(models = all, selectedKey = s.selectedKey?.takeIf { k -> all.any { it.key == k } } ?: "small-q5_1")
        }
    }

    fun selectModel(key: String) {
        prefs.edit().putString("model", key).apply()
        _state.update { it.copy(selectedKey = key) }
    }

    fun setLanguage(code: String) {
        prefs.edit().putString("language", code).apply()
        _state.update { it.copy(language = code) }
    }

    fun setTranslate(enabled: Boolean) {
        prefs.edit().putBoolean("translate", enabled).apply()
        _state.update { it.copy(translate = enabled) }
    }

    fun setShowTimestamps(enabled: Boolean) = _state.update { it.copy(showTimestamps = enabled) }

    fun consumeMessage() = _state.update { it.copy(message = null) }

    fun downloadSelected() {
        val model = _state.value.selectedModel?.downloadable ?: return
        if (downloadJob?.isActive == true) return
        _state.update { it.copy(downloadingKey = model.id, downloadProgress = 0f) }
        downloadJob = viewModelScope.launch {
            try {
                modelManager.download(model) { p -> _state.update { it.copy(downloadProgress = p) } }
                _state.update { it.copy(message = "${model.label} model ready") }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(message = "Download failed: ${e.message}") }
            } finally {
                _state.update { it.copy(downloadingKey = null) }
                refreshModels()
            }
        }
    }

    fun cancelDownload() {
        downloadJob?.cancel()
    }

    fun deleteSelectedModel() {
        val item = _state.value.selectedModel ?: return
        if (_state.value.busy) return
        if (whisperCtxPath == item.file.absolutePath) releaseContext()
        modelManager.delete(item.file)
        refreshModels()
    }

    fun importModel(uri: Uri) {
        viewModelScope.launch {
            try {
                val file = modelManager.import(uri, displayName(uri) ?: "custom-model.bin")
                refreshModels()
                selectModel("file:${file.name}")
                _state.update { it.copy(message = "Imported ${file.name}") }
            } catch (e: Exception) {
                _state.update { it.copy(message = "Import failed: ${e.message}") }
            }
        }
    }

    fun setVideo(uri: Uri) {
        _state.update {
            it.copy(
                videoUri = uri,
                videoName = displayName(uri) ?: uri.lastPathSegment,
                segments = emptyList(),
                detectedLanguage = null,
                phase = Phase.Idle,
            )
        }
    }

    fun transcribe() {
        val s = _state.value
        if (!s.canTranscribe) return
        val uri = s.videoUri!!
        val modelFile = s.selectedModel!!.file
        val startedAt = System.currentTimeMillis()

        _state.update { it.copy(segments = emptyList(), detectedLanguage = null, phase = Phase.ExtractingAudio(0f)) }

        transcribeJob = viewModelScope.launch(Dispatchers.Default) {
            try {
                val samples = AudioDecoder.decode(getApplication(), uri) { p ->
                    _state.update { it.copy(phase = Phase.ExtractingAudio(p)) }
                }
                if (samples.isEmpty()) throw IllegalStateException("No audio found in this file")

                _state.update { it.copy(phase = Phase.LoadingModel) }
                val ctx = loadContext(modelFile)

                _state.update { it.copy(phase = Phase.Transcribing(0f)) }
                val rc = WhisperLib.transcribe(
                    ctx, samples, s.language, s.translate, WhisperLib.preferredThreadCount(),
                    object : WhisperLib.Listener {
                        override fun onProgress(percent: Int) {
                            _state.update { it.copy(phase = Phase.Transcribing(percent / 100f)) }
                        }

                        override fun onSegment(startMs: Long, endMs: Long, utf8: ByteArray) {
                            val text = String(utf8, Charsets.UTF_8).trim()
                            if (text.isNotEmpty()) {
                                _state.update { it.copy(segments = it.segments + Segment(startMs, endMs, text)) }
                            }
                        }
                    },
                )
                when {
                    rc == 1 -> _state.update { it.copy(phase = Phase.Idle, message = "Transcription cancelled") }
                    rc != 0 -> throw IllegalStateException("Transcription failed (code $rc)")
                    else -> {
                        val lang = if (s.language == "auto") WhisperLib.detectedLanguage(ctx) else s.language
                        val seconds = (System.currentTimeMillis() - startedAt) / 1000
                        _state.update { it.copy(phase = Phase.Done(seconds), detectedLanguage = lang) }
                    }
                }
            } catch (e: CancellationException) {
                _state.update { it.copy(phase = Phase.Idle, message = "Transcription cancelled") }
            } catch (e: AudioDecoder.NoAudioTrackException) {
                _state.update { it.copy(phase = Phase.Failed("This video has no audio track")) }
            } catch (e: OutOfMemoryError) {
                _state.update { it.copy(phase = Phase.Failed("Not enough memory. Try a shorter video or a smaller model.")) }
            } catch (e: Exception) {
                _state.update { it.copy(phase = Phase.Failed(e.message ?: e.toString())) }
            }
        }
    }

    fun cancelTranscription() {
        WhisperLib.requestAbort()
        transcribeJob?.cancel()
    }

    private suspend fun loadContext(file: File): Long = withContext(Dispatchers.IO) {
        if (whisperCtx != 0L && whisperCtxPath == file.absolutePath) return@withContext whisperCtx
        releaseContext()
        val ctx = WhisperLib.initContext(file.absolutePath)
        if (ctx == 0L) throw IllegalStateException("Could not load model ${file.name}. Is it a valid ggml model?")
        whisperCtx = ctx
        whisperCtxPath = file.absolutePath
        ctx
    }

    private fun releaseContext() {
        if (whisperCtx != 0L) WhisperLib.freeContext(whisperCtx)
        whisperCtx = 0L
        whisperCtxPath = null
    }

    fun exportText(format: ExportFormat): String = TranscriptFormatter.format(_state.value.segments, format)

    fun shareText(): String = TranscriptFormatter.plainText(_state.value.segments, _state.value.showTimestamps)

    fun suggestedFileName(format: ExportFormat): String {
        val base = _state.value.videoName?.substringBeforeLast('.') ?: "transcript"
        return "$base.${format.extension}"
    }

    fun writeExport(uri: Uri, format: ExportFormat) {
        val text = exportText(format)
        viewModelScope.launch(Dispatchers.IO) {
            val ok = runCatching {
                getApplication<Application>().contentResolver.openOutputStream(uri)?.use {
                    it.write(text.toByteArray(Charsets.UTF_8))
                } ?: error("Could not open file")
            }.isSuccess
            _state.update { it.copy(message = if (ok) "Saved ${format.name}" else "Could not save file") }
        }
    }

    private fun displayName(uri: Uri): String? = runCatching {
        getApplication<Application>().contentResolver
            .query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }.getOrNull()

    override fun onCleared() {
        WhisperLib.requestAbort()
        // Only free the model once a running transcription has stopped using it.
        val job = transcribeJob
        if (job?.isActive == true) job.invokeOnCompletion { releaseContext() } else releaseContext()
    }
}
