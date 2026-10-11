package com.ugcstudio.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ugcstudio.app.domain.model.PluginInfo
import com.ugcstudio.app.domain.model.ServerSettings
import com.ugcstudio.app.domain.repository.AdRepository
import com.ugcstudio.app.domain.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsState(
    val baseUrl: String = "",
    val apiKey: String = "",
    val status: String? = null,
    val ok: Boolean = false,
    val plugins: List<PluginInfo> = emptyList(),
    val busy: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settings: SettingsRepository,
    private val repo: AdRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(SettingsState())
    val state: StateFlow<SettingsState> = _state

    init {
        viewModelScope.launch {
            val s = settings.current()
            _state.update { it.copy(baseUrl = s.baseUrl, apiKey = s.apiKey) }
            check()
        }
    }

    fun edit(url: String = _state.value.baseUrl, key: String = _state.value.apiKey) =
        _state.update { it.copy(baseUrl = url, apiKey = key) }

    fun saveAndTest() {
        viewModelScope.launch {
            settings.save(ServerSettings(_state.value.baseUrl, _state.value.apiKey))
            check()
        }
    }

    private suspend fun check() {
        _state.update { it.copy(busy = true) }
        val result = runCatching { repo.ping() to repo.plugins() }
        _state.update { s ->
            result.fold(
                { (health, plugins) -> s.copy(busy = false, ok = true, status = "Connected: $health", plugins = plugins) },
                { e -> s.copy(busy = false, ok = false, status = "Not connected: ${e.message}", plugins = emptyList()) },
            )
        }
    }

    fun prefer(plugin: PluginInfo) {
        viewModelScope.launch {
            runCatching { repo.preferPlugin(plugin.capability, plugin.name) }
            check()
        }
    }
}
