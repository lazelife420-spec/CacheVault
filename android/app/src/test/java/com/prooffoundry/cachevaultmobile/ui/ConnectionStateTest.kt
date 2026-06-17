package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class ConnectionStateTest {

    private fun status() = BridgeStatus(
        product = "Cache Vault",
        byline = "",
        mobileApiVersion = "1",
        mobileAccessEnabled = true,
        cacheVaultVersion = "0.1",
        deviceId = "pixel-live",
        readOnly = true,
    )

    @Test
    fun loadingBeforeFirstFetchShowsCheckingNotOffline() {
        assertEquals(
            ConnectionState.CHECKING,
            resolveConnectionState(status = null, error = null, loading = true, hasLoadedVault = false),
        )
    }

    @Test
    fun notConnectedOnlyAfterRealFailure() {
        assertEquals(
            ConnectionState.OFFLINE,
            resolveConnectionState(status = null, error = "Cannot reach PC", loading = false, hasLoadedVault = true),
        )
    }

    @Test
    fun clipNotFoundErrorDoesNotAffectConnection() {
        assertEquals(
            ConnectionState.CONNECTED,
            resolveConnectionState(
                status = status(),
                error = "That clip was not found on your PC.",
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }

    @Test
    fun imagesTabLabelIsShort() {
        assertEquals("Images", MainTab.IMAGES.label)
    }

    @Test
    fun connectedAfterSuccessfulLoad() {
        assertEquals(
            ConnectionState.CONNECTED,
            resolveConnectionState(status = status(), error = null, loading = false, hasLoadedVault = true),
        )
    }
}
