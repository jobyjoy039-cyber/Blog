package com.ritvayalife.carousel

import org.json.JSONArray
import org.json.JSONObject

/**
 * One slide. Field names match the JSON used by the web renderer in /carousel,
 * so the same files work in both places. Text fields may contain <br>, <i>…</i>,
 * <span class="accent">…</span> or the app's shorthand [[…]] for gold.
 */
data class Slide(
    val pos: String = "upper",
    val tag: String = "",
    val h1: String = "",
    val h2: String = "",
    val divider: Boolean = false,
    val equation: String = "",
    val body: List<String> = emptyList(),
    val rows: List<List<String>> = emptyList(),
    val flows: List<List<String>> = emptyList(),
    val list: List<String> = emptyList(),
    val statement: String = "",
    val cta: String = "",
    val signoff: String = "",
    val foot: String = "",
    val engage: List<List<String>> = emptyList(),
    val follow: String = "",
)

data class Carousel(
    val slug: String,
    val label: String,
    val caption: String = "",
    val slides: List<Slide>,
) {
    val title: String
        get() = slides.firstOrNull()
            ?.let { plain(it.h1.ifBlank { it.h2 }.ifBlank { it.statement }) }
            ?.ifBlank { null } ?: slug
}

/** Strips markup for places that show plain text (list titles). */
fun plain(html: String): String = html
    .replace(Regex("<br\\s*/?>"), " ")
    .replace(Regex("<[^>]+>"), "")
    .replace("[[", "").replace("]]", "")
    .replace(Regex("\\s+"), " ")
    .trim()

object CarouselJson {
    fun parse(text: String): Carousel {
        val o = JSONObject(text)
        val slides = o.optJSONArray("slides") ?: JSONArray()
        return Carousel(
            slug = o.optString("slug"),
            label = o.optString("label"),
            caption = o.str("caption"),
            slides = (0 until slides.length()).map { parseSlide(slides.getJSONObject(it)) },
        )
    }

    fun write(c: Carousel): String {
        val o = JSONObject()
        o.put("slug", c.slug)
        o.put("label", c.label)
        if (c.caption.isNotBlank()) o.put("caption", c.caption)
        o.put("slides", JSONArray(c.slides.map { slideJson(it) }))
        return o.toString(2)
    }

    private fun JSONObject.str(k: String): String = if (has(k) && !isNull(k)) optString(k) else ""

    private fun JSONObject.strings(k: String): List<String> =
        optJSONArray(k)?.let { a -> (0 until a.length()).map { a.optString(it) } } ?: emptyList()

    private fun JSONObject.nested(k: String): List<List<String>> =
        optJSONArray(k)?.let { a ->
            (0 until a.length()).map { i ->
                a.optJSONArray(i)?.let { r -> (0 until r.length()).map { r.optString(it) } } ?: emptyList()
            }
        } ?: emptyList()

    private fun parseSlide(o: JSONObject) = Slide(
        pos = o.optString("pos", "upper"),
        tag = o.str("tag"),
        h1 = o.str("h1"),
        h2 = o.str("h2"),
        divider = o.optBoolean("divider", false),
        equation = o.str("equation"),
        body = o.strings("body"),
        rows = o.nested("rows"),
        flows = o.nested("flows"),
        list = o.strings("list"),
        statement = o.str("statement"),
        cta = o.str("cta"),
        signoff = o.str("signoff"),
        foot = o.str("foot"),
        engage = o.nested("engage"),
        follow = o.str("follow"),
    )

    private fun slideJson(s: Slide) = JSONObject().apply {
        fun str(k: String, v: String) {
            if (v.isNotBlank()) put(k, v)
        }
        fun arr(k: String, v: List<String>) {
            if (v.isNotEmpty()) put(k, JSONArray(v))
        }
        fun nest(k: String, v: List<List<String>>) {
            if (v.isNotEmpty()) put(k, JSONArray(v.map { JSONArray(it) }))
        }
        put("pos", s.pos)
        str("tag", s.tag)
        str("h1", s.h1)
        str("h2", s.h2)
        if (s.divider) put("divider", true)
        str("equation", s.equation)
        arr("body", s.body)
        nest("rows", s.rows)
        nest("flows", s.flows)
        arr("list", s.list)
        str("statement", s.statement)
        str("cta", s.cta)
        str("signoff", s.signoff)
        str("foot", s.foot)
        nest("engage", s.engage)
        str("follow", s.follow)
    }
}

/** The editable parts of a slide, in the order they appear on the slide. */
enum class Field(val label: String, val hint: String, val multiline: Boolean) {
    TAG("Small label", "e.g. TRADITIONAL VIEW", false),
    H1("Hook (big headline)", "6–8 words · Enter = new line", true),
    H2("Headline", "", true),
    EQUATION("Equation line", "e.g. <i>Dina</i> + <i>charya</i>", false),
    BODY("Paragraphs", "One paragraph per line", true),
    ROWS("Rows", "Name | description — one per line", true),
    FLOWS("Cause → effect", "Cause → step → effect — one per line", true),
    LIST("Numbered steps", "One step per line (3 max looks best)", true),
    STATEMENT("Insight", "Wrap words in [[ ]] to make them gold", true),
    CTA("Call to action", "Enter = new line", true),
    SIGNOFF("Sign-off", "e.g. Stay grounded.", false),
    ENGAGE("Save / Share / Follow cards", "save | Save it | For later. — icon: save, share or follow", true),
    FOLLOW("Gold button", "e.g. Follow @ritvayalife", false),
    FOOT("Footnote", "e.g. Modern lens: …", true),
}

private val BR = Regex("<br\\s*/?>")
private fun fromBr(v: String) = v.replace(BR, "\n")
private fun toBr(v: String) = v.trim().replace("\n", "<br>")
private fun lines(v: String) = v.split("\n").map { it.trim() }.filter { it.isNotEmpty() }
private fun cells(v: String, sep: Regex) = lines(v).map { line -> line.split(sep).map { it.trim() } }

fun Slide.get(f: Field): String = when (f) {
    Field.TAG -> tag
    Field.H1 -> fromBr(h1)
    Field.H2 -> fromBr(h2)
    Field.EQUATION -> equation
    Field.BODY -> body.joinToString("\n")
    Field.ROWS -> rows.joinToString("\n") { it.joinToString(" | ") }
    Field.FLOWS -> flows.joinToString("\n") { it.joinToString(" → ") }
    Field.LIST -> list.joinToString("\n")
    Field.STATEMENT -> fromBr(statement)
    Field.CTA -> fromBr(cta)
    Field.SIGNOFF -> signoff
    Field.ENGAGE -> engage.joinToString("\n") { it.joinToString(" | ") }
    Field.FOLLOW -> follow
    Field.FOOT -> foot
}

fun Slide.set(f: Field, v: String): Slide = when (f) {
    Field.TAG -> copy(tag = v.trim())
    Field.H1 -> copy(h1 = toBr(v))
    Field.H2 -> copy(h2 = toBr(v))
    Field.EQUATION -> copy(equation = v.trim())
    Field.BODY -> copy(body = lines(v))
    Field.ROWS -> copy(rows = cells(v, Regex("\\|")))
    Field.FLOWS -> copy(flows = cells(v, Regex("→|->")))
    Field.LIST -> copy(list = lines(v))
    Field.STATEMENT -> copy(statement = toBr(v))
    Field.CTA -> copy(cta = toBr(v))
    Field.SIGNOFF -> copy(signoff = v.trim())
    Field.ENGAGE -> copy(engage = cells(v, Regex("\\|")))
    Field.FOLLOW -> copy(follow = v.trim())
    Field.FOOT -> copy(foot = v.trim())
}

object Templates {
    private fun engage(save: String, share: String) = Slide(
        pos = "mid",
        tag = "BEFORE YOU GO",
        h2 = "Found this helpful?",
        engage = listOf(
            listOf("save", "Save it", save),
            listOf("share", "Share it", share),
            listOf("follow", "Follow", "For more grounded clarity."),
        ),
        follow = "Follow @ritvayalife",
    )

    /** Slide types offered by "Add slide", matching the carousel pattern's slots. */
    val slideTypes: List<Pair<String, Slide>> = listOf(
        "Hook" to Slide(h1 = "Your hook<br>in 6–8 words."),
        "Headline + text" to Slide(h2 = "A short headline", body = listOf("First short line.", "Second short line.")),
        "Rows" to Slide(
            tag = "TRADITIONAL FRAMEWORK",
            h2 = "Headline",
            rows = listOf(listOf("Vata", "movement"), listOf("Pitta", "transformation"), listOf("Kapha", "structure")),
        ),
        "Cause → effect" to Slide(
            h2 = "How it works",
            flows = listOf(listOf("Cause", "step", "effect"), listOf("Other cause", "step", "effect")),
        ),
        "Numbered steps" to Slide(
            h2 = "Start with three steps",
            list = listOf("Step one.", "Step two.", "Step three."),
            foot = "Modern lens: what research adds.",
        ),
        "Insight" to Slide(pos = "low", statement = "One compressed insight, with [[one gold phrase]]."),
        "Action (CTA)" to Slide(
            pos = "mid",
            cta = "Try this for 3 days.<br>Observe what changes.",
            signoff = "Stay grounded.",
        ),
        "Save / Share / Follow" to engage("Save this for later.", "With a friend who needs it."),
    )

    fun newCarousel(slug: String, topic: String): Carousel = Carousel(
        slug = slug,
        label = "RITVAYA • " + topic.uppercase().take(24).trim(),
        slides = listOf(
            Slide(h1 = topic.trim()),
            Slide(h2 = "Name the problem.", body = listOf("What the reader feels.", "Why it keeps happening.")),
            Slide(
                tag = "TRADITIONAL VIEW",
                divider = true,
                h2 = "What it actually means",
                body = listOf("The simple definition.", "Why it matters for daily life."),
            ),
            Slide(
                tag = "TRADITIONAL FRAMEWORK",
                h2 = "How it works",
                rows = listOf(listOf("One", "cause → effect"), listOf("Two", "cause → effect"), listOf("Three", "cause → effect")),
                foot = "Modern lens: what research adds.",
            ),
            Slide(h2 = "Start with three steps", list = listOf("Step one.", "Step two.", "Step three.")),
            Slide(pos = "low", statement = "One compressed insight, with [[one gold phrase]]."),
            Slide(pos = "mid", cta = "Try this for 3 days.<br>Observe what changes.", signoff = "Stay grounded."),
            engage("Save this for later.", "With a friend who needs it."),
        ),
    )
}
