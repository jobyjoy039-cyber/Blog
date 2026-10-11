package com.ugcstudio.app.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

interface UgcApi {
    @GET("health") suspend fun health(): HealthDto
    @GET("plugins") suspend fun plugins(): List<PluginDto>
    @PUT("plugins/{capability}") suspend fun prefer(@Path("capability") capability: String, @Body body: SwapDto)
    @Multipart @POST("uploads") suspend fun upload(@Part file: MultipartBody.Part): CreatedDto
    @POST("jobs") suspend fun createJob(@Body body: JobRequestDto): JobDto
    @GET("jobs") suspend fun jobs(@Query("limit") limit: Int = 50): List<JobDto>
    @GET("jobs/{id}") suspend fun job(@Path("id") id: String): JobDto
    @POST("jobs/{id}/retry") suspend fun retry(@Path("id") id: String): JobDto
    @Streaming @GET("jobs/{id}/video") suspend fun video(@Path("id") id: String): ResponseBody
}

@Serializable data class HealthDto(val status: String, val version: String = "")
@Serializable data class CreatedDto(val id: String)
@Serializable data class SwapDto(val name: String)

@Serializable
data class PluginDto(
    val name: String,
    val capability: String,
    val available: Boolean,
    val reason: String = "",
    val license: String = "",
    @SerialName("commercial_ok") val commercialOk: Boolean = true,
    val preferred: Boolean = false,
    val description: String = "",
)

@Serializable
data class BriefDto(
    val title: String,
    val description: String = "",
    val price: String = "",
    val features: List<String> = emptyList(),
    @SerialName("upload_ids") val uploadIds: List<String> = emptyList(),
)

@Serializable
data class JobRequestDto(
    val url: String? = null,
    val brief: BriefDto? = null,
    val platform: String,
    val framework: String,
    val resolution: String,
    @SerialName("target_seconds") val targetSeconds: Int,
    val language: String,
    val voice: String? = null,
    val music: String = "upbeat",
)

@Serializable data class SceneDto(val kind: String, val voice: String, @SerialName("on_screen") val onScreen: String = "")

@Serializable
data class ScriptDto(
    val framework: String,
    val title: String,
    val scenes: List<SceneDto>,
    val caption: String = "",
    val hashtags: List<String> = emptyList(),
)

@Serializable data class ProductDto(val title: String)
@Serializable data class AnalysisDto(@SerialName("claim_warnings") val claimWarnings: List<String> = emptyList())
@Serializable data class OutputDto(val duration: Double)

@Serializable
data class TraceDto(val step: String, val plugin: String, val cached: Boolean = false, val fallbacks: List<String> = emptyList())

@Serializable
data class JobDto(
    val id: String,
    val status: String,
    val progress: Double = 0.0,
    val step: String = "",
    val request: JobRequestDto,
    val product: ProductDto? = null,
    val analysis: AnalysisDto? = null,
    val script: ScriptDto? = null,
    val output: OutputDto? = null,
    val trace: List<TraceDto> = emptyList(),
    val error: String? = null,
    @SerialName("created_at") val createdAt: Double,
)
