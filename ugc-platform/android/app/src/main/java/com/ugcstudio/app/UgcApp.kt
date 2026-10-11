package com.ugcstudio.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import com.ugcstudio.app.domain.repository.SettingsRepository
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.runBlocking
import javax.inject.Inject

@HiltAndroidApp
class UgcApp : Application(), ImageLoaderFactory {
    @Inject lateinit var imageLoader: ImageLoader
    @Inject lateinit var settings: SettingsRepository

    override fun onCreate() {
        super.onCreate()
        // Load the saved server + key into memory before the first request.
        runBlocking { settings.current() }
    }

    override fun newImageLoader(): ImageLoader = imageLoader
}
