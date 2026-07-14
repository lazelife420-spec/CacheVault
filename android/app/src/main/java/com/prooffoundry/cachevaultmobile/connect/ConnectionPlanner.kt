package com.prooffoundry.cachevaultmobile.connect

import com.prooffoundry.cachevaultmobile.data.BridgeError

enum class PcOfferMode {
    /** Stored token exists but user approval is still required. */
    APPROVAL_REQUIRED,
    /** Stored token exists and the user trusted silent reconnect. */
    AUTO_CONNECT_READY,
    /** Stored token was rejected — re-pair required. */
    REPAIR_NEEDED,
    /** PC found but phone has no pairing for it. */
    NO_TOKEN,
}

data class PcFoundOffer(
    val displayName: String,
    val host: String,
    val port: Int,
    val mode: PcOfferMode,
    val remembered: Boolean = false,
)

object ConnectionPlanner {
    fun offerMode(
        hasStoredPairing: Boolean,
        lastError: BridgeError?,
        autoConnectApproved: Boolean = false,
    ): PcOfferMode {
        if (!hasStoredPairing) return PcOfferMode.NO_TOKEN
        if (lastError is BridgeError.Unauthorized) return PcOfferMode.REPAIR_NEEDED
        return if (autoConnectApproved) {
            PcOfferMode.AUTO_CONNECT_READY
        } else {
            PcOfferMode.APPROVAL_REQUIRED
        }
    }

    fun isRepairNeeded(error: Throwable?): Boolean =
        error is BridgeError.Unauthorized

    /**
     * Device identity to send when (re-)pairing with a PC.
     *
     * Reuses the phone's remembered device_id when one exists so the desktop
     * refreshes the credential for the same logical device instead of minting
     * a brand-new identity (and orphaning the old, still-active record) on
     * every Re-pair tap.
     */
    fun deviceIdForPairing(existingDeviceId: String?): String? =
        existingDeviceId?.takeIf { it.isNotBlank() }
}
