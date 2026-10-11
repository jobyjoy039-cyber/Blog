package com.ugcstudio.app.data.remote

import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.AdPlatform
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.model.JobStatus
import com.ugcstudio.app.domain.model.PluginInfo
import com.ugcstudio.app.domain.model.Scene
import com.ugcstudio.app.domain.model.StepTrace

fun CreateAdParams.toDto(uploadIds: List<String>) = JobRequestDto(
    url = url,
    brief = manual?.let { BriefDto(it.title, it.description, it.price, it.features, uploadIds) },
    platform = platform.wire,
    framework = framework.wire,
    resolution = resolution.wire,
    targetSeconds = targetSeconds,
    language = language,
    voice = voice,
)

fun JobDto.toDomain() = AdJob(
    id = id,
    status = runCatching { JobStatus.valueOf(status.uppercase()) }.getOrDefault(JobStatus.QUEUED),
    progress = progress.toFloat().coerceIn(0f, 1f),
    step = step,
    productTitle = product?.title,
    platform = AdPlatform.entries.firstOrNull { it.wire == request.platform } ?: AdPlatform.TIKTOK,
    framework = script?.framework ?: request.framework,
    scenes = script?.scenes.orEmpty().map { Scene(it.kind, it.voice, it.onScreen) },
    caption = script?.caption.orEmpty(),
    hashtags = script?.hashtags.orEmpty(),
    claimWarnings = analysis?.claimWarnings.orEmpty(),
    durationSeconds = output?.duration,
    trace = trace.map { StepTrace(it.step, it.plugin, it.cached, it.fallbacks) },
    error = error,
    createdAt = (createdAt * 1000).toLong(),
)

fun PluginDto.toDomain() = PluginInfo(name, capability, available, reason, license, commercialOk, preferred, description)
