package com.prooffoundry.cachevaultmobile.data

/** Clip presentation helpers — no storage changes on desktop. */
object ClipKinds {
    private val imageExt = setOf(".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

    fun isLink(clip: ClipSummary): Boolean =
        clip.classification.equals("link", ignoreCase = true)

    fun isPath(clip: ClipSummary): Boolean =
        clip.classification.equals("path", ignoreCase = true)

    fun isImageReference(clip: ClipSummary): Boolean {
        if (clip.hasAsset) return true
        if (clip.contentType.equals("image", ignoreCase = true)) return true
        if (!isPath(clip)) return false
        val ref = (clip.content.ifBlank { clip.preview }).lowercase()
        return imageExt.any { ref.trim().endsWith(it) }
    }

    fun linkUrl(clip: ClipSummary): String? {
        if (!isLink(clip)) return null
        val url = clip.content.ifBlank { clip.preview }.trim()
        return url.ifBlank { null }
    }
}
