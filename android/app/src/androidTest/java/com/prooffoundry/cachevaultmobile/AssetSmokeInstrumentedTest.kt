package com.prooffoundry.cachevaultmobile

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.PairingConfig
import com.prooffoundry.cachevaultmobile.data.PairingStore
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Real-device smoke: pair via instrumentation args, fetch screenshot asset, log share/save.
 * Invoked by scripts/android_asset_smoke.py — not for CI emulator.
 */
@RunWith(AndroidJUnit4::class)
class AssetSmokeInstrumentedTest {

    @Test
    fun screenshotAssetRoundTrip() {
        val args = InstrumentationRegistry.getArguments()
        val host = args.getString("host") ?: error("Missing -e host")
        val port = args.getString("port")?.toIntOrNull() ?: 8742
        val deviceId = args.getString("device_id") ?: error("Missing -e device_id")
        val token = args.getString("token") ?: error("Missing -e token")

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val store = PairingStore(context)
        store.save(PairingConfig(host, port, deviceId, token, "Smoke PC"))

        val client = BridgeRepository(store).client()
        val status = client.status()
        assertTrue(status.mobileAccessEnabled)

        val screenshots = client.listClips().clips.filter {
            ClipKinds.isImageReference(it) && it.hasAsset
        }
        assertTrue("No screenshot clips with assets on PC", screenshots.isNotEmpty())

        val clip = screenshots.first()
        val detail = client.clipDetail(clip.id).clip
        assertTrue(detail.content.isNotBlank() || detail.preview.isNotBlank())

        val asset = client.fetchImageAsset(clip.id)
        assertTrue("Asset bytes empty", asset.bytes.isNotEmpty())
        assertTrue(asset.contentType.startsWith("image/"))

        client.logShare(clip.id)
        client.logSave(clip.id)
    }
}
