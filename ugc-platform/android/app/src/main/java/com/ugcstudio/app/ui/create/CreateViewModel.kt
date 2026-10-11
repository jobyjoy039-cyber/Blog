package com.ugcstudio.app.ui.create

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ugcstudio.app.domain.model.AdFramework
import com.ugcstudio.app.domain.model.AdPlatform
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.model.ManualProduct
import com.ugcstudio.app.domain.model.Resolution
import com.ugcstudio.app.domain.usecase.CreateAdUseCase
import com.ugcstudio.app.domain.usecase.InvalidAdRequest
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class SourceMode { LINK, MANUAL }

data class CreateState(
    val mode: SourceMode = SourceMode.LINK,
    val url: String = "",
    val title: String = "",
    val description: String = "",
    val price: String = "",
    val features: String = "",
    val images: List<String> = emptyList(),
    val platform: AdPlatform = AdPlatform.TIKTOK,
    val framework: AdFramework = AdFramework.PAS,
    val resolution: Resolution = Resolution.P1080,
    val seconds: Int = 30,
    val voice: String = "Jasper",
    val submitting: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class CreateViewModel @Inject constructor(private val createAd: CreateAdUseCase) : ViewModel() {
    private val _state = MutableStateFlow(CreateState())
    val state: StateFlow<CreateState> = _state

    private val _created = Channel<String>(Channel.BUFFERED)
    /** One-shot navigation events carrying the new job id. */
    val created = _created.receiveAsFlow()

    fun update(transform: CreateState.() -> CreateState) = _state.update { it.transform().copy(error = null) }

    fun onSharedUrl(url: String) = update { copy(mode = SourceMode.LINK, url = url) }

    fun addImages(uris: List<String>) = update { copy(images = (images + uris).distinct().take(6)) }

    fun removeImage(uri: String) = update { copy(images = images - uri) }

    fun submit() {
        val s = _state.value
        if (s.submitting) return
        val params = CreateAdParams(
            url = s.url.takeIf { s.mode == SourceMode.LINK },
            manual = if (s.mode == SourceMode.MANUAL) ManualProduct(
                title = s.title.trim(),
                description = s.description.trim(),
                price = s.price.trim(),
                features = s.features.lines().map { it.trim() }.filter { it.isNotEmpty() },
                imageUris = s.images,
            ) else null,
            platform = s.platform,
            framework = s.framework,
            resolution = s.resolution,
            targetSeconds = s.seconds,
            voice = s.voice,
        )
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            try {
                val job = createAd(params)
                _state.update { it.copy(submitting = false) }
                _created.send(job.id)
            } catch (e: InvalidAdRequest) {
                _state.update { it.copy(submitting = false, error = e.message) }
            } catch (e: Exception) {
                _state.update { it.copy(submitting = false, error = "Couldn't reach the studio server: ${e.message ?: e::class.simpleName}") }
            }
        }
    }
}
