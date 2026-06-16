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
                  "product": "Cache Vault Mobile",
                  "byline": "A Proof Foundry companion app",
                  "mobile_access_enabled": true,
                  "cache_vault_version": "0.1.2",
                  "device_id": "dev-1",
                  "read_only": true
                }
                """.trimIndent(),
            ),
        )
        val status = client.status()
        assertEquals("Cache Vault Mobile", status.product)
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
}
