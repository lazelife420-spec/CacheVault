package com.prooffoundry.cachevaultmobile.data

import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class BridgeClientTest {
    private lateinit var server: MockWebServer
    private lateinit var client: BridgeClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        val pairing = PairingConfig(
            host = server.hostName,
            port = server.port,
            deviceId = "dev-1",
            token = "secret-token",
        )
        client = BridgeClient(pairing)
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun status_parsesBridgeResponse() {
        server.enqueue(
            MockResponse().setBody(
                """
                {
                  "product": "Cache Vault",
                  "byline": "A Proof Foundry companion app",
                  "mobile_api_version": "1",
                  "mobile_access_enabled": true,
                  "cache_vault_version": "0.1.2",
                  "device_id": "dev-1",
                  "read_only": true
                }
                """.trimIndent(),
            ),
        )
        val status = client.status()
        assertEquals("Cache Vault", status.product)
        assertEquals("1", status.mobileApiVersion)
        assertTrue(status.readOnly)
        val request = server.takeRequest()
        assertEquals("dev-1", request.getHeader("X-Device-Id"))
        assertEquals("Bearer secret-token", request.getHeader("Authorization"))
    }

    @Test(expected = BridgeError.Disabled::class)
    fun disabledBridgeFailsClosed() {
        server.enqueue(
            MockResponse().setResponseCode(503).setBody(
                """{"error":"mobile_access_disabled"}""",
            ),
        )
        client.status()
    }

    @Test
    fun clipDetailReturnsFullContent() {
        server.enqueue(
            MockResponse().setBody(
                """
                {
                  "clip": {
                    "id": "abc",
                    "preview": "secret",
                    "content": "sk-live-full-token",
                    "classification": null,
                    "content_type": "text",
                    "source_app": null,
                    "created_at": "2026-01-01T00:00:00Z",
                    "is_favorite": false,
                    "is_sensitive": true,
                    "collection": null,
                    "deleted_at": null
                  }
                }
                """.trimIndent(),
            ),
        )
        val clip = client.clipDetail("abc").clip
        assertEquals("sk-live-full-token", clip.content)
        assertTrue(clip.isSensitive)
    }

    @Test
    fun pairDevicePostsDeviceMetadata() {
        server.enqueue(
            MockResponse().setBody(
                """
                {
                  "device_id": "pixel-9",
                  "device_name": "Pixel 9",
                  "token": "pair-token-123"
                }
                """.trimIndent(),
            ),
        )
        val grant = client.pairDevice(
            deviceName = "Pixel 9",
            deviceId = "pixel-9",
            appVersion = "0.1.0",
        )
        assertEquals("pixel-9", grant.deviceId)
        assertEquals("Pixel 9", grant.deviceName)
        assertEquals("pair-token-123", grant.token)
        val request = server.takeRequest()
        assertEquals("/mobile/v1/pair-device", request.path)
        val sentBody = request.body.readUtf8()
        assertTrue(sentBody.contains("\"device_id\":\"pixel-9\""))
        assertTrue(sentBody.contains("\"device_name\":\"Pixel 9\""))
        assertTrue(sentBody.contains("\"app_version\":\"0.1.0\""))
        assertTrue(sentBody.contains("\"platform\":\"android\""))
    }

    @Test
    fun fetchImageAssetReturnsBytes() {
        val pngHeader = byteArrayOf(
            0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        )
        server.enqueue(
            MockResponse()
                .setHeader("Content-Type", "image/png")
                .setBody(okio.Buffer().write(pngHeader)),
        )
        val result = client.fetchImageAsset("img-1")
        assertEquals("image/png", result.contentType)
        assertTrue(result.bytes.contentEquals(pngHeader))
        val request = server.takeRequest()
        assertEquals("/mobile/v1/clips/img-1/asset", request.path)
    }

    @Test
    fun sendImageToPcPostsBase64Payload() {
        server.enqueue(
            MockResponse().setBody(
                """{"success":true,"desktop_item_id":"img9","safe_name":"Default Safe"}""",
            ),
        )
        val resp = client.sendImageToPc(
            contentB64 = "iVBORw0KGgo=",
            mimeType = "image/png",
            originalName = "photo.png",
            sourceApp = "Android Share",
            sourceDeviceName = "Pixel",
            safeId = "default",
        )
        assertTrue(resp.success)
        assertEquals("Default Safe", resp.safeName)
        val request = server.takeRequest()
        assertEquals("/mobile/v1/inbox/send", request.path)
        val sentBody = request.body.readUtf8()
        assertTrue(sentBody.contains("\"item_type\":\"image\""))
        assertTrue(sentBody.contains("\"content_b64\":\"iVBORw0KGgo=\""))
        assertTrue(sentBody.contains("\"mime_type\":\"image/png\""))
        assertEquals("Bearer secret-token", request.getHeader("Authorization"))
    }

    @Test(expected = BridgeError.AssetNotAvailable::class)
    fun fetchImageAssetNotAvailable() {
        server.enqueue(
            MockResponse().setResponseCode(404).setBody(
                """{"error":"asset_not_available","message":"No image"}""",
            ),
        )
        client.fetchImageAsset("txt-1")
    }
}
