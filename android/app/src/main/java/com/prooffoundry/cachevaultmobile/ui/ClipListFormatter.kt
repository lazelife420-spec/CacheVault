package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import java.net.URI
import java.time.LocalDate
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

/** List-safe clip presentation — never dump full bodies in the vault list. */
object ClipListFormatter {
    const val PREVIEW_MAX_LINES = 2
    const val PREVIEW_MAX_CHARS = 100
    const val TITLE_MAX_CHARS = 70

    data class CardPresentation(
        val title: String,
        val preview: String,
        val dateLine: String,
    )

    fun typeBadge(clip: ClipSummary): String = when {
        ClipKinds.isImageReference(clip) -> "IMAGE"
        ClipKinds.isLink(clip) -> "LINK"
        clip.classification.equals("code", ignoreCase = true) -> "CODE"
        clip.classification.equals("command", ignoreCase = true) -> "CMD"
        ClipKinds.isPath(clip) -> "FILE"
        else -> "TXT"
    }

    fun cardPresentation(clip: ClipSummary): CardPresentation = when {
        ClipKinds.isImageReference(clip) -> imagePresentation(clip)
        ClipKinds.isLink(clip) -> linkPresentation(clip)
        else -> textPresentation(clip)
    }

    /** @deprecated Use [cardPresentation] — kept for detail screens. */
    fun cardTitle(clip: ClipSummary): String = cardPresentation(clip).title

    /** @deprecated Use [cardPresentation] — kept for tests. */
    fun cardPreview(clip: ClipSummary): String = cardPresentation(clip).preview

    fun sourceLabel(clip: ClipSummary): String? =
        clip.sourceApp?.substringAfterLast('\\')?.substringAfterLast('/')
            ?.takeIf { it.isNotBlank() }

    fun formatWhen(iso: String?): String {
        if (iso.isNullOrBlank()) return ""
        return runCatching {
            val instant = Instant.parse(iso)
            DateTimeFormatter.ofLocalizedDateTime(FormatStyle.SHORT)
                .withLocale(Locale.getDefault())
                .withZone(ZoneId.systemDefault())
                .format(instant)
        }.getOrElse { iso.take(16).replace('T', ' ') }
    }

    fun formatRelativeWhen(iso: String?): String {
        if (iso.isNullOrBlank()) return "Never"
        return runCatching {
            val instant = Instant.parse(iso)
            val zone = ZoneId.systemDefault()
            val localDate = instant.atZone(zone).toLocalDate()
            val today = LocalDate.now(zone)
            val time = DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT)
                .withLocale(Locale.getDefault())
                .withZone(zone)
                .format(instant)
            when (localDate) {
                today -> "Today, $time"
                today.minusDays(1) -> "Yesterday, $time"
                else -> formatWhen(iso)
            }
        }.getOrElse { formatWhen(iso).ifBlank { "Never" } }
    }

    fun dateLine(clip: ClipSummary): String = formatWhen(clip.createdAt)

    fun imageSubtitle(clip: ClipSummary): String {
        val dims = clip.preview
            .removePrefix("Screenshot")
            .trim()
            .removePrefix("(")
            .removeSuffix(")")
            .trim()
        return when {
            dims.isNotBlank() && clip.hasAsset -> "$dims · on PC"
            dims.isNotBlank() -> dims
            clip.hasAsset -> "on PC"
            else -> "metadata only"
        }
    }

    private fun textPresentation(clip: ClipSummary): CardPresentation {
        val raw = clip.preview.trim()
        val lines = splitLines(raw)
        val title = titleFromLines(lines) ?: "(no preview)"
        val preview = previewAfterTitle(lines, title)
        return CardPresentation(title, preview, dateLine(clip))
    }

    private fun linkPresentation(clip: ClipSummary): CardPresentation {
        val url = ClipKinds.linkUrl(clip)
        val host = url?.let { runCatching { URI(it).host }.getOrNull() }
        val title = host?.takeIf { it.isNotBlank() }
            ?: titleFromLines(splitLines(clip.preview))
            ?: "Link"
        val preview = when {
            url.isNullOrBlank() -> previewAfterTitle(splitLines(clip.preview), title)
            url.length <= PREVIEW_MAX_CHARS -> url
            else -> url.take(PREVIEW_MAX_CHARS - 1) + "…"
        }.let { p -> if (normalize(p) == normalize(title)) "" else p }
        return CardPresentation(title, preview, dateLine(clip))
    }

    private fun imagePresentation(clip: ClipSummary): CardPresentation {
        val subtitle = imageSubtitle(clip)
        return CardPresentation(imageTitle(clip), subtitle, dateLine(clip))
    }

    /** "Screenshot" alone repeats identically across every image clip — append a time so items are distinguishable. */
    fun imageTitle(clip: ClipSummary): String {
        val time = formatRelativeWhen(clip.createdAt)
        return if (time.isNotBlank() && time != "Never") "Screenshot · $time" else "Screenshot"
    }

    private fun titleFromLines(lines: List<String>): String? {
        val first = lines.firstOrNull { it.isNotBlank() } ?: return null
        val cleaned = first.removePrefix("#").removePrefix("##").trim()
        if (cleaned.isBlank()) return null
        return truncateChars(cleaned, TITLE_MAX_CHARS)
    }

    private fun previewAfterTitle(
        lines: List<String>,
        title: String,
    ): String {
        if (lines.size <= 1) return ""
        val titleNorm = normalize(title)
        val rest = lines.drop(1).filter { normalize(it) != titleNorm && it.isNotBlank() }
        if (rest.isEmpty()) return ""
        val joined = rest.take(PREVIEW_MAX_LINES).joinToString("\n")
        val truncated = truncateChars(joined, PREVIEW_MAX_CHARS)
        if (normalize(truncated) == titleNorm) return ""
        if (titleNorm.startsWith(normalize(truncated.take(24))) && truncated.length < 32) return ""
        return truncated
    }

    private fun splitLines(text: String): List<String> =
        text.replace("\r\n", "\n").replace('\r', '\n')
            .split('\n')
            .map { it.trim() }
            .filter { it.isNotEmpty() }

    private fun normalize(text: String): String =
        text.lowercase(Locale.getDefault()).replace(Regex("\\s+"), " ").trim()

    private fun truncateChars(text: String, max: Int): String =
        if (text.length <= max) text else text.take(max - 1).trimEnd() + "…"
}
