package com.prooffoundry.cachevaultmobile.data

class BridgeRepository(
    private val pairingStore: PairingStore,
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
}
