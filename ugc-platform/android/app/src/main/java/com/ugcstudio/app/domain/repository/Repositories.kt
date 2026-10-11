package com.ugcstudio.app.domain.repository

import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.model.PluginInfo
import com.ugcstudio.app.domain.model.ServerSettings
import kotlinx.coroutines.flow.Flow
import java.io.File

interface AdRepository {
    suspend fun createAd(params: CreateAdParams): AdJob
    suspend fun getJob(id: String): AdJob
    suspend fun listJobs(): List<AdJob>
    suspend fun retry(id: String): AdJob
    /** Downloads the rendered MP4 (cached on disk) and returns the local file. */
    suspend fun downloadVideo(id: String): File
    fun thumbnailUrl(id: String): String
    suspend fun plugins(): List<PluginInfo>
    suspend fun preferPlugin(capability: String, name: String)
    suspend fun ping(): String
}

interface SettingsRepository {
    val settings: Flow<ServerSettings>
    suspend fun current(): ServerSettings
    suspend fun save(settings: ServerSettings)
}
