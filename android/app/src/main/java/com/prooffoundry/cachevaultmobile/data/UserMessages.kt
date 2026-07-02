package com.prooffoundry.cachevaultmobile.data

/** Plain-language errors — no stack traces, no fake claims. */
object UserMessages {
    const val SUPPORTED_API_VERSION = "1"

    const val PC_UNREACHABLE =
        "Cannot reach your PC.\nMake sure your phone and PC are on the same Wi-Fi."

    const val MOBILE_ACCESS_OFF =
        "Mobile Access is off.\nTurn it on in Cache Vault on your PC."

    const val PAIRING_FAILED =
        "Could not connect.\nCheck the PC address, port, device ID, and pairing code."

    const val DEVICE_REVOKED =
        "Device revoked.\nThis phone no longer has access. Pair again from your PC."

    const val FIREWALL_HINT =
        "Firewall may be blocking access.\nAllow Cache Vault on private networks."

    const val UNSUPPORTED_API =
        "This app version cannot talk to your PC.\nUpdate Cache Vault Mobile or your PC app."

    const val NOT_FOUND = "That clip was not found on your PC."

    const val IMAGE_NOT_AVAILABLE =
        "This screenshot is not available on your PC.\nIt may not have been saved as an image asset."

    const val REPAIR_NEEDED =
        "This PC no longer trusts this phone.\nRe-pair to continue."

    const val PAIRING_SAVED = "Saved — connected to PC"

    const val PC_FOUND_SECURE =
        "Local vault detected on this Wi-Fi."

    fun forBridgeError(error: BridgeError): String = when (error) {
        is BridgeError.Disabled -> MOBILE_ACCESS_OFF
        is BridgeError.Unauthorized -> when {
            error.message?.contains("revoked", ignoreCase = true) == true -> DEVICE_REVOKED
            error.message?.contains("token", ignoreCase = true) == true -> REPAIR_NEEDED
            else -> PAIRING_FAILED
        }
        is BridgeError.UnsupportedApi -> UNSUPPORTED_API
        is BridgeError.Network -> "$PC_UNREACHABLE\n\n$FIREWALL_HINT"
        is BridgeError.NotFound -> NOT_FOUND
        is BridgeError.AssetNotAvailable -> error.message ?: IMAGE_NOT_AVAILABLE
        is BridgeError -> error.message ?: PC_UNREACHABLE
    }
}
