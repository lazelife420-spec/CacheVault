package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import com.prooffoundry.cachevaultmobile.data.UserMessages
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

    @Test
    fun updateRequiredErrorResolvesToUpdateRequiredState() {
        assertEquals(
            ConnectionState.UPDATE_REQUIRED,
            resolveConnectionState(
                status = null,
                error = UserMessages.updateRequired("0.1.5"),
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }

    @Test
    fun updateRequiredIsNotConfusedWithRepairNeeded() {
        val state = resolveConnectionState(
            status = null,
            error = UserMessages.updateRequired("0.1.5"),
            loading = false,
            hasLoadedVault = true,
        )
        assertEquals(ConnectionState.UPDATE_REQUIRED, state)
        assert(state != ConnectionState.REPAIR_NEEDED)
    }

    @Test
    fun pairingResumesAfterCompatibleReconnect() {
        assertEquals(
            ConnectionState.UPDATE_REQUIRED,
            resolveConnectionState(
                status = null,
                error = UserMessages.updateRequired("0.1.5"),
                loading = false,
                hasLoadedVault = true,
            ),
        )
        assertEquals(
            ConnectionState.CONNECTED,
            resolveConnectionState(status = status(), error = null, loading = false, hasLoadedVault = true),
        )
    }

    // --- Regression coverage for the disabled-bridge state-machine fix ---
    //
    // AppViewModel.initializeConnectionLifecycle() previously left uiState in its
    // untouched initial shape (loading=false, hasLoadedVault=false, error=null)
    // whenever a manual reconnect's repository.discoverPc() returned null (bridge
    // off, unreachable, or timed out). resolveConnectionState reads that exact
    // shape as CHECKING, so a phone reconnecting against a disabled desktop bridge
    // got stuck showing "Checking…"/"Loading…" forever instead of resolving to
    // Offline, even though data access was already correctly blocked. The fix
    // makes the ViewModel explicitly set loading=false, hasLoadedVault=true, and a
    // non-blank error on discovery failure — these tests pin that state shape.

    @Test
    fun discoveryStillInFlightShowsCheckingNotOffline() {
        // The instant after initializeConnectionLifecycle() sets loading=true,
        // before repository.discoverPc() has resolved either way.
        assertEquals(
            ConnectionState.CHECKING,
            resolveConnectionState(status = null, error = null, loading = true, hasLoadedVault = false),
        )
    }

    @Test
    fun disabledBridgeAfterManualReconnectResolvesToOfflineNotChecking() {
        // Mirrors the state AppViewModel now sets when discoverPc() returns null:
        // loading=false, hasLoadedVault=true, status=null, error=PC_UNREACHABLE.
        assertEquals(
            ConnectionState.OFFLINE,
            resolveConnectionState(
                status = null,
                error = UserMessages.PC_UNREACHABLE,
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }

    @Test
    fun connectionTimeoutResolvesToOffline() {
        assertEquals(
            ConnectionState.OFFLINE,
            resolveConnectionState(
                status = null,
                error = "timeout",
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }

    @Test
    fun revokedDeviceResolvesToRevokedNotOffline() {
        assertEquals(
            ConnectionState.REVOKED,
            resolveConnectionState(
                status = null,
                error = UserMessages.DEVICE_REVOKED,
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }

    @Test
    fun rejectedTokenResolvesToRepairNeededNotOffline() {
        assertEquals(
            ConnectionState.REPAIR_NEEDED,
            resolveConnectionState(
                status = null,
                error = UserMessages.REPAIR_NEEDED,
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }

    @Test
    fun reenableAndReconnectReturnsToConnected() {
        val offline = resolveConnectionState(
            status = null,
            error = UserMessages.PC_UNREACHABLE,
            loading = false,
            hasLoadedVault = true,
        )
        assertEquals(ConnectionState.OFFLINE, offline)
        assertEquals(
            ConnectionState.CONNECTED,
            resolveConnectionState(status = status(), error = null, loading = false, hasLoadedVault = true),
        )
    }

    @Test
    fun genuineNetworkErrorIsNotSwallowedLikeClipNotFound() {
        // A real "could not send" bridge failure must still surface as Offline —
        // it must not be filtered the way the clip-detail 404 special case is
        // (see clipNotFoundErrorDoesNotAffectConnection above), which would let a
        // failed send look falsely connected.
        assertEquals(UserMessages.PC_UNREACHABLE, connectionOnlyError(UserMessages.PC_UNREACHABLE))
        assertEquals(
            ConnectionState.OFFLINE,
            resolveConnectionState(
                status = null,
                error = UserMessages.PC_UNREACHABLE,
                loading = false,
                hasLoadedVault = true,
            ),
        )
    }
}
