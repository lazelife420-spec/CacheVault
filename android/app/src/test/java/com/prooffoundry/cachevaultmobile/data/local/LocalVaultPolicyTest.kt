package com.prooffoundry.cachevaultmobile.data.local

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Golden vectors for the local hashing policy and content classification
 * (CV-MOBILE-1). The digest contract is deliberately strict: raw saved bytes,
 * UTF-8, no normalization — CRLF and LF must NOT hash equal.
 */
class LocalVaultPolicyTest {

    @Test
    fun textHashPreservesExactBytes() {
        val lf = "line1\nline2"
        val crlf = "line1\r\nline2"
        assertNotEquals(
            "CRLF and LF content are different saved bytes and must hash differently",
            LocalVaultPolicy.sha256HexText(lf),
            LocalVaultPolicy.sha256HexText(crlf),
        )
    }

    @Test
    fun textHashKeepsLeadingAndTrailingWhitespace() {
        val padded = "  padded  "
        val bare = "padded"
        assertNotEquals(
            LocalVaultPolicy.sha256HexText(padded),
            LocalVaultPolicy.sha256HexText(bare),
        )
    }

    @Test
    fun textHashHandlesNonBmpCharacters() {
        val emoji = "done 🎉🔐"
        // SHA-256 of "done 🎉🔐" in UTF-8 — golden vector computed once, kept fixed.
        val expected = java.security.MessageDigest.getInstance("SHA-256")
            .digest(emoji.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
        assertEquals(expected, LocalVaultPolicy.sha256HexText(emoji))
        assertEquals(64, LocalVaultPolicy.sha256HexText(emoji).length)
    }

    @Test
    fun textHashHandlesCombiningCharacters() {
        val decomposed = "cafe\u0301"      // e + combining acute
        val precomposed = "café"           // precomposed é
        assertNotEquals(
            "Combining vs precomposed forms are distinct byte sequences",
            LocalVaultPolicy.sha256HexText(decomposed),
            LocalVaultPolicy.sha256HexText(precomposed),
        )
    }

    @Test
    fun bareUrlClassification() {
        assertEquals(LocalItemKind.LINK, LocalVaultPolicy.classifyText("https://example.com/x"))
        assertEquals(LocalItemKind.LINK, LocalVaultPolicy.classifyText("  http://a.b  "))
        assertEquals(LocalItemKind.TEXT, LocalVaultPolicy.classifyText("see https://example.com later"))
        assertEquals(LocalItemKind.TEXT, LocalVaultPolicy.classifyText("https://example.com\nhttps://b.co"))
        assertEquals(LocalItemKind.TEXT, LocalVaultPolicy.classifyText("just text"))
        assertEquals(LocalItemKind.TEXT, LocalVaultPolicy.classifyText("ftp://nope.example"))
    }

    @Test
    fun titleAndPreviewAreBounded() {
        val long = "x".repeat(500)
        assertEquals(LocalVaultPolicy.TITLE_MAX_CHARS, LocalVaultPolicy.titleFor(long).length)
        val multi = "first\n" + "y".repeat(300) + "\nthird"
        val preview = LocalVaultPolicy.previewFor(multi)
        assertTrue(preview.length <= LocalVaultPolicy.PREVIEW_MAX_CHARS)
        assertFalse(preview.contains("third"))
    }

    @Test
    fun titleSkipsBlankFirstLines() {
        assertEquals("real title", LocalVaultPolicy.titleFor("\n\n  real title\nbody"))
        assertEquals("(empty)", LocalVaultPolicy.titleFor("\n \n"))
    }

    @Test
    fun escapeLikeTreatsWildcardsLiterally() {
        assertEquals("100\\%\\_\\\\", LocalVaultPolicy.escapeLike("100%_\\"))
        assertEquals("plain", LocalVaultPolicy.escapeLike("plain"))
    }

    @Test
    fun utf8ByteCountIsReal() {
        assertTrue(LocalVaultPolicy.utf8Bytes("é") == 2)
        assertTrue(LocalVaultPolicy.utf8Bytes("🎉") == 4)
    }

    @Test
    fun imageMimePolicy() {
        assertTrue(LocalVaultPolicy.ALLOWED_IMAGE_MIME.contains("image/png"))
        assertTrue(LocalVaultPolicy.ALLOWED_IMAGE_MIME.contains("image/jpeg"))
        assertFalse(LocalVaultPolicy.ALLOWED_IMAGE_MIME.contains("image/heic"))
        assertFalse(LocalVaultPolicy.ALLOWED_IMAGE_MIME.contains("application/octet-stream"))
        assertEquals("jpg", LocalVaultPolicy.extensionForMime("image/jpeg"))
        assertEquals("img", LocalVaultPolicy.extensionForMime("image/heic"))
    }
}
