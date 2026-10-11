package com.ugcstudio.app.data.repository

import com.ugcstudio.app.data.remote.SwapDto
import com.ugcstudio.app.data.remote.UgcApi
import com.ugcstudio.app.data.remote.toDomain
import com.ugcstudio.app.data.remote.toDto
import com.ugcstudio.app.data.settings.ServerConfigHolder
import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.model.PluginInfo
import com.ugcstudio.app.domain.repository.AdRepository
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

/** Reads picked images (content:// URIs); abstracted so the repository is testable on the JVM. */
interface ImageSource {
    fun read(uri: String): Pair<ByteArray, String>
}

class AdRepositoryImpl(
    private val api: UgcApi,
    private val images: ImageSource,
    private val config: ServerConfigHolder,
    private val cacheDir: File,
    private val io: CoroutineDispatcher,
) : AdRepository {

    override suspend fun createAd(params: CreateAdParams): AdJob = withContext(io) {
        val uploadIds = params.manual?.imageUris.orEmpty().map { uri ->
            val (bytes, mime) = images.read(uri)
            val part = MultipartBody.Part.createFormData(
                "file", "image", bytes.toRequestBody(mime.toMediaTypeOrNull())
            )
            api.upload(part).id
        }
        api.createJob(params.toDto(uploadIds)).toDomain()
    }

    override suspend fun getJob(id: String) = withContext(io) { api.job(id).toDomain() }

    override suspend fun listJobs() = withContext(io) { api.jobs().map { it.toDomain() } }

    override suspend fun retry(id: String) = withContext(io) { api.retry(id).toDomain() }

    override suspend fun downloadVideo(id: String): File = withContext(io) {
        val dir = File(cacheDir, "videos").apply { mkdirs() }
        val file = File(dir, "ugc-ad-${id.take(8)}.mp4")
        if (file.length() > 0) return@withContext file
        val tmp = File(dir, "$id.part")
        api.video(id).byteStream().use { input -> tmp.outputStream().use { input.copyTo(it) } }
        check(tmp.renameTo(file)) { "Could not save video" }
        file
    }

    override fun thumbnailUrl(id: String) = "${config.current.baseUrl}jobs/$id/thumbnail"

    override suspend fun plugins(): List<PluginInfo> = withContext(io) { api.plugins().map { it.toDomain() } }

    override suspend fun preferPlugin(capability: String, name: String) = withContext(io) {
        api.prefer(capability, SwapDto(name))
    }

    override suspend fun ping(): String = withContext(io) { api.health().let { "${it.status} · v${it.version}" } }
}
