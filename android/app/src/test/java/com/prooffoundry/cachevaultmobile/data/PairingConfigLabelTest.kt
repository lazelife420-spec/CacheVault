package com.prooffoundry.cachevaultmobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingConfigLabelTest {
    @Test
    fun sanitizeKeepsOptionalPcLabel() {
        val config = PairingConfig.sanitize(
            host = "192.168.0.11",
            port = 8742,
            deviceId = "phone-1",
            token = "abc123",
            pcLabel = "Office PC",
        )
        assertEquals("Office PC", config.pcLabel)
    }

    @Test
    fun sanitizeTrimsPcLabel() {
        val config = PairingConfig.sanitize(
            host = "192.168.0.11",
            port = 8742,
            deviceId = "phone-1",
            token = "abc123",
            pcLabel = "  Kitchen PC  ",
        )
        assertEquals("Kitchen PC", config.pcLabel)
    }

    @Test
    fun sanitizePreservesReconnectPreferences() {
        val config = PairingConfig.sanitize(
            host = "192.168.0.11",
            port = 8742,
            deviceId = "phone-1",
            token = "abc123",
            pcLabel = "Kitchen PC",
            lastSeenAt = "2026-07-01T01:02:03Z",
            autoConnectApproved = true,
            keepConnectedInBackground = true,
        )
        assertEquals("2026-07-01T01:02:03Z", config.lastSeenAt)
        assertTrue(config.autoConnectApproved)
        assertTrue(config.keepConnectedInBackground)
    }

    @Test
    fun pairingFailedUsesPlainCouldNotConnect() {
        assertTrue(UserMessages.PAIRING_FAILED.startsWith("Could not connect"))
    }
}
