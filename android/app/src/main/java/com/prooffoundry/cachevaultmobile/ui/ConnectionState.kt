package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BridgeStatus

/** Truthful connection badge — never show Connected without a live status check. */
enum class ConnectionState(val label: String) {
    CONNECTED("Connected"),
    REPAIR_NEEDED("Re-pair needed"),
    REVOKED("Device revoked"),
    OFFLINE("Not connected"),
    MOBILE_ACCESS_OFF("Mobile Access off"),
    CHECKING("Checking PC…"),
}

fun resolveConnectionState(
    status: BridgeStatus?,
    error: String?,
    loading: Boolean,
): ConnectionState {
    if (loading && status == null && error.isNullOrBlank()) return ConnectionState.CHECKING
    if (error?.contains("revoked", ignoreCase = true) == true) return ConnectionState.REVOKED
    if (error?.contains("Mobile Access is off", ignoreCase = true) == true) {
        return ConnectionState.MOBILE_ACCESS_OFF
    }
    if (status != null && error.isNullOrBlank()) return ConnectionState.CONNECTED
    if (error?.contains("token", ignoreCase = true) == true ||
        error?.contains("Pairing", ignoreCase = true) == true ||
        error?.contains("Re-pair", ignoreCase = true) == true
    ) {
        return ConnectionState.REPAIR_NEEDED
    }
    if (!error.isNullOrBlank()) return ConnectionState.OFFLINE
    return ConnectionState.CHECKING
}

fun connectionSubtitle(state: ConnectionState, hostLabel: String): String = when (state) {
    ConnectionState.CONNECTED -> "Connected · ${hostLabel.ifBlank { "PC" }}"
    ConnectionState.REPAIR_NEEDED -> "Re-pair needed"
    ConnectionState.REVOKED -> "Device revoked — pair again on PC"
    ConnectionState.OFFLINE -> "Not connected"
    ConnectionState.MOBILE_ACCESS_OFF -> "Mobile Access off on PC"
    ConnectionState.CHECKING -> "Checking PC…"
}
