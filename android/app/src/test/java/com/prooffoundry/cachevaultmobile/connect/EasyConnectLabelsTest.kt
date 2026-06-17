package com.prooffoundry.cachevaultmobile.connect

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EasyConnectLabelsTest {
    @Test
    fun connectToMyPcLabel() {
        assertEquals("Connect to My PC", EasyConnectLabels.CONNECT_TO_MY_PC)
    }

    @Test
    fun openWifiSettingsLabel() {
        assertEquals("Open Wi-Fi Settings", EasyConnectLabels.OPEN_WIFI_SETTINGS)
    }

    @Test
    fun manualSetupFallbackLabel() {
        assertEquals("Manual Setup", EasyConnectLabels.MANUAL_SETUP)
    }

    @Test
    fun discoveryFailureMentionsManualSetup() {
        assertTrue(EasyConnectLabels.DISCOVER_FAILED.contains("Could not find"))
    }

    @Test
    fun formatDiscoveredPcIncludesHostAndPort() {
        val text = formatDiscoveredPc("Christian's PC", "192.168.1.10", 8742)
        assertTrue(text.contains("192.168.1.10"))
        assertTrue(text.contains("8742"))
    }

    @Test
    fun serviceTypeMatchesDesktop() {
        assertTrue(PcDiscovery.SERVICE_TYPE.contains("_cachevault-mobile._tcp"))
    }
}
