package com.prooffoundry.cachevaultmobile.data

import android.content.Context
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcDiscovery

class BridgeRepository(
    private val pairingStore: PairingStore,
    private val discoveryFactory: (Context) -> PcDiscovery = { PcDiscovery(it) },
    private val appContext: Context? = null,
) {
    fun isPaired(): Boolean = pairingStore.isPaired()

    fun loadPairing(): PairingConfig? = pairingStore.load()

    fun savePairing(config: PairingConfig) {
        pairingStore.save(config)
    }

    fun disconnect() {
        pairingStore.clear()
    }

    fun client(): BridgeClient {
        val config = pairingStore.load()
            ?: throw BridgeError.Unauthorized("Not paired.")
        return BridgeClient(config)
    }

    suspend fun verifyConnection(config: PairingConfig): BridgeStatus {
        val status = BridgeClient(config).status()
        pairingStore.save(config.copy(pcLabel = status.product))
        return status
    }

    suspend fun discoverPc(): DiscoveredPc? {
        val ctx = appContext ?: return null
        return discoveryFactory(ctx.applicationContext).findDesktop()
    }
}
