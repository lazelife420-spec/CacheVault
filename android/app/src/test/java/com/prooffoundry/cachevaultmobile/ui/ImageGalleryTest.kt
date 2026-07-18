package com.prooffoundry.cachevaultmobile.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class ImageGalleryTest {

    @Test
    fun advancesToNextIndex() {
        assertEquals(1, ImageGallery.clampIndex(current = 0, delta = 1, size = 5))
    }

    @Test
    fun stepsBackToPreviousIndex() {
        assertEquals(1, ImageGallery.clampIndex(current = 2, delta = -1, size = 5))
    }

    @Test
    fun doesNotWrapPastLastImage() {
        assertEquals(4, ImageGallery.clampIndex(current = 4, delta = 1, size = 5))
    }

    @Test
    fun doesNotWrapPastFirstImage() {
        assertEquals(0, ImageGallery.clampIndex(current = 0, delta = -1, size = 5))
    }

    @Test
    fun emptyGalleryAlwaysResolvesToZero() {
        assertEquals(0, ImageGallery.clampIndex(current = 0, delta = 1, size = 0))
    }

    @Test
    fun neighborIndicesIncludeBothSidesInTheMiddle() {
        assertEquals(listOf(4, 6), ImageGallery.neighborIndices(index = 5, size = 10))
    }

    @Test
    fun neighborIndicesOmitOutOfRangeSideAtStart() {
        assertEquals(listOf(1), ImageGallery.neighborIndices(index = 0, size = 10))
    }

    @Test
    fun neighborIndicesOmitOutOfRangeSideAtEnd() {
        assertEquals(listOf(8), ImageGallery.neighborIndices(index = 9, size = 10))
    }

    @Test
    fun singleImageGalleryHasNoNeighbors() {
        assertEquals(emptyList<Int>(), ImageGallery.neighborIndices(index = 0, size = 1))
    }
}
