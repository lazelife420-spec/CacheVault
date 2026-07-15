package com.prooffoundry.cachevaultmobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UserMessagesTest {
    @Test
    fun disabledShowsMobileAccessOff() {
        val msg = UserMessages.forBridgeError(BridgeError.Disabled())
        assertTrue(msg.contains("Mobile Access is off"))
    }

    @Test
    fun revokedShowsDeviceRevoked() {
        val msg = UserMessages.forBridgeError(BridgeError.Unauthorized("Device revoked."))
        assertTrue(msg.contains("Device revoked"))
    }

    @Test
    fun invalidRememberedTokenShowsRepairRequiredNotPairingCodeCopy() {
        val msg = UserMessages.forBridgeError(BridgeError.Unauthorized("Invalid device token."))
        assertTrue(msg.contains("no longer trusts this phone"))
        assertTrue(msg.contains("Re-pair to continue"))
        assertFalse(msg.contains("pairing code was rejected"))
    }

    @Test
    fun networkShowsWifiHint() {
        val msg = UserMessages.forBridgeError(BridgeError.Network(Exception("timeout")))
        assertTrue(msg.contains("same Wi-Fi"))
        assertTrue(msg.contains("Firewall"))
    }

    @Test
    fun unsupportedApiVersion() {
        val msg = UserMessages.forBridgeError(BridgeError.UnsupportedApi("99"))
        assertTrue(msg.contains("cannot talk"))
    }

    @Test
    fun updateRequiredShowsMinimumVersionNotGenericNetworkFailure() {
        val msg = UserMessages.forBridgeError(
            BridgeError.UpdateRequired(
                clientProtocol = 0,
                serverProtocolMin = 1,
                serverProtocolMax = 1,
                minimumMobileVersion = "0.1.5",
                serverMessage = null,
            ),
        )
        assertTrue(msg.contains("Update required"))
        assertTrue(msg.contains("no longer compatible"))
        assertTrue(msg.contains("0.1.5"))
        assertFalse(msg.contains("same Wi-Fi"))
        assertFalse(msg.contains("Firewall"))
    }

    @Test
    fun minimumVersionDisplayedCorrectlyWhenMissing() {
        val msg = UserMessages.updateRequired(null)
        assertTrue(msg.contains("Update required"))
        assertFalse(msg.contains("null"))
    }

    @Test
    fun trustedUpdateUrlIsHttpsOnTheCacheVaultLandingPage() {
        val uri = java.net.URI(UserMessages.TRUSTED_UPDATE_URL)
        assertEquals("https", uri.scheme)
        // Exact host match — a lookalike domain merely containing this
        // substring (e.g. "cache-vault-landing.pages.dev.evil.example")
        // must not pass.
        assertEquals("cache-vault-landing.pages.dev", uri.host)
        assertEquals("mobile-download", uri.fragment)
    }
}
