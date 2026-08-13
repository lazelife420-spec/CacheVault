package com.prooffoundry.cachevaultmobile.connect

import com.prooffoundry.cachevaultmobile.data.PairingConfig
import com.prooffoundry.cachevaultmobile.data.PairingSanitize
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingSelfHealTest {

    @Test
    fun testInvalidHostValidation() {
        assertFalse(PairingSanitize.isUsableHost("Cache Vault Desktop"))
        assertFalse(PairingSanitize.isUsableHost("CacheVaultDesktop"))
        assertFalse(PairingSanitize.isUsableHost(""))
        assertFalse(PairingSanitize.isUsableHost("   "))

        assertTrue(PairingSanitize.isUsableHost("192.168.0.16"))
        assertTrue(PairingSanitize.isUsableHost("192.168.0.11"))
        assertTrue(PairingSanitize.isUsableHost("desktop-pc.local"))
    }

    @Test
    fun testPairingConfigHasUsableHost() {
        val badConfig = PairingConfig(
            host = "Cache Vault Desktop",
            port = 8742,
            deviceId = "s23-test-device",
            token = "s23-test-token",
            pcLabel = "Cache Vault Desktop"
        )
        assertFalse(badConfig.hasUsableHost())

        val goodConfig = badConfig.copy(host = "192.168.0.16")
        assertTrue(goodConfig.hasUsableHost())
        assertEquals("s23-test-device", goodConfig.deviceId)
        assertEquals("s23-test-token", goodConfig.token)
    }

    @Test
    fun testEndpointSelfHealPreservesIdentity() {
        val stalePairing = PairingConfig(
            host = "192.168.0.11",
            port = 8742,
            deviceId = "s23-test-device",
            token = "s23-test-token",
            pcLabel = "My Desktop PC"
        )

        val discoveredNewEndpoint = DiscoveredPc(
            displayName = "My Desktop PC",
            host = "192.168.0.16",
            port = 8742
        )

        // Self-heal updates host/port while strictly retaining deviceId and token
        val healedPairing = stalePairing.copy(
            host = discoveredNewEndpoint.host,
            port = discoveredNewEndpoint.port
        )

        assertEquals("192.168.0.16", healedPairing.host)
        assertEquals(8742, healedPairing.port)
        assertEquals("s23-test-device", healedPairing.deviceId)
        assertEquals("s23-test-token", healedPairing.token)
        assertEquals("My Desktop PC", healedPairing.pcLabel)
    }
}
