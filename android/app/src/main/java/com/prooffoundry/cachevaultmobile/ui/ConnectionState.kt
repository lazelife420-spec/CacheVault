package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.BridgeStatus

/** Truthful connection badge — never show Connected without a live status check. */
enum class ConnectionState(val label: String) {
    CONNECTED("Connected"),
    REPAIR_NEEDED("Re-pair needed"),
    REVOKED("Device revoked"),
    OFFLINE("Not connected"),
    MOBILE_ACCESS_OFF("Mobile Access off"),
    VAULT_LOCKED("Vault locked"),
    UPDATE_REQUIRED("Update required"),
    CHECKING("Loading…"),
}

fun resolveConnectionState(
    status: BridgeStatus?,
    error: String?,
    loading: Boolean,
    hasLoadedVault: Boolean = true,
): ConnectionState {
    val connError = connectionOnlyError(error)
    if (loading || (!hasLoadedVault && status == null && connError.isNullOrBlank())) {
        return ConnectionState.CHECKING
    }
    // Checked before "revoked"/token substrings below: an incompatible client
    // must never be shown as merely needing re-pair, since re-pairing alone
    // cannot fix it — the app itself must be updated.
    if (connError?.contains("no longer compatible", ignoreCase = true) == true) {
        return ConnectionState.UPDATE_REQUIRED
    }
    if (connError?.contains("revoked", ignoreCase = true) == true) return ConnectionState.REVOKED
    if (connError?.contains("Mobile Access is off", ignoreCase = true) == true) {
        return ConnectionState.MOBILE_ACCESS_OFF
    }
    if (connError?.contains("Vault is locked", ignoreCase = true) == true) {
        return ConnectionState.VAULT_LOCKED
    }
    if (status != null && connError.isNullOrBlank()) return ConnectionState.CONNECTED
    if (connError?.contains("token", ignoreCase = true) == true ||
        connError?.contains("Pairing", ignoreCase = true) == true ||
        connError?.contains("Re-pair", ignoreCase = true) == true
    ) {
        return ConnectionState.REPAIR_NEEDED
    }
    if (!connError.isNullOrBlank()) return ConnectionState.OFFLINE
    if (!hasLoadedVault) return ConnectionState.CHECKING
    return ConnectionState.CHECKING
}

/** Ignore clip-detail errors when resolving vault connection state. */
fun connectionOnlyError(error: String?): String? {
    if (error.isNullOrBlank()) return null
    if (error.contains("not found", ignoreCase = true) &&
        error.contains("clip", ignoreCase = true)
    ) {
        return null
    }
    return error
}

fun connectionSubtitle(state: ConnectionState, hostLabel: String): String = when (state) {
    ConnectionState.CONNECTED -> "Connected · ${hostLabel.ifBlank { "PC" }}"
    ConnectionState.REPAIR_NEEDED -> "Re-pair needed — get a fresh code on your PC"
    ConnectionState.REVOKED -> "Device revoked — pair again on your PC"
    ConnectionState.OFFLINE -> "Not connected — same Wi-Fi, PC app open, then Retry"
    ConnectionState.MOBILE_ACCESS_OFF -> "Mobile Access off on your PC"
    ConnectionState.VAULT_LOCKED -> "Vault is locked on your PC"
    ConnectionState.UPDATE_REQUIRED -> "Update required — this app version is no longer supported"
    ConnectionState.CHECKING -> "Checking connection…"
}
