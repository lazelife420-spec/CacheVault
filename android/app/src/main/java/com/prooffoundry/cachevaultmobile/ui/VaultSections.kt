package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.data.VaultSectionCounts

/** Client-side vault organization — no bridge auth changes. */
object VaultSections {
    const val HOME_RECENT_LIMIT = 3

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
