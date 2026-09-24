package com.prooffoundry.cachevaultmobile.data.local

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Recognition rules for shared/typed payloads (CV-MOBILE-1): canceled,
 * malformed and oversized intake are their own outcomes — never persisted as
 * placeholder items.
 */
class LocalIngestionTest {

    @Test
    fun blankAndMissingTextAreInvalid() {
        assertTrue(LocalIngestion.recognizeText(null) is LocalIngestion.Incoming.Invalid)
        assertTrue(LocalIngestion.recognizeText("") is LocalIngestion.Incoming.Invalid)
        assertTrue(LocalIngestion.recognizeText("   \n\t  ") is LocalIngestion.Incoming.Invalid)
    }

    @Test
    fun bareUrlRecognizedAsLinkCandidate() {
        val r = LocalIngestion.recognizeText("https://example.com/a?b=c")
        assertTrue(r is LocalIngestion.Incoming.Text)
        assertEquals("https://example.com/a?b=c", (r as LocalIngestion.Incoming.Text).url)
        // Verbatim content preserved for hashing — no normalization on ingest.
        assertEquals("https://example.com/a?b=c", r.content)
    }

    @Test
    fun urlWithSurroundingWhitespaceKeepsVerbatimContent() {
        val r = LocalIngestion.recognizeText("  https://a.b  ") as LocalIngestion.Incoming.Text
        assertEquals("https://a.b", r.url)
        assertEquals("  https://a.b  ", r.content)
    }

    @Test
    fun embeddedUrlIsTextNotLink() {
        val r = LocalIngestion.recognizeText("check https://example.com out") as LocalIngestion.Incoming.Text
        assertNull(r.url)
    }

    @Test
    fun imageRecognitionRequiresAllowedMime() {
        assertTrue(
            LocalIngestion.recognizeImage("image/png", "a.png") is LocalIngestion.Incoming.Image,
        )
        assertTrue(
            LocalIngestion.recognizeImage("image/heic", "a.heic") is LocalIngestion.Incoming.Invalid,
        )
        assertTrue(
            LocalIngestion.recognizeImage(null, "a.png") is LocalIngestion.Incoming.Invalid,
        )
    }

    @Test
    fun failureReasonsAreBoundedCodes() {
        assertEquals("empty", LocalIngestion.failureReason(LocalVaultError.Empty()))
        assertEquals("text_too_large", LocalIngestion.failureReason(LocalVaultError.TextTooLarge()))
        assertEquals("image_too_large", LocalIngestion.failureReason(LocalVaultError.ImageTooLarge()))
        assertEquals("unsupported_mime", LocalIngestion.failureReason(LocalVaultError.UnsupportedImage()))
        assertEquals("image_unreadable", LocalIngestion.failureReason(LocalVaultError.ImageUnreadable()))
        assertEquals("io_error", LocalIngestion.failureReason(RuntimeException("x")))
        assertTrue(LocalIngestion.failureReason(LocalVaultError.Empty()).length <= LocalVaultPolicy.REASON_MAX_CHARS)
    }
}
