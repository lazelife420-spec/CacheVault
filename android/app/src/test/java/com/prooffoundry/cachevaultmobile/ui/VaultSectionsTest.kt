package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VaultSectionsTest {

    private fun clip(
        preview: String = "line",
        classification: String? = null,
        contentType: String? = null,
        isFavorite: Boolean = false,
        isSensitive: Boolean = false,
        hasAsset: Boolean = false,
        deletedAt: String? = null,
    ) = ClipSummary(
        id = "c-${preview.hashCode()}",
        preview = preview,
        content = "",
        classification = classification,
        contentType = contentType,
        sourceApp = "app.exe",
        createdAt = "2026-06-16T20:00:00+00:00",
        isFavorite = isFavorite,
        isSensitive = isSensitive,
        collection = null,
        deletedAt = deletedAt,
        hasAsset = hasAsset,
    )

    @Test
    fun homeRecentPreviewLimitedToThree() {
        val all = (1..10).map { clip(preview = "clip $it") }
        assertEquals(3, VaultSections.recentPreview(all).size)
    }

    @Test
    fun browseFilterByTextType() {
        val all = listOf(
            clip(preview = "hello", classification = "text"),
            clip(preview = "https://x.com", classification = "link"),
        )
        val textOnly = VaultSections.filterClips(all, BrowseFilter.TEXT)
        assertEquals(1, textOnly.size)
        assertEquals("TXT", ClipListFormatter.typeBadge(textOnly.first()))
    }

    @Test
    fun duplicateTitlePreviewStillSuppressed() {
        val presentation = ClipListFormatter.cardPresentation(
            clip(preview = "Same line\nSame line"),
        )
        assertEquals("", presentation.preview)
    }

    @Test
    fun sectionCountsIncludeSensitiveAndRemoved() {
        val all = listOf(
            clip(preview = "a", isSensitive = true),
            clip(preview = "b"),
        )
        val removed = listOf(clip(preview = "gone", deletedAt = "2026-06-16T20:00:00+00:00"))
        val counts = VaultSections.computeCounts(all, removed)
        assertEquals(1, counts.sensitive)
        assertEquals(1, counts.recentlyRemoved)
        assertTrue(counts.recentlySaved >= 1)
    }
}
