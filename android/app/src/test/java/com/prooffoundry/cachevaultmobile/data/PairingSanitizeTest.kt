package com.prooffoundry.cachevaultmobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class PairingSanitizeTest {
    @Test
    fun token_strips_newlines_from_multiline_paste() {
        val raw = "T1amK1-uQxWc1\n"
        assertEquals("T1amK1-uQxWc1", PairingSanitize.sanitizeToken(raw))
    }

    @Test
    fun device_id_strips_whitespace() {
        assertEquals("pixel-live", PairingSanitize.sanitizeDeviceId(" pixel-live \n"))
    }

    @Test
    fun host_strips_whitespace() {
        assertEquals("192.168.0.11", PairingSanitize.sanitizeHost("192.168.0.11\n"))
    }
}
