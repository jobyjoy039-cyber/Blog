package com.ugcstudio.app.domain.model

enum class AdPlatform(val wire: String, val label: String, val aspect: String) {
    TIKTOK("tiktok", "TikTok", "9:16"),
    REELS("reels", "Instagram Reels", "9:16"),
    SHORTS("shorts", "YouTube Shorts", "9:16"),
    SNAPCHAT("snapchat", "Snapchat", "9:16"),
    FACEBOOK("facebook", "Facebook Feed", "4:5"),
    PINTEREST("pinterest", "Pinterest", "2:3"),
    YOUTUBE("youtube", "YouTube", "16:9"),
    AMAZON("amazon", "Amazon listing", "16:9"),
    FLIPKART("flipkart", "Flipkart listing", "1:1"),
}

enum class AdFramework(val wire: String, val label: String, val blurb: String) {
    PAS("PAS", "Problem · Agitate · Solve", "Name the pain, twist the knife, show the fix"),
    AIDA("AIDA", "AIDA", "Attention, interest, desire, action"),
    BAB("BAB", "Before · After · Bridge", "Life before, life after, the product in between"),
    PROBLEM_SOLUTION("PROBLEM_SOLUTION", "Problem → Solution", "Short and direct"),
    UNBOXING("UNBOXING", "Unboxing", "First impressions on camera"),
    FOUNDER("FOUNDER", "Founder story", "Why we built it"),
    EDUCATIONAL("EDUCATIONAL", "Educational tip", "Teach one thing, product is the tool"),
    COMPARISON("COMPARISON", "Old way vs new", "Side-by-side contrast"),
}

enum class Resolution(val wire: String) { P720("720p"), P1080("1080p"), K4("4k") }

/** What the user asks for. Exactly one of [url] or [manual] is set. */
data class CreateAdParams(
    val url: String? = null,
    val manual: ManualProduct? = null,
    val platform: AdPlatform = AdPlatform.TIKTOK,
    val framework: AdFramework = AdFramework.PAS,
    val resolution: Resolution = Resolution.P1080,
    val targetSeconds: Int = 30,
    val language: String = "en",
)

data class ManualProduct(
    val title: String,
    val description: String = "",
    val price: String = "",
    val features: List<String> = emptyList(),
    /** Local content:// URIs picked by the user; uploaded before the job starts. */
    val imageUris: List<String> = emptyList(),
)

enum class JobStatus { QUEUED, RUNNING, SUCCEEDED, FAILED }

data class Scene(val kind: String, val voice: String, val onScreen: String)

data class StepTrace(val step: String, val plugin: String, val cached: Boolean, val fallbacks: List<String>)

data class AdJob(
    val id: String,
    val status: JobStatus,
    val progress: Float,
    val step: String,
    val productTitle: String?,
    val platform: AdPlatform,
    val framework: String,
    val scenes: List<Scene>,
    val caption: String,
    val hashtags: List<String>,
    val claimWarnings: List<String>,
    val durationSeconds: Double?,
    val trace: List<StepTrace>,
    val error: String?,
    val createdAt: Long,
) {
    val isFinished get() = status == JobStatus.SUCCEEDED || status == JobStatus.FAILED
}

data class PluginInfo(
    val name: String,
    val capability: String,
    val available: Boolean,
    val reason: String,
    val license: String,
    val commercialOk: Boolean,
    val preferred: Boolean,
    val description: String,
)

data class ServerSettings(val baseUrl: String, val apiKey: String)
