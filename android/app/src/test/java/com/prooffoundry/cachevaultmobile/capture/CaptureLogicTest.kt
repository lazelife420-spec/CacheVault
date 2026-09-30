package com.prooffoundry.cachevaultmobile.capture

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CaptureLogicTest {

    @Test
    fun screenshotFilter_matchesConventionalLocations() {
        assertTrue(
            ScreenshotImport.looksLikeScreenshot(
                path = "Pictures/Screenshots/",
                displayName = "Screenshot_20260929.png",
            ),
        )
        assertTrue(
            ScreenshotImport.looksLikeScreenshot(
                path = "DCIM/Screenshots",
                displayName = "IMG_2026.png",
            ),
        )
        assertTrue(
            ScreenshotImport.looksLikeScreenshot(
                path = "Pictures",
                displayName = "Screenshot_20260929_233012.png",
            ),
        )
        assertTrue(
            ScreenshotImport.looksLikeScreenshot(
                path = "Pictures/Screenshots",
                displayName = "shot.png",
            ),
        )
    }

    @Test
    fun screenshotFilter_rejectsNonScreenshots() {
        assertFalse(
            ScreenshotImport.looksLikeScreenshot(
                path = "DCIM/Camera/",
                displayName = "IMG_20260929.jpg",
            ),
        )
        assertFalse(
            ScreenshotImport.looksLikeScreenshot(
                path = "Pictures/",
                displayName = "photo.png",
            ),
        )
        assertFalse(ScreenshotImport.looksLikeScreenshot(path = null, displayName = null))
        assertFalse(
            ScreenshotImport.looksLikeScreenshot(
                path = "Download/",
                displayName = "not_a_screenshot.txt",
            ),
        )
    }

    @Test
    fun echo_marksAndMatchesWithinWindow() {
        val content = "user copied this from the vault"
        ClipboardEcho.mark(content, nowMs = 1_000L)
        assertTrue(ClipboardEcho.isEcho(content, nowMs = 5_000L))
    }

    @Test
    fun echo_rejectsDifferentContent() {
        ClipboardEcho.mark("original", nowMs = 1_000L)
        assertFalse(ClipboardEcho.isEcho("something else", nowMs = 2_000L))
    }

    @Test
    fun echo_expiresAfterWindow() {
        val content = "stale echo"
        ClipboardEcho.mark(content, nowMs = 1_000L)
        assertFalse(ClipboardEcho.isEcho(content, nowMs = 1_000L + 31_000L))
    }

    @Test
    fun markedRecently_onlyWithinShortWindow() {
        ClipboardEcho.mark("x", nowMs = 10_000L)
        assertTrue(ClipboardEcho.markedRecently(nowMs = 11_000L))
        assertFalse(ClipboardEcho.markedRecently(nowMs = 13_000L))
    }
}
