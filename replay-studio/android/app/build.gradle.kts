// Replay Studio Android app: a Java shell (foreground service + WebView) around the same Python backend
// that runs on Linux, embedded with Chaquopy, plus FFmpeg/ffprobe cross-compiled for arm64.
plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

val backendDir = rootProject.file("../backend/replay_studio")
val ffmpegDir = rootProject.file("ffmpeg/prebuilt/arm64-v8a")   // filled by ffmpeg/build-ffmpeg.sh

android {
    namespace = "com.replaystudio.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.replaystudio.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            // Signed with the debug key so it can be sideloaded without a Play Store account.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    // FFmpeg and ffprobe are executables packaged as lib*.so so Android installs them into the app's
    // native library directory, the only app location that is allowed to execute files (Android 10+).
    sourceSets { getByName("main") { jniLibs.srcDir(layout.buildDirectory.dir("ffmpeg-jni")) } }
    packaging { jniLibs { useLegacyPackaging = true } }
}

val stageFfmpeg by tasks.registering(Copy::class) {
    from(ffmpegDir) {
        include("ffmpeg", "ffprobe")
        rename("ffmpeg", "libffmpeg.so")
        rename("ffprobe", "libffprobe.so")
    }
    into(layout.buildDirectory.dir("ffmpeg-jni/arm64-v8a"))
    doFirst {
        require(File(ffmpegDir, "ffmpeg").exists()) {
            "Missing $ffmpegDir/ffmpeg - run android/ffmpeg/build-ffmpeg.sh first (see android/README.md)"
        }
    }
}

val stagePython by tasks.registering(Sync::class) {
    from(backendDir) { exclude("**/__pycache__/**", "fake_youtube.py") }
    into(layout.buildDirectory.dir("python-src/replay_studio"))
    doFirst {
        require(File(backendDir, "static/index.html").exists()) {
            "Dashboard not built - run: cd frontend && npm ci && npm run build"
        }
    }
}

tasks.named("preBuild") { dependsOn(stageFfmpeg, stagePython) }

chaquopy {
    defaultConfig {
        version = "3.13"
        // Pure-Python dependencies (pinned to the versions the test suite runs with) + Chaquopy's
        // prebuilt Android wheel for cryptography.
        pip {
            install("starlette==0.46.2")
            install("uvicorn==0.54.0")
            install("h11==0.16.0")
            install("httpx==0.28.1")
            install("httpcore==1.0.9")
            install("anyio==4.16.0")
            install("idna")
            install("certifi")
            install("sniffio")
            install("tzdata")
            install("cryptography==42.0.8")
        }
        extractPackages("replay_studio")   // the dashboard files must exist as real files
    }
    sourceSets {
        getByName("main") { srcDir(layout.buildDirectory.dir("python-src")) }
    }
}
