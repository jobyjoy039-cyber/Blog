package com.ugcstudio.app

import app.cash.turbine.test
import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.AdPlatform
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.model.JobStatus
import com.ugcstudio.app.domain.model.ManualProduct
import com.ugcstudio.app.domain.model.PluginInfo
import com.ugcstudio.app.domain.repository.AdRepository
import com.ugcstudio.app.domain.usecase.CreateAdUseCase
import com.ugcstudio.app.domain.usecase.InvalidAdRequest
import com.ugcstudio.app.domain.usecase.ObserveJobUseCase
import com.ugcstudio.app.domain.usecase.SharedTextParser
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test
import java.io.File
import java.io.IOException

fun fakeJob(id: String = "j1", status: JobStatus = JobStatus.RUNNING, progress: Float = 0.5f) = AdJob(
    id = id, status = status, progress = progress, step = "voice", productTitle = "GripMount",
    platform = AdPlatform.TIKTOK, framework = "PAS", scenes = emptyList(), caption = "", hashtags = emptyList(),
    claimWarnings = emptyList(), durationSeconds = null, trace = emptyList(), error = null, createdAt = 0L,
)

open class FakeRepo : AdRepository {
    val created = mutableListOf<CreateAdParams>()
    var responses = ArrayDeque<Result<AdJob>>()

    override suspend fun createAd(params: CreateAdParams) = fakeJob().also { created += params }
    override suspend fun getJob(id: String): AdJob = responses.removeFirst().getOrThrow()
    override suspend fun listJobs() = listOf(fakeJob())
    override suspend fun retry(id: String) = fakeJob("j2")
    override suspend fun downloadVideo(id: String) = File("x.mp4")
    override fun thumbnailUrl(id: String) = "http://x/$id"
    override suspend fun plugins() = emptyList<PluginInfo>()
    override suspend fun preferPlugin(capability: String, name: String) {}
    override suspend fun ping() = "ok"
}

class CreateAdUseCaseTest {
    private val repo = FakeRepo()
    private val createAd = CreateAdUseCase(repo)

    @Test fun rejectsMissingSource() = runTest {
        assertThrows(InvalidAdRequest::class.java) { kotlinx.coroutines.runBlocking { createAd(CreateAdParams()) } }
    }

    @Test fun rejectsNonHttpLinks() = runTest {
        for (bad in listOf("ftp://x.com/p", "not a url", "https://")) {
            assertThrows(InvalidAdRequest::class.java) { kotlinx.coroutines.runBlocking { createAd(CreateAdParams(url = bad)) } }
        }
    }

    @Test fun rejectsBlankManualTitle() = runTest {
        assertThrows(InvalidAdRequest::class.java) {
            kotlinx.coroutines.runBlocking { createAd(CreateAdParams(manual = ManualProduct(title = " "))) }
        }
    }

    @Test fun trimsAndSubmitsValidLink() = runTest {
        createAd(CreateAdParams(url = "  https://shop.example/products/mount  "))
        assertEquals("https://shop.example/products/mount", repo.created.single().url)
    }
}

class ObserveJobUseCaseTest {
    @Test fun emitsUntilFinishedAndSurvivesBlips() = runTest {
        val repo = FakeRepo().apply {
            responses = ArrayDeque(listOf(
                Result.success(fakeJob(progress = 0.2f)),
                Result.failure(IOException("wifi blip")),
                Result.success(fakeJob(progress = 0.7f)),
                Result.success(fakeJob(status = JobStatus.SUCCEEDED, progress = 1f)),
            ))
        }
        ObserveJobUseCase(repo)("j1").test {
            assertEquals(0.2f, awaitItem().progress)
            assertEquals(0.7f, awaitItem().progress)
            assertEquals(JobStatus.SUCCEEDED, awaitItem().status)
            awaitComplete()
        }
    }

    @Test fun givesUpAfterRepeatedErrors() = runTest {
        val repo = FakeRepo().apply { responses = ArrayDeque(List(3) { Result.failure(IOException("down")) }) }
        ObserveJobUseCase(repo)("j1", maxErrors = 3).test {
            assertEquals("down", awaitError().message)
        }
    }
}

class SharedTextParserTest {
    @Test fun extractsFirstLink() {
        assertEquals(
            "https://www.flipkart.com/item/p/itm123?pid=X",
            SharedTextParser.firstUrl("Check this out! https://www.flipkart.com/item/p/itm123?pid=X."),
        )
        assertNull(SharedTextParser.firstUrl("no link here"))
    }
}
