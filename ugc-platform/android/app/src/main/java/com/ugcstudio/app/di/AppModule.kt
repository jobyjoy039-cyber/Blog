package com.ugcstudio.app.di

import android.content.Context
import coil.ImageLoader
import com.ugcstudio.app.BuildConfig
import com.ugcstudio.app.data.remote.UgcApi
import com.ugcstudio.app.data.repository.AdRepositoryImpl
import com.ugcstudio.app.data.repository.ImageSource
import com.ugcstudio.app.data.settings.DataStoreSettingsRepository
import com.ugcstudio.app.data.settings.ServerConfigHolder
import com.ugcstudio.app.domain.repository.AdRepository
import com.ugcstudio.app.domain.repository.SettingsRepository
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.Dispatchers
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

/**
 * Points every request at the server chosen in Settings and attaches the API
 * key, so changing servers needs no app restart.
 */
class ServerInterceptor(private val holder: ServerConfigHolder) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): okhttp3.Response {
        val cfg = holder.current
        val base = cfg.baseUrl.toHttpUrlOrNull() ?: return chain.proceed(chain.request())
        val original = chain.request().url
        val url = if (original.host == PLACEHOLDER_HOST) {
            original.newBuilder()
                .scheme(base.scheme).host(base.host).port(base.port)
                .encodedPath(base.encodedPath.trimEnd('/') + original.encodedPath)
                .build()
        } else original
        val request = chain.request().newBuilder().url(url).apply {
            if (cfg.apiKey.isNotEmpty() && url.host == base.host) header("X-API-Key", cfg.apiKey)
        }.build()
        return chain.proceed(request)
    }

    companion object {
        const val PLACEHOLDER_HOST = "ugc-server.invalid"
    }
}

val ApiJson = Json { ignoreUnknownKeys = true; explicitNulls = false; coerceInputValues = true }

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides @Singleton
    fun okHttp(holder: ServerConfigHolder): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(ServerInterceptor(holder))
        .apply {
            if (BuildConfig.DEBUG) addInterceptor(HttpLoggingInterceptor().setLevel(HttpLoggingInterceptor.Level.BASIC))
        }
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    @Provides @Singleton
    fun api(client: OkHttpClient): UgcApi = Retrofit.Builder()
        .baseUrl("http://${ServerInterceptor.PLACEHOLDER_HOST}/")
        .client(client)
        .addConverterFactory(ApiJson.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(UgcApi::class.java)

    @Provides @Singleton
    fun imageLoader(@ApplicationContext context: Context, client: OkHttpClient): ImageLoader =
        ImageLoader.Builder(context).okHttpClient(client).crossfade(true).build()

    @Provides @Singleton
    fun imageSource(@ApplicationContext context: Context): ImageSource = object : ImageSource {
        override fun read(uri: String): Pair<ByteArray, String> {
            val u = android.net.Uri.parse(uri)
            val resolver = context.contentResolver
            val mime = resolver.getType(u) ?: "image/jpeg"
            val bytes = resolver.openInputStream(u)?.use { it.readBytes() } ?: error("Cannot read $uri")
            return bytes to mime
        }
    }

    @Provides @Singleton
    fun adRepository(
        api: UgcApi, images: ImageSource, holder: ServerConfigHolder, @ApplicationContext context: Context,
    ): AdRepository = AdRepositoryImpl(api, images, holder, context.cacheDir, Dispatchers.IO)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class BindingsModule {
    @Binds abstract fun settings(impl: DataStoreSettingsRepository): SettingsRepository
}
