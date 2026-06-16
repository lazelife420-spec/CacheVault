package com.prooffoundry.cachevaultmobile.connect

import com.prooffoundry.cachevaultmobile.data.BridgeError

/** Foreground-only PC discovery offer — no silent auto-connect. */
enum class PcOfferMode {
    /** Stored token exists — user may tap Connect. */
    PAIRED_TRY_CONNECT,
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
)

object ConnectionPlanner {
    fun offerMode(hasStoredPairing: Boolean, lastError: BridgeError?): PcOfferMode {
        if (!hasStoredPairing) return PcOfferMode.NO_TOKEN
        if (lastError is BridgeError.Unauthorized) return PcOfferMode.REPAIR_NEEDED
        return PcOfferMode.PAIRED_TRY_CONNECT
    }

    fun isRepairNeeded(error: Throwable?): Boolean =
        error is BridgeError.Unauthorized
}
