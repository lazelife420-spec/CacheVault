package com.prooffoundry.cachevaultmobile

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.prooffoundry.cachevaultmobile.data.local.LocalAssetStore
import com.prooffoundry.cachevaultmobile.data.local.LocalFilter
import com.prooffoundry.cachevaultmobile.data.local.LocalItemKind
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository
import java.io.ByteArrayInputStream
import java.io.File
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * On-device persistence proof for the phone-local vault (CV-MOBILE-1).
 * A fresh repository instance against the same database file exercises the
 * same reopen path a process restart does. Runs only under
 * connectedDebugAndroidTest on a device/emulator — never in JVM unit tests.
 */
@RunWith(AndroidJUnit4::class)
class LocalVaultInstrumentedTest {

    private fun repo(context: android.content.Context, dbName: String) = LocalVaultRepository(
        context = context,
        assetStore = LocalAssetStore(File(context.filesDir, "files_$dbName")),
        dbName = dbName,
    )

    @Test
    fun textSurvivesRepositoryReopen() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val dbName = "instr_${UUID.randomUUID()}.db"
        try {
            val first = repo(context, dbName)
            val saved = first.saveText("on-device persisted 🎉\r\nline two")
            first.close()

            val second = repo(context, dbName)
            val reloaded = second.item(saved.id)
            assertNotNull(reloaded)
            assertEquals("on-device persisted 🎉\r\nline two", reloaded!!.content)
            second.close()
        } finally {
            context.deleteDatabase(dbName)
        }
    }

    @Test
    fun imageSurvivesReopenAndStaysInSafe() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val dbName = "instr_${UUID.randomUUID()}.db"
        try {
            // A real, decodable PNG produced on-device — the ingestion path
            // correctly rejects bytes that are not a valid image.
            val pngStream = java.io.ByteArrayOutputStream()
            android.graphics.Bitmap.createBitmap(8, 8, android.graphics.Bitmap.Config.ARGB_8888)
                .compress(android.graphics.Bitmap.CompressFormat.PNG, 100, pngStream)
            val png = pngStream.toByteArray()
            val first = repo(context, dbName)
            val safe = first.createSafe("Device Safe")
            val item = first.saveImage("image/png", "on-device.png", safe.id) {
                ByteArrayInputStream(png)
            }
            first.close()

            val second = repo(context, dbName)
            val asset = second.assetForItem(item.id)
            assertNotNull(asset)
            assertEquals(safe.id, second.item(item.id)!!.safeId)
            assertTrue(second.assetFileFor(asset!!.fileName)!!.exists())
            second.close()
        } finally {
            context.deleteDatabase(dbName)
        }
    }

    @Test
    fun searchAndActivityWorkOfflineOnDevice() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val dbName = "instr_${UUID.randomUUID()}.db"
        try {
            val r = repo(context, dbName)
            r.saveText("café on device")
            r.recordCancelledSave()
            assertEquals(1, r.search("CAFÉ").size)
            assertEquals(0, r.search("%wildcard%").size)
            assertTrue(r.activity().any { it.outcome == "cancelled" })
            r.close()
        } finally {
            context.deleteDatabase(dbName)
        }
    }
}
