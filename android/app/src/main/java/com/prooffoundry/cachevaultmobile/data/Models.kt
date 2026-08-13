package com.prooffoundry.cachevaultmobile.data

data class PairingConfig(
    val host: String,
    val port: Int,
    val deviceId: String,
    val token: String,
    val pcLabel: String = "",
    val lastSeenAt: String? = null,
    val autoConnectApproved: Boolean = false,
    val keepConnectedInBackground: Boolean = false,
) {
    fun hasUsableHost(): Boolean = PairingSanitize.isUsableHost(host)

    companion object {
        fun sanitize(
            host: String,
            port: Int,
            deviceId: String,
            token: String,
            pcLabel: String = "",
            lastSeenAt: String? = null,
            autoConnectApproved: Boolean = false,
            keepConnectedInBackground: Boolean = false,
        ): PairingConfig = PairingConfig(
            host = sanitizeHost(host),
            port = port,
            deviceId = sanitizeDeviceId(deviceId),
            token = sanitizeToken(token),
            pcLabel = pcLabel.trim(),
            lastSeenAt = lastSeenAt?.trim()?.ifBlank { null },
            autoConnectApproved = autoConnectApproved,
            keepConnectedInBackground = keepConnectedInBackground,
        )
    }
}

/** Strip paste/newline noise from pairing fields before HTTP headers are built. */
object PairingSanitize {
    fun sanitizeHost(host: String): String =
        host.trim().replace(Regex("\\s+"), "")

    fun isUsableHost(host: String): Boolean {
        val trimmed = host.trim()
        if (trimmed.isBlank()) return false
        if (trimmed.contains(" ") || trimmed.contains("Cache Vault", ignoreCase = true)) return false
        if (!trimmed.contains(".") && !trimmed.contains(":")) return false
        if (trimmed.matches(Regex("^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$"))) return true
        if (trimmed.matches(Regex("^[a-zA-Z0-9.-]+$")) && !trimmed.startsWith("-")) return true
        return false
    }

    fun sanitizeDeviceId(deviceId: String): String =
        deviceId.trim().replace(Regex("\\s+"), "")

    fun sanitizeToken(token: String): String =
        token.trim().replace(Regex("\\s+"), "")
}

private fun sanitizeHost(host: String) = PairingSanitize.sanitizeHost(host)
private fun sanitizeDeviceId(deviceId: String) = PairingSanitize.sanitizeDeviceId(deviceId)
private fun sanitizeToken(token: String) = PairingSanitize.sanitizeToken(token)

data class BridgeStatus(
    val product: String,
    val byline: String,
    val mobileApiVersion: String,
    val mobileAccessEnabled: Boolean,
    val cacheVaultVersion: String,
    val deviceId: String,
    val readOnly: Boolean,
    val compatible: Boolean? = null,
    val serverProtocolMin: Int? = null,
    val serverProtocolMax: Int? = null,
    val minimumMobileVersion: String? = null,
    val updateRequired: Boolean = false,
)

data class PairDeviceGrant(
    val deviceId: String,
    val deviceName: String,
    val token: String,
    val compatible: Boolean? = null,
    val serverProtocolMin: Int? = null,
    val serverProtocolMax: Int? = null,
    val minimumMobileVersion: String? = null,
    val updateRequired: Boolean = false,
)

data class ClipSummary(
    val id: String,
    val preview: String,
    val content: String,
    val classification: String?,
    val contentType: String?,
    val sourceApp: String?,
    val createdAt: String?,
    val isFavorite: Boolean,
    val isSensitive: Boolean,
    val collection: String?,
    val deletedAt: String?,
    val hasAsset: Boolean = false,
)

data class ClipListResponse(
    val clips: List<ClipSummary>,
    val count: Int,
    val q: String? = null,
)

data class ClipDetailResponse(
    val clip: ClipSummary,
)

data class CollectionEntry(
    val name: String,
    val count: Int,
)

data class CollectionsResponse(
    val collections: List<CollectionEntry>,
)

data class InboxSendResponse(
    val success: Boolean,
    val desktopItemId: String? = null,
    val safeId: String? = null,
    val safeName: String? = null,
    val warning: String? = null,
    val error: String? = null,
)

enum class ClipFeed {
    ALL,
    FAVORITES,
    SCREENSHOTS,
    RECENT,
    COLLECTION,
}

sealed class BridgeError(message: String) : Exception(message) {
    class Disabled : BridgeError("Mobile Access is disabled on the PC.")
    class Unauthorized(reason: String) : BridgeError(reason)
    class NotFound : BridgeError("Not found.")
    class AssetNotAvailable(message: String = "Image not available on your PC.") :
        BridgeError(message)
    class Network(cause: Throwable) : BridgeError(cause.message ?: "Network error")
    class Unknown(code: Int, body: String) : BridgeError("HTTP $code: $body")
    class UnsupportedApi(version: String) :
        BridgeError("Unsupported mobile API version: $version")

    /** HTTP 426 — the versioned compatibility handshake rejected this client. */
    class UpdateRequired(
        val clientProtocol: Int?,
        val serverProtocolMin: Int?,
        val serverProtocolMax: Int?,
        val minimumMobileVersion: String?,
        serverMessage: String?,
    ) : BridgeError(serverMessage ?: "This app version is no longer compatible with your PC.")
}

data class ImageAssetResult(
    val bytes: ByteArray,
    val contentType: String,
)

data class ImageAssetState(
    val loading: Boolean = false,
    val bytes: ByteArray? = null,
    val contentType: String = "image/png",
    val error: String? = null,
)
