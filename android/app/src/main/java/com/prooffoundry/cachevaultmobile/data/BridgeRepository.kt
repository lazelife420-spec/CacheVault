package com.prooffoundry.cachevaultmobile.data

import android.content.Context
import android.os.Build
import com.prooffoundry.cachevaultmobile.connect.ConnectionPlanner
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcDiscovery
import java.time.Instant
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.withContext

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

    suspend fun discoverAndSelfHealEndpoint(): PairingConfig? {
        val current = pairingStore.load() ?: return null
        var candidateHost: String? = null
        var candidatePort = current.port
        var candidateLabel = current.pcLabel

        val pc = discoverPc()
        if (pc != null && PairingSanitize.isUsableHost(pc.host)) {
            candidateHost = pc.host
            candidatePort = pc.port
            if (pc.displayName.isNotBlank()) candidateLabel = pc.displayName
        }

        if (candidateHost == null && appContext != null) {
            candidateHost = findPcOnSubnet(appContext, candidatePort)
        }

        if (candidateHost == null) return null

        val updated = current.copy(
            host = candidateHost,
            port = candidatePort,
            pcLabel = candidateLabel,
        )
        val verified = runCatching { verifyConnection(updated) }.getOrNull()
        if (verified != null) {
            savePairing(updated)
            return updated
        }
        return null
    }

    private suspend fun findPcOnSubnet(context: Context, port: Int): String? = withContext(Dispatchers.IO) {
        val prefixes = getActiveIpPrefixes(context)
        val candidates = prefixes.flatMap { prefix -> (1..254).map { "$prefix.$it" } }
        kotlinx.coroutines.coroutineScope {
            val jobs = candidates.map { host ->
                async {
                    try {
                        java.net.Socket().use { s ->
                            s.connect(java.net.InetSocketAddress(host, port), 250)
                            host
                        }
                    } catch (_: Exception) { null }
                }
            }
            for (job in jobs) {
                val res = job.await()
                if (res != null) return@coroutineScope res
            }
            null
        }
    }

    private fun getActiveIpPrefixes(context: Context): List<String> {
        val prefixes = mutableListOf<String>()
        val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? android.net.wifi.WifiManager
        val dhcp = wifiManager?.dhcpInfo
        if (dhcp != null && dhcp.gateway != 0) {
            val gw = dhcp.gateway
            prefixes.add(String.format("%d.%d.%d", (gw and 0xff), (gw shr 8 and 0xff), (gw shr 16 and 0xff)))
        }
        runCatching {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces() ?: return@runCatching
            for (iface in interfaces) {
                if (!iface.isUp || iface.isLoopback) continue
                for (addr in iface.inetAddresses) {
                    if (!addr.isLoopbackAddress && addr is java.net.Inet4Address) {
                        val hostAddr = addr.hostAddress ?: continue
                        val parts = hostAddr.split(".")
                        if (parts.size == 4) {
                            val prefix = "${parts[0]}.${parts[1]}.${parts[2]}"
                            if (!prefixes.contains(prefix)) {
                                prefixes.add(prefix)
                            }
                        }
                    }
                }
            }
        }
        if (prefixes.isEmpty()) prefixes.add("192.168.0")
        return prefixes.distinct()
    }
}
