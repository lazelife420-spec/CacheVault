package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.ClipSummary
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClipListFormatterTest {

    private fun clip(
        preview: String = "",
        content: String = "",
        classification: String? = null,
        contentType: String? = null,
        hasAsset: Boolean = false,
    ) = ClipSummary(
        id = "c1",
        preview = preview,
        content = content,
        classification = classification,
        contentType = contentType,
        sourceApp = "Cursor.exe",
        createdAt = "2026-06-16T20:00:00+00:00",
        isFavorite = false,
        isSensitive = false,
        collection = null,
        deletedAt = null,
        hasAsset = hasAsset,
    )

    @Test
    fun cardPreviewTruncatesLongMarkdown() {
        val long = "# Root cause\n\n" + "line two\n" + "x".repeat(500)
        val preview = ClipListFormatter.cardPreview(clip(preview = long))
        assertTrue(preview.length <= ClipListFormatter.PREVIEW_MAX_CHARS + 1)
        assertFalse(preview.contains("x".repeat(200)))
    }

    @Test
    fun cardTitleUsesFirstLineNotFullBody() {
        val title = ClipListFormatter.cardTitle(
            clip(preview = "# Root cause: smoke revoked pixel-live\n\nMore body text"),
        )
        assertEquals("Root cause: smoke revoked pixel-live", title)
    }

    @Test
    fun duplicateTitlePreviewSuppressed() {
        val presentation = ClipListFormatter.cardPresentation(
            clip(preview = "Root cause: smoke revoked pixel-live\nRoot cause: smoke revoked pixel-live"),
        )
        assertEquals("Root cause: smoke revoked pixel-live", presentation.title)
        assertEquals("", presentation.preview)
    }

    @Test
    fun previewUsesLinesAfterTitle() {
        val presentation = ClipListFormatter.cardPresentation(
            clip(preview = "Root cause: smoke revoked pixel-live\nSecond line detail here"),
        )
        assertEquals("Root cause: smoke revoked pixel-live", presentation.title)
        assertEquals("Second line detail here", presentation.preview)
    }

    @Test
    fun imagePresentationUsesScreenshotTitle() {
        val presentation = ClipListFormatter.cardPresentation(
            clip(
                preview = "Screenshot (37×29)",
                contentType = "image",
                classification = "image",
                hasAsset = true,
            ),
        )
        assertEquals("Screenshot", presentation.title)
        assertTrue(presentation.preview.contains("37"))
    }

    @Test
    fun typeBadgeForImage() {
        assertEquals("IMAGE", ClipListFormatter.typeBadge(
            clip(
                preview = "Screenshot (37×29)",
                contentType = "image",
                classification = "image",
                hasAsset = true,
            ),
        ))
    }

    @Test
    fun connectedStateRequiresStatusWithoutError() {
        assertEquals(
            ConnectionState.CONNECTED,
            resolveConnectionState(status = dummyStatus(), error = null, loading = false, hasLoadedVault = true),
        )
        assertEquals(
            ConnectionState.OFFLINE,
            resolveConnectionState(status = null, error = "Cannot reach PC", loading = false, hasLoadedVault = true),
        )
    }

    @Test
    fun initialLoadShowsChecking() {
        assertEquals(
            ConnectionState.CHECKING,
            resolveConnectionState(status = null, error = null, loading = true, hasLoadedVault = false),
        )
    }

    @Test
    fun revokedStateDetectedFromError() {
        assertEquals(
            ConnectionState.REVOKED,
            resolveConnectionState(status = null, error = "Device revoked.", loading = false, hasLoadedVault = true),
        )
    }

    private fun dummyStatus() = com.prooffoundry.cachevaultmobile.data.BridgeStatus(
        product = "Cache Vault",
        byline = "",
        mobileApiVersion = "1",
        mobileAccessEnabled = true,
        cacheVaultVersion = "0.1",
        deviceId = "pixel-live",
        readOnly = true,
    )
}
