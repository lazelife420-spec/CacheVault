package com.prooffoundry.cachevaultmobile.data

import android.content.Context
import android.os.Build
import com.prooffoundry.cachevaultmobile.connect.ConnectionPlanner
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcDiscovery
import java.time.Instant

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

    fun updateConnectionPreferences(
        autoConnectApproved: Boolean? = null,
        keepConnectedInBackground: Boolean? = null,
    ) {
        val current = pairingStore.load() ?: return
        pairingStore.save(
            current.copy(
                autoConnectApproved = autoConnectApproved ?: current.autoConnectApproved,
                keepConnectedInBackground = keepConnectedInBackground
                    ?: current.keepConnectedInBackground,
            ),
        )
    }

    fun updatePairingHost(host: String, port: Int, displayName: String? = null) {
        val current = pairingStore.load() ?: return
        pairingStore.save(
            current.copy(
                host = PairingSanitize.sanitizeHost(host),
                port = port,
                pcLabel = displayName?.trim().orEmpty().ifBlank { current.pcLabel },
            ),
        )
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
        pairingStore.save(
            config.copy(
                pcLabel = config.pcLabel.ifBlank { status.product.ifBlank { config.host } },
                lastSeenAt = Instant.now().toString(),
            ),
        )
        return status
    }

    suspend fun pairDiscoveredPc(
        host: String,
        port: Int,
        displayName: String,
    ): BridgeStatus {
        val client = BridgeClient(
            PairingConfig(
                host = host,
                port = port,
                deviceId = "",
                token = "",
            ),
        )
        val existingDeviceId = ConnectionPlanner.deviceIdForPairing(pairingStore.load()?.deviceId)
        val grant = if (existingDeviceId != null) {
            client.pairDevice(
                deviceName = Build.MODEL, deviceId = existingDeviceId, deviceModel = Build.MODEL,
            )
        } else {
            client.pairDevice(deviceName = Build.MODEL, deviceModel = Build.MODEL)
        }
        val config = PairingConfig.sanitize(
            host = host,
            port = port,
            deviceId = grant.deviceId,
            token = grant.token,
            pcLabel = displayName,
        )
        return verifyConnection(config)
    }

    suspend fun discoverPc(): DiscoveredPc? {
        val ctx = appContext ?: return null
        return discoveryFactory(ctx.applicationContext).findDesktop()
    }
}
