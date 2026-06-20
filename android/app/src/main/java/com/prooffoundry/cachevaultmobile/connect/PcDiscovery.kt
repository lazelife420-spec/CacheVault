package com.prooffoundry.cachevaultmobile.connect

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class PcDiscovery(private val context: Context) {
    private val nsd = context.getSystemService(NsdManager::class.java)
    private val mainHandler = Handler(Looper.getMainLooper())

    suspend fun findDesktop(timeoutMs: Long = 8000L): DiscoveredPc? {
        if (nsd == null) return null
        return suspendCancellableCoroutine { cont ->
            var finished = false
            fun finish(value: DiscoveredPc?) {
                if (finished || cont.isCompleted) return
                finished = true
                cont.resume(value)
            }

            lateinit var discoveryListener: NsdManager.DiscoveryListener
            discoveryListener = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(serviceType: String) {}

                override fun onServiceFound(info: NsdServiceInfo) {
                    if (!info.serviceType.contains("_cachevault._tcp")) return
                    nsd.resolveService(info, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(s: NsdServiceInfo, code: Int) {}

                        override fun onServiceResolved(s: NsdServiceInfo) {
                            runCatching { nsd.stopServiceDiscovery(discoveryListener) }
                            val host = s.host?.hostAddress ?: return finish(null)
                            val port = if (s.port > 0) s.port else DEFAULT_PORT
                            val display = s.serviceName
                                ?.substringBefore('.')
                                ?.ifBlank { "Cache Vault Desktop" }
                                ?: "Cache Vault Desktop"
                            finish(DiscoveredPc(display, host, port))
                        }
                    })
                }

                override fun onServiceLost(info: NsdServiceInfo) {}
                override fun onDiscoveryStopped(serviceType: String) {
                    finish(null)
                }

                override fun onStartDiscoveryFailed(serviceType: String, code: Int) {
                    finish(null)
                }

                override fun onStopDiscoveryFailed(serviceType: String, code: Int) {}
            }

            cont.invokeOnCancellation {
                runCatching { nsd.stopServiceDiscovery(discoveryListener) }
            }
            nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discoveryListener)
            mainHandler.postDelayed({
                runCatching { nsd.stopServiceDiscovery(discoveryListener) }
                finish(null)
            }, timeoutMs)
        }
    }

    companion object {
        const val SERVICE_TYPE = "_cachevault._tcp."
        const val DEFAULT_PORT = 8742
    }
}
