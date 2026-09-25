plugins {
    id("com.android.application")
}

android {
    namespace = "com.latentspaces.brag"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.latentspaces.brag"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Signed with the debug key so the APK installs without a keystore.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // The site's .mp4/.jpg files are already compressed.
    androidResources {
        noCompress += listOf("mp4", "jpg", "png")
    }
}

dependencies {
    implementation("androidx.webkit:webkit:1.12.1")
}
