package com.prooffoundry.cachevaultmobile.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClipKindsTest {
    @Test
    fun linkClipDetected() {
        val clip = ClipSummary(
            id = "1", preview = "https://example.com", content = "https://example.com",
            classification = "link", contentType = "text", sourceApp = null,
            createdAt = null, isFavorite = false, isSensitive = false,
            collection = null, deletedAt = null,
        )
        assertTrue(ClipKinds.isLink(clip))
        assertTrue(ClipKinds.linkUrl(clip)?.startsWith("https://") == true)
    }

    @Test
    fun imagePathReferenceDetected() {
        val clip = ClipSummary(
            id = "2", preview = "C:\\shots\\cap.png", content = "",
            classification = "path", contentType = "text", sourceApp = null,
            createdAt = null, isFavorite = false, isSensitive = false,
            collection = null, deletedAt = null,
        )
        assertTrue(ClipKinds.isImageReference(clip))
    }

    @Test
    fun plainTextIsNotImage() {
        val clip = ClipSummary(
            id = "3", preview = "hello", content = "hello",
            classification = "plain", contentType = "text", sourceApp = null,
            createdAt = null, isFavorite = false, isSensitive = false,
            collection = null, deletedAt = null,
        )
        assertFalse(ClipKinds.isImageReference(clip))
    }

    @Test
    fun imageContentTypeDetected() {
        val clip = ClipSummary(
            id = "4", preview = "Screenshot (100×50)", content = "[Screenshot PNG 100×50]",
            classification = "image", contentType = "image", sourceApp = "SnippingTool.exe",
            createdAt = null, isFavorite = false, isSensitive = false,
            collection = null, deletedAt = null, hasAsset = true,
        )
        assertTrue(ClipKinds.isImageReference(clip))
    }
}
