package com.ugcstudio.app

import com.ugcstudio.app.data.remote.UgcApi
import com.ugcstudio.app.data.repository.AdRepositoryImpl
import com.ugcstudio.app.data.repository.ImageSource
import com.ugcstudio.app.data.settings.ServerConfigHolder
import com.ugcstudio.app.di.ApiJson
import com.ugcstudio.app.di.ServerInterceptor
import com.ugcstudio.app.domain.model.AdFramework
import com.ugcstudio.app.domain.model.AdPlatform
import com.ugcstudio.app.domain.model.CreateAdParams
import com.ugcstudio.app.domain.model.JobStatus
import com.ugcstudio.app.domain.model.ManualProduct
import com.ugcstudio.app.domain.model.ServerSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class RepositoryTest {
    @get:Rule val tmp = TemporaryFolder()
    private val server = MockWebServer()
    private val holder = ServerConfigHolder()
    private lateinit var repo: AdRepositoryImpl

    private fun fixture(name: String) = javaClass.classLoader!!.getResource(name)!!.readText()

    @Before fun setUp() {
        server.start()
        holder.current = ServerSettings(server.url("/api/").toString(), "s3cret")
        val client = OkHttpClient.Builder().addInterceptor(ServerInterceptor(holder)).build()
        val api = Retrofit.Builder()
            .baseUrl("http://${ServerInterceptor.PLACEHOLDER_HOST}/")
            .client(client)
            .addConverterFactory(ApiJson.asConverterFactory("application/json".toMediaType()))
            .build().create(UgcApi::class.java)
        val images = object : ImageSource {
            override fun read(uri: String) = byteArrayOf(1, 2, 3) to "image/jpeg"
        }
        repo = AdRepositoryImpl(api, images, holder, tmp.root, Dispatchers.Unconfined)
    }

    @After fun tearDown() = server.shutdown()

    @Test fun parsesRealServerJob() = runTest {
        server.enqueue(MockResponse().setBody(fixture("job_succeeded.json")))
        val job = repo.getJob("abc")
        assertEquals(JobStatus.SUCCEEDED, job.status)
        assertEquals(AdPlatform.SHORTS, job.platform)
        assertTrue(job.scenes.isNotEmpty())
        assertTrue(job.durationSeconds!! > 5)

        val req = server.takeRequest()
        assertEquals("/api/jobs/abc", req.path)  // base path from Settings is kept
        assertEquals("s3cret", req.getHeader("X-API-Key"))
    }

    @Test fun manualAdUploadsImagesThenCreatesJob() = runTest {
        server.enqueue(MockResponse().setBody("""{"id":"up1"}"""))
        server.enqueue(MockResponse().setBody("""{"id":"up2"}"""))
        server.enqueue(MockResponse().setResponseCode(202).setBody(fixture("job_succeeded.json")))
        repo.createAd(CreateAdParams(
            manual = ManualProduct("GripMount", price = "28", imageUris = listOf("content://a", "content://b")),
            platform = AdPlatform.REELS, framework = AdFramework.AIDA, targetSeconds = 20,
        ))
        assertEquals("/api/uploads", server.takeRequest().path)
        assertEquals("/api/uploads", server.takeRequest().path)
        val create = server.takeRequest()
        val body = ApiJson.parseToJsonElement(create.body.readUtf8()).jsonObject
        assertEquals("reels", body["platform"]!!.jsonPrimitive.content)
        assertEquals("AIDA", body["framework"]!!.jsonPrimitive.content)
        assertEquals(20, body["target_seconds"]!!.jsonPrimitive.content.toInt())
        assertEquals("""["up1","up2"]""", body["brief"]!!.jsonObject["upload_ids"].toString())
    }

    @Test fun downloadsVideoOnceAndCaches() = runTest {
        server.enqueue(MockResponse().setBody(Buffer().write(ByteArray(2048) { 7 })))
        val first = repo.downloadVideo("abcdef123456")
        val second = repo.downloadVideo("abcdef123456")
        assertEquals(2048L, first.length())
        assertEquals(first, second)
        assertEquals(1, server.requestCount)
    }

    @Test fun parsesPluginList() = runTest {
        server.enqueue(MockResponse().setBody(fixture("plugins.json")))
        val plugins = repo.plugins()
        assertTrue(plugins.any { it.capability == "voice" && it.name == "voicestudio" })
        assertTrue(plugins.any { it.capability == "analyze" && it.name == "claude" && !it.available })
    }
}
