package com.ritvayalife.carousel

import android.content.ClipData
import android.content.ClipboardManager
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Saves slides as 1080 × 1350 PNGs to Pictures/Ritvaya/<slug> and shares them. */
object Exporter {
    fun folder(c: Carousel) = "${Environment.DIRECTORY_PICTURES}/Ritvaya/${c.slug}"

    suspend fun saveAll(context: Context, renderer: SlideRenderer, c: Carousel): List<Uri> = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val collection = MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        val path = folder(c) + "/"

        // Replace this app's earlier export of the same carousel instead of piling up copies.
        runCatching {
            resolver.delete(collection, "${MediaStore.Images.Media.RELATIVE_PATH} = ?", arrayOf(path))
        }

        c.slides.indices.map { i ->
            val bmp = renderer.render(c, i, 2f)
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, "%s_%02d.png".format(c.slug, i + 1))
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                put(MediaStore.Images.Media.RELATIVE_PATH, path)
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val uri = resolver.insert(collection, values) ?: error("Could not create image ${i + 1}")
            resolver.openOutputStream(uri).use { out ->
                requireNotNull(out) { "Could not write image ${i + 1}" }
                bmp.compress(Bitmap.CompressFormat.PNG, 100, out)
            }
            bmp.recycle()
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            uri
        }
    }

    fun share(context: Context, uris: List<Uri>) {
        val send = Intent(Intent.ACTION_SEND_MULTIPLE).apply {
            type = "image/png"
            putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(send, "Share carousel").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun copy(context: Context, label: String, text: String) {
        val clipboard = context.getSystemService(ClipboardManager::class.java)
        clipboard?.setPrimaryClip(ClipData.newPlainText(label, text))
    }
}
