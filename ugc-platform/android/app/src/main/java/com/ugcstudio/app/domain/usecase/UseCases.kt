package com.ugcstudio.app.domain.usecase

import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.repository.AdRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.net.URI
import javax.inject.Inject

class InvalidAdRequest(message: String) : IllegalArgumentException(message)

/** Validates input before it reaches the network, then submits the job. */
class CreateAdUseCase @Inject constructor(private val repo: AdRepository) {
    suspend operator fun invoke(params: CreateAdParams): AdJob {
        val url = params.url?.trim()?.takeIf { it.isNotEmpty() }
        val manual = params.manual
        if (url == null && manual == null) throw InvalidAdRequest("Paste a product link or fill in the product details")
        if (url != null) {
            val uri = runCatching { URI(url) }.getOrNull()
            if (uri == null || uri.scheme !in setOf("http", "https") || uri.host.isNullOrBlank()) {
                throw InvalidAdRequest("That doesn't look like a product link")
            }
        }
        if (manual != null && manual.title.isBlank()) throw InvalidAdRequest("Product name is required")
        if (params.targetSeconds !in 8..90) throw InvalidAdRequest("Length must be 8-90 seconds")
        return repo.createAd(params.copy(url = url))
    }
}

/**
 * Polls a job until it finishes. Backs off from 1s to 4s while running and
 * keeps going through brief network errors (the server keeps working).
 */
class ObserveJobUseCase @Inject constructor(private val repo: AdRepository) {
    operator fun invoke(id: String, maxErrors: Int = 5): Flow<AdJob> = flow {
        var interval = 1_000L
        var errors = 0
        while (true) {
            val job = try {
                repo.getJob(id).also { errors = 0 }
            } catch (e: Exception) {
                if (++errors >= maxErrors) throw e
                null
            }
            if (job != null) {
                emit(job)
                if (job.isFinished) return@flow
            }
            delay(interval)
            interval = (interval * 3 / 2).coerceAtMost(4_000L)
        }
    }
}

/** Extracts the first http(s) link from text shared by another app. */
object SharedTextParser {
    private val urlRegex = Regex("""https?://[^\s<>"']+""")
    fun firstUrl(text: String?): String? = text?.let { urlRegex.find(it)?.value?.trimEnd('.', ',', ')') }
}
