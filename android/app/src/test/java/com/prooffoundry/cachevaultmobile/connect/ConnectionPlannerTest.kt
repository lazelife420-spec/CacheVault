package com.prooffoundry.cachevaultmobile.connect

import com.prooffoundry.cachevaultmobile.data.BridgeError
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConnectionPlannerTest {
    @Test
    fun noStoredPairing_isNoToken() {
        assertEquals(PcOfferMode.NO_TOKEN, ConnectionPlanner.offerMode(false, null))
    }

    @Test
    fun storedPairing_withoutError_isTryConnect() {
        assertEquals(PcOfferMode.PAIRED_TRY_CONNECT, ConnectionPlanner.offerMode(true, null))
    }

    @Test
    fun unauthorized_isRepairNeeded() {
        val err = BridgeError.Unauthorized("Invalid device token.")
        assertEquals(PcOfferMode.REPAIR_NEEDED, ConnectionPlanner.offerMode(true, err))
        assertTrue(ConnectionPlanner.isRepairNeeded(err))
    }

    @Test
    fun networkError_isNotRepair() {
        val err = BridgeError.Network(IllegalStateException("timeout"))
        assertFalse(ConnectionPlanner.isRepairNeeded(err))
    }
}
