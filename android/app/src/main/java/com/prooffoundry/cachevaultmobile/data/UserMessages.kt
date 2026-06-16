package com.prooffoundry.cachevaultmobile.data

/** Plain-language errors — no stack traces, no fake claims. */
object UserMessages {
    const val SUPPORTED_API_VERSION = "1"

    const val PC_UNREACHABLE =
        "Cannot reach your PC.\nMake sure your phone and PC are on the same Wi-Fi."

    const val MOBILE_ACCESS_OFF =
        "Mobile Access is off.\nTurn it on in Cache Vault on your PC."

    const val PAIRING_FAILED =
        "Pairing failed.\nCheck the device ID and token, or pair again."

    const val DEVICE_REVOKED =
        "Device revoked.\nThis phone no longer has access. Pair again from your PC."

    const val FIREWALL_HINT =
        "Firewall may be blocking access.\nAllow Cache Vault on private networks."

    const val UNSUPPORTED_API =
        "This app version cannot talk to your PC.\nUpdate Cache Vault Mobile or your PC app."

    const val NOT_FOUND = "That clip was not found on your PC."

    fun forBridgeError(error: BridgeError): String = when (error) {
        is BridgeError.Disabled -> MOBILE_ACCESS_OFF
        is BridgeError.Unauthorized -> when {
            error.message?.contains("revoked", ignoreCase = true) == true -> DEVICE_REVOKED
            else -> PAIRING_FAILED
        }
        is BridgeError.UnsupportedApi -> UNSUPPORTED_API
        is BridgeError.Network -> "$PC_UNREACHABLE\n\n$FIREWALL_HINT"
        is BridgeError.NotFound -> NOT_FOUND
        is BridgeError -> error.message ?: PC_UNREACHABLE
    }
}
