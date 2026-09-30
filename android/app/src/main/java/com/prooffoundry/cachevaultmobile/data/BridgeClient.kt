package com.prooffoundry.cachevaultmobile.data

import com.squareup.moshi.Json
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import java.util.UUID

class BridgeClient(
    private val pairing: PairingConfig,
    private val http: OkHttpClient = defaultClient(),
) {
    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    fun status(): BridgeStatus {
        val status = get("/mobile/v1/status", StatusJson::class.java).toModel()
        if (status.mobileApiVersion != UserMessages.SUPPORTED_API_VERSION) {
            throw BridgeError.UnsupportedApi(status.mobileApiVersion)
        }
        if (!status.mobileAccessEnabled) {
            throw BridgeError.Disabled()
        }
        return status
    }

    fun listClips(): ClipListResponse =
        get("/mobile/v1/clips", ClipListJson::class.java).toModel()

    fun listFavorites(): ClipListResponse =
        get("/mobile/v1/favorites", ClipListJson::class.java).toModel()

    fun listRecentlyRemoved(): ClipListResponse =
        get("/mobile/v1/recently-removed", ClipListJson::class.java).toModel()

    fun search(query: String): ClipListResponse =
        get("/mobile/v1/search?q=${encode(query)}", ClipListJson::class.java).toModel(query)

    fun clipDetail(id: String): ClipDetailResponse =
        get("/mobile/v1/clips/$id", ClipDetailJson::class.java).toModel()

    fun listCollections(): CollectionsResponse =
        get("/mobile/v1/collections", CollectionsJson::class.java).toModel()

    fun logCopy(clipId: String) {
        post("/mobile/v1/clips/$clipId/copy")
    }

    fun logShare(clipId: String) {
        post("/mobile/v1/clips/$clipId/share")
    }

    fun logSave(clipId: String) {
        post("/mobile/v1/clips/$clipId/save")
    }

    fun sendToPc(
        content: String,
        itemType: String = "text",
        sourceApp: String? = null,
        sourceDeviceName: String? = null,
        sourceUrl: String? = null,
        safeId: String? = null,
    ): InboxSendResponse {
        val payload = InboxSendRequest(
            itemType = itemType,
            content = content,
            sourceApp = sourceApp,
            sourceDeviceName = sourceDeviceName,
            sourceUrl = sourceUrl,
            safeId = safeId,
            userAction = "send_to_pc",
        )
        val json = moshi.adapter(InboxSendRequest::class.java).toJson(payload)
        val body = json.toRequestBody("application/json".toMediaType())
        val request = baseRequest("/mobile/v1/inbox/send").post(body).build()
        return execute(request, InboxSendResponseJson::class.java).toModel()
    }

    /**
     * Send an image to the paired PC. [contentB64] is the base64-encoded image
     * bytes (encoding is the caller's responsibility so this stays JVM-testable).
     */
    fun sendImageToPc(
        contentB64: String,
        mimeType: String,
        originalName: String? = null,
        sourceApp: String? = null,
        sourceDeviceName: String? = null,
        safeId: String? = null,
    ): InboxSendResponse {
        val payload = InboxImageSendRequest(
            contentB64 = contentB64,
            mimeType = mimeType,
            originalName = originalName,
            sourceApp = sourceApp,
            sourceDeviceName = sourceDeviceName,
            safeId = safeId,
        )
        val json = moshi.adapter(InboxImageSendRequest::class.java).toJson(payload)
        val body = json.toRequestBody("application/json".toMediaType())
        val request = baseRequest("/mobile/v1/inbox/send").post(body).build()
        return execute(request, InboxSendResponseJson::class.java).toModel()
    }

    fun pairDevice(
        deviceName: String? = null,
        deviceId: String = generateDeviceId(),
        appVersion: String? = AppIdentity.APP_VERSION,
        platform: String = AppIdentity.PLATFORM,
        build: Int? = AppIdentity.APP_BUILD,
        protocol: Int = AppIdentity.PROTOCOL_VERSION,
        deviceModel: String? = null,
        pairingToken: String? = null,
    ): PairDeviceGrant {
        val payload = PairDeviceRequest(
            deviceId = deviceId,
            deviceName = deviceName,
            appVersion = appVersion,
            platform = platform,
            build = build,
            protocol = protocol,
            device = if (deviceName != null || deviceModel != null) {
                DeviceInfoJson(name = deviceName, model = deviceModel)
            } else {
                null
            },
            pairingToken = pairingToken,
        )
        val json = moshi.adapter(PairDeviceRequest::class.java).toJson(payload)
        val body = json.toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("http://${pairing.host}:${pairing.port}/mobile/v1/pair-device")
            .post(body)
            .build()
        return execute(request, PairDeviceResponseJson::class.java).toModel()
    }

    fun fetchImageAsset(clipId: String): ImageAssetResult {
        val request = baseRequest("/mobile/v1/clips/$clipId/asset").get().build()
        try {
            http.newCall(request).execute().use { response ->
                val bodyBytes = response.body?.bytes() ?: byteArrayOf()
                when (response.code) {
                    200 -> {
                        val ct = response.header("Content-Type") ?: "image/png"
                        return ImageAssetResult(bodyBytes, ct)
                    }
                    401 -> throw BridgeError.Unauthorized(parseMessage(String(bodyBytes)))
                    423 -> throw BridgeError.VaultLocked()
                    503 -> throw BridgeError.Disabled()
                    404 -> throw parseAssetNotAvailable(String(bodyBytes))
                    else -> throw BridgeError.Unknown(response.code, String(bodyBytes))
                }
            }
        } catch (e: BridgeError) {
            throw e
        } catch (e: Exception) {
            throw BridgeError.Network(e)
        }
    }

    private fun parseAssetNotAvailable(body: String): BridgeError {
        val err = runCatching {
            moshi.adapter(AssetErrorJson::class.java).fromJson(body)?.error
        }.getOrNull()
        return if (err == "asset_not_available") {
            BridgeError.AssetNotAvailable(
                moshi.adapter(AssetErrorJson::class.java).fromJson(body)?.message
                    ?: UserMessages.IMAGE_NOT_AVAILABLE,
            )
        } else {
            BridgeError.NotFound()
        }
    }

    private fun <T> get(path: String, type: Class<T>): T {
        val request = baseRequest(path).get().build()
        return execute(request, type)
    }

    private fun post(path: String) {
        val body = "{}".toRequestBody("application/json".toMediaType())
        val request = baseRequest(path).post(body).build()
        execute(request, OkJson::class.java)
    }

    private fun baseRequest(path: String): Request.Builder {
        val base = "http://${pairing.host}:${pairing.port}"
        return Request.Builder()
            .url("$base$path")
            .header("X-Device-Id", pairing.deviceId)
            .header("Authorization", "Bearer ${pairing.token}")
            // Lets an already-paired device's compatibility state update on
            // reconnect (e.g. after this app is updated) without a full
            // re-pair — see docs/MOBILE_API_CONTRACT.md.
            .header("X-App-Version", AppIdentity.APP_VERSION)
            .header("X-App-Build", AppIdentity.APP_BUILD.toString())
            .header("X-Protocol-Version", AppIdentity.PROTOCOL_VERSION.toString())
    }

    private fun <T> execute(request: Request, type: Class<T>): T {
        try {
            http.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                when (response.code) {
                    200 -> return parseJson(body, type)
                    401 -> throw BridgeError.Unauthorized(parseMessage(body))
                    423 -> throw BridgeError.VaultLocked()
                    426 -> throw parseUpdateRequired(body)
                    503 -> throw BridgeError.Disabled()
                    404 -> throw BridgeError.NotFound()
                    else -> throw BridgeError.Unknown(response.code, body)
                }
            }
        } catch (e: BridgeError) {
            throw e
        } catch (e: Exception) {
            throw BridgeError.Network(e)
        }
    }

    private fun parseUpdateRequired(body: String): BridgeError.UpdateRequired {
        val parsed = runCatching {
            moshi.adapter(IncompatibleJson::class.java).fromJson(body)
        }.getOrNull()
        return BridgeError.UpdateRequired(
            clientProtocol = parsed?.clientProtocol,
            serverProtocolMin = parsed?.serverProtocolMin,
            serverProtocolMax = parsed?.serverProtocolMax,
            minimumMobileVersion = parsed?.minimumMobileVersion,
            serverMessage = parsed?.message,
        )
    }

    private fun <T> parseJson(body: String, type: Class<T>): T {
        val adapter = moshi.adapter(type)
        return adapter.fromJson(body)
            ?: throw BridgeError.Network(IllegalStateException("Empty JSON"))
    }

    private fun parseMessage(body: String): String {
        return runCatching {
            moshi.adapter(ErrorJson::class.java).fromJson(body)?.message
        }.getOrNull() ?: "Unauthorized"
    }

    private fun encode(value: String): String =
        java.net.URLEncoder.encode(value, Charsets.UTF_8.name())

    companion object {
        fun defaultClient(): OkHttpClient =
            OkHttpClient.Builder()
                .connectTimeout(8, TimeUnit.SECONDS)
                .readTimeout(12, TimeUnit.SECONDS)
                .build()

        fun generateDeviceId(): String = UUID.randomUUID().toString().replace("-", "")
    }

    private data class StatusJson(
        val product: String,
        val byline: String,
        @Json(name = "mobile_api_version") val mobileApiVersion: String = "1",
        @Json(name = "mobile_access_enabled") val mobileAccessEnabled: Boolean,
        @Json(name = "cache_vault_version") val cacheVaultVersion: String,
        @Json(name = "device_id") val deviceId: String,
        @Json(name = "read_only") val readOnly: Boolean,
        val compatible: Boolean? = null,
        @Json(name = "server_protocol_min") val serverProtocolMin: Int? = null,
        @Json(name = "server_protocol_max") val serverProtocolMax: Int? = null,
        @Json(name = "minimum_mobile_version") val minimumMobileVersion: String? = null,
        @Json(name = "update_required") val updateRequired: Boolean = false,
    ) {
        fun toModel() = BridgeStatus(
            product, byline, mobileApiVersion, mobileAccessEnabled,
            cacheVaultVersion, deviceId, readOnly,
            compatible, serverProtocolMin, serverProtocolMax,
            minimumMobileVersion, updateRequired,
        )
    }

    private data class ClipJson(
        val id: String,
        val preview: String,
        val content: String,
        val classification: String?,
        @Json(name = "content_type") val contentType: String?,
        @Json(name = "source_app") val sourceApp: String?,
        @Json(name = "created_at") val createdAt: String?,
        @Json(name = "is_favorite") val isFavorite: Boolean,
        @Json(name = "is_sensitive") val isSensitive: Boolean,
        val collection: String?,
        @Json(name = "deleted_at") val deletedAt: String?,
        @Json(name = "has_asset") val hasAsset: Boolean = false,
    ) {
        fun toModel() = ClipSummary(
            id, preview, content, classification, contentType, sourceApp,
            createdAt, isFavorite, isSensitive, collection, deletedAt, hasAsset,
        )
    }

    private data class ClipListJson(
        val clips: List<ClipJson>,
        val count: Int,
        val q: String? = null,
    ) {
        fun toModel(query: String? = q) =
            ClipListResponse(clips.map { it.toModel() }, count, query)
    }

    private data class ClipDetailJson(val clip: ClipJson) {
        fun toModel() = ClipDetailResponse(clip.toModel())
    }

    private data class CollectionJson(val name: String, val count: Int)
    private data class CollectionsJson(val collections: List<CollectionJson>) {
        fun toModel() = CollectionsResponse(
            collections.map { CollectionEntry(it.name, it.count) },
        )
    }

    private data class ErrorJson(val message: String? = null)
    private data class AssetErrorJson(
        val error: String? = null,
        val message: String? = null,
    )
    private data class OkJson(val ok: Boolean? = null)

    private data class DeviceInfoJson(
        val name: String? = null,
        val model: String? = null,
    )

    private data class PairDeviceRequest(
        val client: String = "cachevault-android",
        @Json(name = "device_id") val deviceId: String,
        @Json(name = "device_name") val deviceName: String? = null,
        @Json(name = "app_version") val appVersion: String? = null,
        val platform: String = "android",
        val build: Int? = null,
        val protocol: Int? = null,
        val device: DeviceInfoJson? = null,
        @Json(name = "pairing_token") val pairingToken: String? = null,
    )

    private data class PairDeviceResponseJson(
        @Json(name = "device_id") val deviceId: String,
        @Json(name = "device_name") val deviceName: String,
        val token: String,
        val compatible: Boolean? = null,
        @Json(name = "server_protocol_min") val serverProtocolMin: Int? = null,
        @Json(name = "server_protocol_max") val serverProtocolMax: Int? = null,
        @Json(name = "minimum_mobile_version") val minimumMobileVersion: String? = null,
        @Json(name = "update_required") val updateRequired: Boolean = false,
    ) {
        fun toModel() = PairDeviceGrant(
            deviceId, deviceName, token,
            compatible, serverProtocolMin, serverProtocolMax,
            minimumMobileVersion, updateRequired,
        )
    }

    private data class IncompatibleJson(
        val error: String? = null,
        val compatible: Boolean? = null,
        @Json(name = "client_protocol") val clientProtocol: Int? = null,
        @Json(name = "server_protocol_min") val serverProtocolMin: Int? = null,
        @Json(name = "server_protocol_max") val serverProtocolMax: Int? = null,
        @Json(name = "minimum_mobile_version") val minimumMobileVersion: String? = null,
        @Json(name = "update_required") val updateRequired: Boolean? = null,
        val message: String? = null,
    )

    private data class InboxSendRequest(
        @Json(name = "item_type") val itemType: String,
        val content: String,
        @Json(name = "source_app") val sourceApp: String? = null,
        @Json(name = "source_device_name") val sourceDeviceName: String? = null,
        @Json(name = "source_url") val sourceUrl: String? = null,
        @Json(name = "safe_id") val safeId: String? = null,
        @Json(name = "user_action") val userAction: String = "send_to_pc",
    )

    private data class InboxImageSendRequest(
        @Json(name = "item_type") val itemType: String = "image",
        @Json(name = "content_b64") val contentB64: String,
        @Json(name = "mime_type") val mimeType: String,
        @Json(name = "original_name") val originalName: String? = null,
        @Json(name = "source_app") val sourceApp: String? = null,
        @Json(name = "source_device_name") val sourceDeviceName: String? = null,
        @Json(name = "safe_id") val safeId: String? = null,
        @Json(name = "user_action") val userAction: String = "send_to_pc",
    )

    private data class InboxSendResponseJson(
        val success: Boolean,
        @Json(name = "desktop_item_id") val desktopItemId: String? = null,
        @Json(name = "safe_id") val safeId: String? = null,
        @Json(name = "safe_name") val safeName: String? = null,
        val warning: String? = null,
        val error: String? = null,
    ) {
        fun toModel() = InboxSendResponse(
            success, desktopItemId, safeId, safeName, warning, error,
        )
    }
}
