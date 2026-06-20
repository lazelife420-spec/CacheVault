package com.prooffoundry.cachevaultmobile.connect

/** User-facing Easy Connect labels (single source for tests). */
object EasyConnectLabels {
    const val CONNECT_TO_MY_PC = "Connect to Cache Vault on this PC"
    const val EASY_CONNECT = "Easy Connect"
    const val SCAN_QR_CODE = "Scan QR Code"
    const val FIND_PC_WIFI = "Find PC on this Wi-Fi"
    const val MANUAL_SETUP = "Manual Setup"
    const val OPEN_WIFI_SETTINGS = "Open Wi-Fi Settings"
    const val SAME_WIFI = "I'm on the same Wi-Fi — find my PC"
    const val DISCOVER_FAILED = "Could not find your PC"
}

data class DiscoveredPc(
    val displayName: String,
    val host: String,
    val port: Int,
)

fun formatDiscoveredPc(name: String, host: String, port: Int): String =
    "Found Cache Vault at $host:$port".let { base ->
        if (name.isNotBlank() && name != "PC") "$name — $base" else base
    }
