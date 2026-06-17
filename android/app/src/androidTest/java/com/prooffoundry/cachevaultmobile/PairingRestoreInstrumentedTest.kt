package com.prooffoundry.cachevaultmobile

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingConfig
import com.prooffoundry.cachevaultmobile.data.PairingStore
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Push fresh PC pairing credentials onto the phone (used after smoke / revoke recovery). */
@RunWith(AndroidJUnit4::class)
class PairingRestoreInstrumentedTest {

    @Test
    fun restorePhonePairing() {
        val args = InstrumentationRegistry.getArguments()
        val host = args.getString("host") ?: error("Missing -e host")
        val port = args.getString("port")?.toIntOrNull() ?: 8742
        val deviceId = args.getString("device_id") ?: error("Missing -e device_id")
        val token = args.getString("token") ?: error("Missing -e token")

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val store = PairingStore(context)
        store.save(PairingConfig(host, port, deviceId, token, "Cache Vault PC"))

        val status = BridgeRepository(store).client().status()
        assertTrue(status.mobileAccessEnabled)
    }
}
