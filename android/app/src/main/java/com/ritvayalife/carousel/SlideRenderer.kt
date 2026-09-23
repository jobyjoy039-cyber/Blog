package com.ritvayalife.carousel

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.text.Html
import android.text.StaticLayout
import android.text.TextPaint
import androidx.core.content.res.ResourcesCompat
import kotlin.math.max
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.random.Random

/**
 * Draws Ritvayalife slides with android.graphics, mirroring carousel/render.mjs.
 * Layout is in design units (540 × 675); [render] scales it, so scale 2 gives the
 * 1080 × 1350 Instagram size and scale 1 a lighter preview.
 */
class SlideRenderer(context: Context) {
    private val regular: Typeface = ResourcesCompat.getFont(context, R.font.inter_regular)!!
    private val medium: Typeface = ResourcesCompat.getFont(context, R.font.inter_medium)!!
    private val bold: Typeface = ResourcesCompat.getFont(context, R.font.inter_tight_bold)!!
    private val grain: Bitmap = makeGrain()

    fun render(c: Carousel, index: Int, scale: Float = 2f): Bitmap {
        val bmp = Bitmap.createBitmap((W * scale).roundToInt(), (H * scale).roundToInt(), Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        canvas.scale(scale, scale)
        draw(canvas, c, index.coerceIn(0, c.slides.lastIndex))
        return bmp
    }

    private fun draw(canvas: Canvas, c: Carousel, i: Int) {
        val n = c.slides.size
        drawBackground(canvas, i, n)

        // Frame
        canvas.drawRoundRect(RectF(16.5f, 16.5f, W - 16.5f, H - 16.5f), 6f, 6f, stroke(alpha(HEAD, .14f), 1f))

        // Top label
        val label = textPaint(medium, 9f, alpha(HEAD, .7f), .18f)
        canvas.drawText(c.label, 40f, 34f - label.ascent(), label)

        drawContent(canvas, c.slides[i])

        // Handle with leaf mark
        val handle = textPaint(medium, 10f, alpha(BODY, .8f))
        val baseline = H - 35f
        canvas.save()
        canvas.translate(40f, baseline - 9f)
        canvas.scale(11f / 20f, 11f / 20f)
        canvas.drawPath(
            Path().apply {
                moveTo(3f, 17f); cubicTo(3f, 8f, 9f, 3f, 17f, 3f); cubicTo(17f, 11f, 12f, 17f, 3f, 17f); close()
                moveTo(3f, 17f); lineTo(12f, 8f)
            },
            stroke(HEAD, 1.6f),
        )
        canvas.restore()
        canvas.drawText("@ritvayalife", 56f, baseline, handle)

        // Progress dots
        val widths = List(n) { if (it == i) 16f else 5f }
        var x = W - 40f - (widths.sum() + 6f * (n - 1))
        val y = H - 34f - 5f
        widths.forEachIndexed { k, w ->
            canvas.drawRoundRect(RectF(x, y, x + w, y + 5f), 2.5f, 2.5f, fill(if (k == i) HEAD else alpha(HEAD, .22f)))
            x += w + 6f
        }
    }

    // ---- Background -------------------------------------------------------

    private fun drawBackground(canvas: Canvas, i: Int, n: Int) {
        canvas.drawColor(BG)
        canvas.drawRect(0f, 0f, W, H, Paint().apply {
            shader = RadialGradient(W * .85f, H * .12f, 460f, ALT, alpha(BG, 0f), Shader.TileMode.CLAMP)
        })
        canvas.drawRect(0f, 0f, W, H, Paint().apply {
            shader = BitmapShader(grain, Shader.TileMode.REPEAT, Shader.TileMode.REPEAT)
        })

        // Panorama across all slides; this slide shows its own 540px window.
        canvas.save()
        canvas.translate(-W * i, 0f)
        val wave = Path()
        val wave2 = Path()
        var x = -20f
        while (x <= W * n + 20f) {
            val y = 560f + sin(x / 150f) * 26f + sin(x / 61f) * 6f
            val y2 = y + 16f + sin(x / 90f) * 5f
            if (x == -20f) { wave.moveTo(x, y); wave2.moveTo(x, y2) } else { wave.lineTo(x, y); wave2.lineTo(x, y2) }
            x += 10f
        }
        canvas.drawPath(wave, stroke(alpha(HEAD, .22f), 1.4f))
        canvas.drawPath(wave2, stroke(alpha(ACCENT, .35f), 1f))
        var k = 1
        while (k < n) {
            val cx = W * k
            val cy = if (k % 4 == 1) 118f else 600f
            for (r in listOf(46f, 78f, 112f, 150f)) canvas.drawCircle(cx, cy, r, stroke(alpha(HEAD, .16f - r / 1500f), 1f))
            canvas.drawCircle(cx, cy, 30f, fill(alpha(ACCENT, .10f)))
            k += 2
        }
        canvas.restore()

        when {
            i == 0 -> { sprig(canvas, 575f, 610f, -148f, 1.6f, .42f); sprig(canvas, 560f, 330f, 175f, .9f, .22f) }
            i == n - 1 -> sprig(canvas, 585f, 585f, -150f, 1.4f, .38f)
            else -> sprig(canvas, 548f, 90f, 150f, .8f, .22f)
        }
    }

    private fun leaf(canvas: Canvas, x: Float, y: Float, rot: Float, len: Float) {
        canvas.save()
        canvas.translate(x, y)
        canvas.rotate(rot)
        val p = Path().apply {
            moveTo(0f, 0f)
            cubicTo(len * .3f, -len * .28f, len * .72f, -len * .28f, len, 0f)
            cubicTo(len * .72f, len * .28f, len * .3f, len * .28f, 0f, 0f)
            close()
        }
        canvas.drawPath(p, fill(alpha(HEAD, .10f)))
        canvas.drawPath(p, stroke(HEAD, 1f))
        canvas.drawLine(len * .08f, 0f, len * .9f, 0f, stroke(HEAD, .7f))
        canvas.restore()
    }

    private fun sprig(canvas: Canvas, x: Float, y: Float, rot: Float, scale: Float, opacity: Float) {
        canvas.saveLayerAlpha(null, (opacity * 255).roundToInt())
        canvas.translate(x, y)
        canvas.rotate(rot)
        canvas.scale(scale, scale)
        canvas.drawPath(Path().apply { moveTo(0f, 0f); quadTo(70f, -22f, 136f, -6f) }, stroke(HEAD, 1.1f))
        listOf(Triple(18f, -40f, 34f), Triple(34f, 40f, 38f), Triple(52f, -44f, 40f), Triple(70f, 42f, 36f), Triple(86f, -38f, 30f))
            .forEach { (t, a, l) -> leaf(canvas, t * 1.4f, -sin(t / 30f) * 10f, a, l) }
        leaf(canvas, 136f, -6f, -8f, 30f)
        canvas.restore()
    }

    // ---- Content ----------------------------------------------------------

    private class Block(val marginTop: Float, val height: Float, val draw: (Canvas, Float, Float) -> Unit)

    private fun drawContent(canvas: Canvas, s: Slide) {
        val w = 380
        val blocks = mutableListOf<Block>()
        fun text(mt: Float, l: StaticLayout, dx: Float = 0f) =
            blocks.add(Block(mt, l.height.toFloat()) { c, x, y -> drawLayout(c, l, x + dx, y) })

        if (s.tag.isNotBlank()) {
            text(0f, layout(s.tag, medium, 9f, BODY, w, 1.3f, .16f))
            blocks.add(Block(12f, 0f) { _, _, _ -> })
        }
        if (s.h1.isNotBlank()) text(0f, layout(s.h1, bold, 44f, HEAD, w, 1.08f, -.01f))
        if (s.h2.isNotBlank()) text(0f, layout(s.h2, bold, 28f, HEAD, w, 1.15f, -.01f))
        if (s.divider) blocks.add(Block(16f, 1f) { c, x, y -> c.drawRect(x, y, x + 48f, y + 1f, fill(alpha(HEAD, .25f))) })
        if (s.equation.isNotBlank()) text(24f, layout(s.equation, bold, 24f, HEAD, w, 1.25f))
        s.body.forEachIndexed { k, p -> text(if (k == 0) 24f else 16f, layout(p, regular, 19f, BODY, w, 1.4f)) }

        s.rows.forEachIndexed { k, row ->
            val name = layout(row.getOrElse(0) { "" }, medium, 18f, HEAD, 72, 1.35f)
            val desc = layout(row.drop(1).joinToString(" · "), regular, 18f, BODY, w - 32 - 72, 1.35f)
            val h = 24f + max(name.height, desc.height)
            blocks.add(Block(if (k == 0) 24f else 10f, h) { c, x, y ->
                card(c, x, y, h, 10f)
                drawLayout(c, name, x + 16f, y + 12f)
                drawLayout(c, desc, x + 16f + 72f, y + 12f)
            })
        }

        s.flows.forEachIndexed { k, flow ->
            val lead = k == 0
            val from = layout(flow.firstOrNull().orEmpty(), medium, 19f, if (lead) HEAD else BODY, w - 32 - 3, 1.35f)
            val to = layout("→ " + flow.drop(1).joinToString(" → "), regular, 18f, BODY, w - 32 - 3, 1.4f)
            val h = 28f + from.height + 4f + to.height
            blocks.add(Block(if (k == 0) 24f else 12f, h) { c, x, y ->
                card(c, x, y, h, 10f)
                if (lead) {
                    c.save()
                    c.clipPath(Path().apply { addRoundRect(RectF(x, y, x + w, y + h), 10f, 10f, Path.Direction.CW) })
                    c.drawRect(x, y, x + 3f, y + h, fill(HEAD))
                    c.restore()
                }
                drawLayout(c, from, x + 19f, y + 14f)
                drawLayout(c, to, x + 19f, y + 14f + from.height + 4f)
            })
        }

        s.list.forEachIndexed { k, item ->
            val num = layout("%02d".format(k + 1), bold, 22f, HEAD, 40, 1.2f)
            val body = layout(item, medium, 18f, BODY, w - 32 - 32 - 14, 1.35f)
            val inner = max(num.height, body.height).toFloat()
            val h = 24f + inner
            blocks.add(Block(if (k == 0) 24f else 10f, h) { c, x, y ->
                card(c, x, y, h, 10f)
                drawLayout(c, num, x + 16f, y + 12f + (inner - num.height) / 2f)
                drawLayout(c, body, x + 16f + 32f + 14f, y + 12f + (inner - body.height) / 2f)
            })
        }

        if (s.statement.isNotBlank()) {
            val quote = textPaint(bold, 96f, alpha(HEAD, .18f))
            blocks.add(Block(0f, 40f) { c, x, y -> c.drawText("“", x - 4f, y + 64f, quote) })
            text(0f, layout(s.statement, bold, 32f, HEAD, w, 1.18f, -.01f))
        }

        if (s.cta.isNotBlank()) {
            val cta = layout(s.cta, medium, 22f, HEAD, w - 48, 1.35f)
            val sign = s.signoff.takeIf { it.isNotBlank() }?.let { layout(it, regular, 16f, BODY, w - 48, 1.3f) }
            val h = 24f + cta.height + (sign?.let { 24f + it.height } ?: 0f) + 22f
            blocks.add(Block(0f, h) { c, x, y ->
                card(c, x, y, h, 14f, .12f)
                drawLayout(c, cta, x + 24f, y + 24f)
                sign?.let { drawLayout(c, it, x + 24f, y + 24f + cta.height + 24f) }
            })
        }

        s.engage.forEachIndexed { k, e ->
            val title = layout(e.getOrElse(1) { "" }, medium, 18f, HEAD, w - 32 - 30 - 14, 1.35f)
            val desc = layout(e.getOrElse(2) { "" }, regular, 17f, BODY, w - 32 - 30 - 14, 1.35f)
            val inner = max(30f, (title.height + desc.height).toFloat())
            val h = 26f + inner
            blocks.add(Block(if (k == 0) 24f else 10f, h) { c, x, y ->
                card(c, x, y, h, 10f)
                icon(c, e.getOrElse(0) { "" }, x + 16f, y + 13f + (inner - 30f) / 2f)
                val ty = y + 13f + (inner - title.height - desc.height) / 2f
                drawLayout(c, title, x + 16f + 30f + 14f, ty)
                drawLayout(c, desc, x + 16f + 30f + 14f, ty + title.height)
            })
        }

        if (s.follow.isNotBlank()) {
            val p = textPaint(medium, 18f, WHITE)
            val tw = p.measureText(s.follow)
            val h = 12f + 22f + 12f
            blocks.add(Block(24f, h) { c, x, y ->
                c.drawRoundRect(RectF(x, y, x + tw + 44f, y + h), h / 2f, h / 2f, fill(ACCENT))
                c.drawText(s.follow, x + 22f, y + h / 2f - (p.ascent() + p.descent()) / 2f, p)
            })
        }

        if (s.foot.isNotBlank()) {
            val foot = layout(s.foot, regular, 15f, alpha(BODY, .9f), w - 14, 1.45f)
            blocks.add(Block(24f, foot.height.toFloat()) { c, x, y ->
                c.drawRect(x, y, x + 2f, y + foot.height, fill(alpha(HEAD, .25f)))
                drawLayout(c, foot, x + 14f, y)
            })
        }

        // Centre the stack in the content area, then shift by the slide's position.
        val total = blocks.sumOf { (it.marginTop + it.height).toDouble() }.toFloat()
        val shift = when (s.pos) { "mid" -> 0f; "low" -> 40f; else -> -36f }
        var y = 80f + (H - 90f - 80f - total) / 2f + shift
        for (b in blocks) {
            y += b.marginTop
            b.draw(canvas, 40f, y)
            y += b.height
        }
    }

    private fun icon(c: Canvas, kind: String, x: Float, y: Float) {
        c.drawCircle(x + 15f, y + 15f, 15f, fill(alpha(HEAD, .08f)))
        val p = Path()
        when (kind) {
            "save" -> { p.moveTo(7f, 4f); p.lineTo(17f, 4f); p.lineTo(17f, 20f); p.lineTo(12f, 16f); p.lineTo(7f, 20f); p.close() }
            "share" -> {
                p.moveTo(21f, 3f); p.lineTo(3f, 10f); p.lineTo(10f, 13f); p.lineTo(13f, 20f); p.close()
                p.moveTo(10f, 13f); p.lineTo(21f, 3f)
            }
            else -> {
                p.addCircle(9f, 8f, 4f, Path.Direction.CW)
                p.moveTo(2f, 20f); p.cubicTo(2f, 16f, 5f, 14f, 9f, 14f); p.cubicTo(13f, 14f, 16f, 16f, 16f, 20f)
                p.moveTo(19f, 8f); p.lineTo(19f, 14f)
                p.moveTo(16f, 11f); p.lineTo(22f, 11f)
            }
        }
        c.save()
        c.translate(x, y)
        c.scale(1.25f, 1.25f)
        c.translate(5f, 5f)
        c.scale(.58f, .58f)
        c.drawPath(p, stroke(HEAD, 2f).apply { strokeJoin = Paint.Join.ROUND; strokeCap = Paint.Cap.ROUND })
        c.restore()
    }

    private fun card(c: Canvas, x: Float, y: Float, h: Float, r: Float, border: Float = .10f) {
        val rect = RectF(x, y, x + 380f, y + h)
        c.drawRoundRect(rect, r, r, fill(alpha(WHITE, .55f)))
        c.drawRoundRect(rect, r, r, stroke(alpha(HEAD, border), 1f))
    }

    // ---- Text -------------------------------------------------------------

    private fun layout(
        raw: String, tf: Typeface, size: Float, color: Int, width: Int, lineHeight: Float, spacing: Float = 0f,
    ): StaticLayout {
        val paint = textPaint(tf, size, color, spacing)
        val text = html(raw)
        val natural = paint.fontMetrics.let { it.descent - it.ascent }
        return StaticLayout.Builder.obtain(text, 0, text.length, paint, width)
            .setLineSpacing(size * lineHeight - natural, 1f)
            .setIncludePad(false)
            .build()
    }

    private fun drawLayout(c: Canvas, l: StaticLayout, x: Float, y: Float) {
        c.save()
        c.translate(x, y)
        l.draw(c)
        c.restore()
    }

    /** <br>, <i>, <span class="accent"> and the [[gold]] shorthand. */
    private fun html(s: String): CharSequence {
        val gold = "<font color=\"#C2A87D\">\$1</font>"
        val t = s.replace("\n", "<br>")
            .replace(Regex("<span class=\"accent\">(.*?)</span>"), gold)
            .replace(Regex("\\[\\[(.*?)]]"), gold)
        val spanned = Html.fromHtml(t, Html.FROM_HTML_MODE_LEGACY)
        var end = spanned.length
        while (end > 0 && spanned[end - 1].isWhitespace()) end--
        return spanned.subSequence(0, end)
    }

    private fun textPaint(tf: Typeface, size: Float, color: Int, spacing: Float = 0f) =
        TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = tf
            textSize = size
            this.color = color
            letterSpacing = spacing
        }

    private fun fill(color: Int) = Paint(Paint.ANTI_ALIAS_FLAG).apply { this.color = color; style = Paint.Style.FILL }

    private fun stroke(color: Int, width: Float) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color
        style = Paint.Style.STROKE
        strokeWidth = width
    }

    private fun makeGrain(): Bitmap {
        val size = 160
        val rnd = Random(7)
        val pixels = IntArray(size * size) { alpha(HEAD, rnd.nextFloat() * .055f) }
        return Bitmap.createBitmap(pixels, size, size, Bitmap.Config.ARGB_8888)
    }

    companion object {
        const val W = 540f
        const val H = 675f
        private val BG = 0xFFF5F1E8.toInt()
        private val ALT = 0xFFE8E2D6.toInt()
        private val HEAD = 0xFF2E5E4E.toInt()
        private val BODY = 0xFF6B6B6B.toInt()
        private val ACCENT = 0xFFC2A87D.toInt()
        private val WHITE = 0xFFFFFFFF.toInt()

        private fun alpha(color: Int, a: Float): Int =
            (color and 0x00FFFFFF) or ((a.coerceIn(0f, 1f) * 255).roundToInt() shl 24)
    }
}
