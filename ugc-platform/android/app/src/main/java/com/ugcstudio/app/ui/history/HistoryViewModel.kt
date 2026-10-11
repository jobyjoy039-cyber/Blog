package com.ugcstudio.app.ui.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.repository.AdRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HistoryState(val jobs: List<AdJob> = emptyList(), val loading: Boolean = false, val error: String? = null)

@HiltViewModel
class HistoryViewModel @Inject constructor(private val repo: AdRepository) : ViewModel() {
    private val _state = MutableStateFlow(HistoryState())
    val state: StateFlow<HistoryState> = _state

    init { refresh() }

    fun refresh() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            runCatching { repo.listJobs() }
                .onSuccess { jobs -> _state.value = HistoryState(jobs = jobs) }
                .onFailure { e -> _state.update { it.copy(loading = false, error = e.message ?: "Server unreachable") } }
        }
    }

    fun thumbnailUrl(id: String) = repo.thumbnailUrl(id)
}
