package com.ugcstudio.app.data.settings

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.ugcstudio.app.BuildConfig
import com.ugcstudio.app.domain.model.ServerSettings
import com.ugcstudio.app.domain.repository.SettingsRepository
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("server_settings")

/** AES-GCM with a non-exportable key held in the Android Keystore. */
class SecretCipher {
    private val alias = "ugc_api_key"

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return gen.generateKey()
    }

    fun encrypt(plain: String): String {
        if (plain.isEmpty()) return ""
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        return Base64.encodeToString(c.iv + c.doFinal(plain.toByteArray()), Base64.NO_WRAP)
    }

    fun decrypt(stored: String): String {
        if (stored.isEmpty()) return ""
        return runCatching {
            val bytes = Base64.decode(stored, Base64.NO_WRAP)
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes, 0, 12))
            String(c.doFinal(bytes, 12, bytes.size - 12))
        }.getOrDefault("") // key lost (e.g. restored backup): ask the user again
    }
}

/** Latest settings, readable synchronously by the OkHttp interceptor. */
@Singleton
class ServerConfigHolder @Inject constructor() {
    @Volatile var current: ServerSettings = ServerSettings(BuildConfig.DEFAULT_SERVER_URL, "")
}

@Singleton
class DataStoreSettingsRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val holder: ServerConfigHolder,
) : SettingsRepository {
    private val urlKey = stringPreferencesKey("base_url")
    private val apiKeyKey = stringPreferencesKey("api_key_enc")
    private val cipher = SecretCipher()

    override val settings: Flow<ServerSettings> = context.dataStore.data.map { prefs ->
        ServerSettings(
            baseUrl = prefs[urlKey] ?: BuildConfig.DEFAULT_SERVER_URL,
            apiKey = cipher.decrypt(prefs[apiKeyKey].orEmpty()),
        ).also { holder.current = it }
    }

    override suspend fun current(): ServerSettings = settings.first()

    override suspend fun save(settings: ServerSettings) {
        val url = settings.baseUrl.trim().let { if (it.endsWith("/")) it else "$it/" }
        context.dataStore.edit {
            it[urlKey] = url
            it[apiKeyKey] = cipher.encrypt(settings.apiKey.trim())
        }
        holder.current = settings.copy(baseUrl = url)
    }
}
