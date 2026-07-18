package com.prooffoundry.cachevaultmobile.ui

/** Pure index math for the full-screen image viewer's swipe navigation — no wrap-around. */
object ImageGallery {
    /** Clamps a navigation step to the gallery's bounds; never wraps past the first/last item. */
    fun clampIndex(current: Int, delta: Int, size: Int): Int {
        if (size <= 0) return 0
        return (current + delta).coerceIn(0, size - 1)
    }

    /** Immediate previous/next indices worth preloading, bounded to the gallery's extent. */
    fun neighborIndices(index: Int, size: Int): List<Int> =
        listOf(index - 1, index + 1).filter { it in 0 until size }
}
