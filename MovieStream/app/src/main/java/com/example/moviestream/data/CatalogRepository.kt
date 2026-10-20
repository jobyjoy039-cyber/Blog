package com.example.moviestream.data

import android.content.Context
import android.util.Log
import com.example.moviestream.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Loads the movie catalog. If [BuildConfig.CATALOG_URL] is set the catalog is fetched from there,
 * falling back to the copy bundled in assets when offline or the request fails.
 */
class CatalogRepository(private val context: Context) {

    suspend fun load(): List<Movie> = withContext(Dispatchers.IO) {
        val remote = BuildConfig.CATALOG_URL.takeIf { it.isNotBlank() }?.let { url ->
            runCatching { parse(fetch(url)) }
                .onFailure { Log.w(TAG, "Remote catalog failed, using bundled copy", it) }
                .getOrNull()
        }
        remote ?: parse(context.assets.open("catalog.json").bufferedReader().use { it.readText() })
    }

    private fun fetch(url: String): String {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 10_000
        connection.readTimeout = 10_000
        return try {
            check(connection.responseCode == HttpURLConnection.HTTP_OK) { "HTTP ${connection.responseCode}" }
            connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun parse(json: String): List<Movie> {
        val items = JSONObject(json).getJSONArray("movies")
        return List(items.length()) { i ->
            val o = items.getJSONObject(i)
            val genres = o.optJSONArray("genres")
            Movie(
                id = o.getString("id"),
                title = o.getString("title"),
                year = o.optInt("year"),
                durationMinutes = o.optInt("durationMinutes"),
                rating = o.optString("rating"),
                genres = genres?.let { arr -> List(arr.length()) { arr.getString(it) } }.orEmpty(),
                featured = o.optBoolean("featured"),
                description = o.optString("description"),
                posterUrl = if (o.isNull("poster")) null else o.optString("poster").ifBlank { null },
                streamUrl = o.getString("stream"),
                credit = o.optString("credit"),
            )
        }
    }

    private companion object {
        const val TAG = "CatalogRepository"
    }
}
