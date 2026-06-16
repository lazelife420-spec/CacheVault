package com.prooffoundry.cachevaultmobile.data

import com.squareup.moshi.Json
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

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
    }

    private fun <T> execute(request: Request, type: Class<T>): T {
        try {
            http.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                when (response.code) {
                    200 -> return parseJson(body, type)
                    401 -> throw BridgeError.Unauthorized(parseMessage(body))
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
    }

    private data class StatusJson(
        val product: String,
        val byline: String,
        @Json(name = "mobile_api_version") val mobileApiVersion: String = "1",
        @Json(name = "mobile_access_enabled") val mobileAccessEnabled: Boolean,
        @Json(name = "cache_vault_version") val cacheVaultVersion: String,
        @Json(name = "device_id") val deviceId: String,
        @Json(name = "read_only") val readOnly: Boolean,
    ) {
        fun toModel() = BridgeStatus(
            product, byline, mobileApiVersion, mobileAccessEnabled,
            cacheVaultVersion, deviceId, readOnly,
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
}
