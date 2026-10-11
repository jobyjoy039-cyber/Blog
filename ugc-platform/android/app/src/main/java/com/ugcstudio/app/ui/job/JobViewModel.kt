package com.ugcstudio.app.ui.job

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.JobStatus
import com.ugcstudio.app.domain.repository.AdRepository
import com.ugcstudio.app.domain.usecase.ObserveJobUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

data class JobState(
    val job: AdJob? = null,
    val video: File? = null,
    val downloading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class JobViewModel @Inject constructor(
    savedState: SavedStateHandle,
    private val observeJob: ObserveJobUseCase,
    private val repo: AdRepository,
) : ViewModel() {
    private var jobId: String = checkNotNull(savedState["id"])
    private val _state = MutableStateFlow(JobState())
    val state: StateFlow<JobState> = _state
    private var polling: Job? = null

    init { watch() }

    private fun watch() {
        polling?.cancel()
        polling = viewModelScope.launch {
            observeJob(jobId)
                .catch { e -> _state.update { it.copy(error = "Lost contact with the server: ${e.message}") } }
                .collect { job ->
                    _state.update { it.copy(job = job, error = null) }
                    if (job.status == JobStatus.SUCCEEDED) download()
                }
        }
    }

    fun download() {
        if (_state.value.downloading || _state.value.video != null) return
        _state.update { it.copy(downloading = true) }
        viewModelScope.launch {
            runCatching { repo.downloadVideo(jobId) }
                .onSuccess { f -> _state.update { it.copy(video = f, downloading = false) } }
                .onFailure { e -> _state.update { it.copy(downloading = false, error = "Download failed: ${e.message}") } }
        }
    }

    fun retry() {
        viewModelScope.launch {
            runCatching { repo.retry(jobId) }
                .onSuccess { job ->
                    jobId = job.id
                    _state.value = JobState(job = job)
                    watch()
                }
                .onFailure { e -> _state.update { it.copy(error = e.message) } }
        }
    }

    fun thumbnailUrl() = repo.thumbnailUrl(jobId)
}
