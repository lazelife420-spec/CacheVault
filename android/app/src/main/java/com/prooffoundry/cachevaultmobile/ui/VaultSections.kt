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
            text = live.count { typeBadge(it) == "TXT" },
            links = live.count { typeBadge(it) == "LINK" },
            code = live.count { typeBadge(it) == "CODE" },
            commands = live.count { typeBadge(it) == "CMD" },
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
            BrowseFilter.TEXT -> live.filter { typeBadge(it) == "TXT" }
            BrowseFilter.LINKS -> live.filter { typeBadge(it) == "LINK" }
            BrowseFilter.CODE -> live.filter { typeBadge(it) == "CODE" }
            BrowseFilter.COMMANDS -> live.filter { typeBadge(it) == "CMD" }
            BrowseFilter.FILES -> live.filter { typeBadge(it) == "FILE" }
            BrowseFilter.SENSITIVE -> live.filter { it.isSensitive }
            BrowseFilter.REMOVED -> removed
        }
    }

    fun screenshotClips(clips: List<ClipSummary>): List<ClipSummary> =
        clips.filter { it.deletedAt == null && ClipKinds.isImageReference(it) }

    fun recentPreview(clips: List<ClipSummary>, limit: Int = HOME_RECENT_LIMIT): List<ClipSummary> =
        clips.filter { it.deletedAt == null }.take(limit)

    private fun typeBadge(clip: ClipSummary): String = ClipListFormatter.typeBadge(clip)
}
