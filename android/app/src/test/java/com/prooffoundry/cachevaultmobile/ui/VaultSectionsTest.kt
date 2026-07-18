package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class VaultSectionsTest {

    private fun clip(
        preview: String = "line",
        classification: String? = null,
        contentType: String? = null,
        isFavorite: Boolean = false,
        isSensitive: Boolean = false,
        hasAsset: Boolean = false,
        deletedAt: String? = null,
        createdAt: String? = "2026-06-16T20:00:00+00:00",
    ) = ClipSummary(
        id = "c-${preview.hashCode()}",
        preview = preview,
        content = "",
        classification = classification,
        contentType = contentType,
        sourceApp = "app.exe",
        createdAt = createdAt,
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

    @Test
    fun groupsScreenshotsIntoTodayYesterdayAndOlder() {
        val now = Instant.now()
        val todayShot = clip(preview = "today", createdAt = now.toString())
        val yesterdayShot = clip(preview = "yesterday", createdAt = now.minusSeconds(60 * 60 * 24).toString())
        val olderShot = clip(preview = "older", createdAt = now.minusSeconds(60 * 60 * 24 * 10).toString())

        val groups = VaultSections.groupScreenshotsByDate(listOf(todayShot, yesterdayShot, olderShot))
        val labels = groups.map { it.label }

        assertTrue(labels.contains("Today"))
        assertEquals("today", groups.first { it.label == "Today" }.clips.single().preview)
        assertEquals("older", groups.first { it.label == "Older" }.clips.single().preview)
    }

    @Test
    fun groupingOmitsEmptyBuckets() {
        val onlyOld = clip(preview = "ancient", createdAt = "2020-01-01T00:00:00Z")
        val groups = VaultSections.groupScreenshotsByDate(listOf(onlyOld))
        assertEquals(listOf("Older"), groups.map { it.label })
    }

    @Test
    fun groupingTreatsMissingTimestampAsOlder() {
        val noTimestamp = clip(preview = "no-time", createdAt = null)
        val groups = VaultSections.groupScreenshotsByDate(listOf(noTimestamp))
        assertEquals(listOf("Older"), groups.map { it.label })
    }
}
