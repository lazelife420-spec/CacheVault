package com.prooffoundry.cachevaultmobile.data

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
}
