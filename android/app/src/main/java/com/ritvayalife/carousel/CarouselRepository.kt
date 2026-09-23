package com.ritvayalife.carousel

import android.content.Context
import java.io.File

/** Stores each carousel as <slug>.json in the app's private files. */
class CarouselRepository(private val context: Context) {
    private val dir = File(context.filesDir, "carousels").apply { mkdirs() }

    /** On first launch, copies the bundled example carousels in. */
    fun seedIfNeeded() {
        val marker = File(dir, ".seeded")
        if (marker.exists()) return
        val assets = context.assets
        assets.list("").orEmpty().filter { it.endsWith(".json") }.forEach { name ->
            val target = File(dir, name)
            if (!target.exists()) {
                assets.open(name).use { input -> target.outputStream().use { input.copyTo(it) } }
            }
        }
        marker.createNewFile()
    }

    fun loadAll(): List<Carousel> = dir.listFiles { f -> f.extension == "json" }.orEmpty()
        .sortedByDescending { it.lastModified() }
        .mapNotNull { runCatching { CarouselJson.parse(it.readText()) }.getOrNull() }

    fun load(slug: String): Carousel? =
        File(dir, "$slug.json").takeIf { it.exists() }?.let { runCatching { CarouselJson.parse(it.readText()) }.getOrNull() }

    fun save(c: Carousel) = File(dir, "${c.slug}.json").writeText(CarouselJson.write(c))

    fun delete(slug: String) = File(dir, "$slug.json").delete()

    fun create(topic: String): Carousel {
        val c = Templates.newCarousel(uniqueSlug(topic), topic)
        save(c)
        return c
    }

    fun duplicate(c: Carousel): Carousel {
        val copy = c.copy(slug = uniqueSlug(c.slug))
        save(copy)
        return copy
    }

    private fun uniqueSlug(text: String): String {
        val base = text.lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').take(40).ifBlank { "carousel" }
        var slug = base
        var n = 2
        while (File(dir, "$slug.json").exists()) slug = "$base-${n++}"
        return slug
    }
}
