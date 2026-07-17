package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.data.VaultSectionCounts
import java.time.Instant
import java.time.ZoneId

data class ScreenshotGroup(val label: String, val clips: List<ClipSummary>)

/** Client-side vault organization — no bridge auth changes. */
object VaultSections {
    const val HOME_RECENT_LIMIT = 3
    private val DATE_BUCKET_ORDER = listOf("Today", "Yesterday", "Older")

    fun computeCounts(all: List<ClipSummary>, removed: List<ClipSummary>): VaultSectionCounts {
        val live = all.filter { it.deletedAt == null }
        return VaultSectionCounts(
            text = live.count { matchesBrowseFilter(it, BrowseFilter.TEXT) },
            links = live.count { matchesBrowseFilter(it, BrowseFilter.LINKS) },
            code = live.count { matchesBrowseFilter(it, BrowseFilter.CODE) },
            commands = live.count { matchesBrowseFilter(it, BrowseFilter.COMMANDS) },
            screenshots = live.count { ClipKinds.isImageReference(it) && it.hasAsset },
            favorites = live.count { it.isFavorite },
            recentlySaved = live.size,
            sensitive = live.count { it.isSensitive },
            recentlyRemoved = removed.size,
        )
    }

    fun filterClips(
        clips: List<ClipSummary>,
        filter: BrowseFilter,
        removed: List<ClipSummary> = emptyList(),
    ): List<ClipSummary> {
        if (filter == BrowseFilter.REMOVED) return removed
        val live = clips.filter { it.deletedAt == null }
        return when (filter) {
            BrowseFilter.ALL -> live
            BrowseFilter.FAVORITES -> live.filter { it.isFavorite }
            BrowseFilter.TEXT -> live.filter { matchesBrowseFilter(it, BrowseFilter.TEXT) }
            BrowseFilter.LINKS -> live.filter { matchesBrowseFilter(it, BrowseFilter.LINKS) }
            BrowseFilter.CODE -> live.filter { matchesBrowseFilter(it, BrowseFilter.CODE) }
            BrowseFilter.COMMANDS -> live.filter { matchesBrowseFilter(it, BrowseFilter.COMMANDS) }
            BrowseFilter.FILES -> live.filter { matchesBrowseFilter(it, BrowseFilter.FILES) }
            BrowseFilter.SENSITIVE -> live.filter { it.isSensitive }
            BrowseFilter.REMOVED -> removed
        }
    }

    fun screenshotClips(clips: List<ClipSummary>): List<ClipSummary> =
        clips.filter { it.deletedAt == null && ClipKinds.isImageReference(it) }

    /** Buckets screenshots into Today / Yesterday / Older, preserving each clip's existing order within its bucket. */
    fun groupScreenshotsByDate(clips: List<ClipSummary>): List<ScreenshotGroup> {
        val zone = ZoneId.systemDefault()
        val today = java.time.LocalDate.now(zone)
        val buckets = DATE_BUCKET_ORDER.associateWith { mutableListOf<ClipSummary>() }
        clips.forEach { clip ->
            val date = clip.createdAt?.let {
                runCatching { Instant.parse(it).atZone(zone).toLocalDate() }.getOrNull()
            }
            val label = when (date) {
                today -> "Today"
                today.minusDays(1) -> "Yesterday"
                else -> "Older"
            }
            buckets.getValue(label).add(clip)
        }
        return DATE_BUCKET_ORDER.mapNotNull { label ->
            buckets.getValue(label).takeIf { it.isNotEmpty() }?.let { ScreenshotGroup(label, it) }
        }
    }

    fun recentPreview(clips: List<ClipSummary>, limit: Int = HOME_RECENT_LIMIT): List<ClipSummary> =
        clips.filter { it.deletedAt == null }.take(limit)

    private fun matchesBrowseFilter(clip: ClipSummary, filter: BrowseFilter): Boolean = when (filter) {
        BrowseFilter.TEXT -> {
            !ClipKinds.isImageReference(clip) &&
                !ClipKinds.isLink(clip) &&
                !ClipKinds.isPath(clip) &&
                !clip.classification.equals("code", ignoreCase = true) &&
                !clip.classification.equals("command", ignoreCase = true)
        }
        BrowseFilter.LINKS -> ClipKinds.isLink(clip)
        BrowseFilter.CODE -> clip.classification.equals("code", ignoreCase = true)
        BrowseFilter.COMMANDS -> clip.classification.equals("command", ignoreCase = true)
        BrowseFilter.FILES -> ClipKinds.isPath(clip) && !ClipKinds.isImageReference(clip)
        else -> true
    }
}
