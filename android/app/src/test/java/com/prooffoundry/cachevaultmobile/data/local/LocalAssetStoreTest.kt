package com.prooffoundry.cachevaultmobile.data.local

import java.io.ByteArrayInputStream
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * JVM tests for the bounded image-file pipeline (CV-MOBILE-1). The dims probe
 * is faked so these exercise staging, hashing, finalization, traversal guards
 * and orphan reconciliation without needing Android's BitmapFactory.
 */
class LocalAssetStoreTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private lateinit var store: LocalAssetStore

    private val probe = LocalAssetStore.ImageDimsProbe { LocalAssetStore.ImageDims(8, 8) }

    @Before
    fun setUp() {
        store = LocalAssetStore(tmp.newFolder("files"), probe)
    }

    @Test
    fun importStagesValidatesHashesAndFinalizes() {
        val bytes = ByteArray(1024) { (it % 251).toByte() }
        val staged = store.importStream("image/png") { ByteArrayInputStream(bytes) }
        assertTrue(staged.file.exists())
        assertEquals("local_assets", staged.file.parentFile?.name)
        assertEquals(1024L, staged.byteCount)
        assertEquals(LocalVaultPolicy.sha256Hex(bytes), staged.sha256)
        assertEquals(8, staged.width)
        assertEquals(8, staged.height)
    }

    @Test
    fun zeroByteStreamRejectedAndStagedFileRemoved() {
        val dir = File(tmp.root, "files/local_assets/staging")
        try {
            store.importStream("image/png") { ByteArrayInputStream(ByteArray(0)) }
            fail("zero-byte must throw")
        } catch (e: LocalVaultError.ImageUnreadable) { }
        assertTrue(dir.listFiles()?.isEmpty() ?: true)
    }

    @Test
    fun oversizedStreamRejectedBeforeFullRead() {
        val oversized = ByteArray(LocalVaultPolicy.MAX_IMAGE_BYTES + 16) { 7 }
        try {
            store.importStream("image/jpeg") { ByteArrayInputStream(oversized) }
            fail("oversized must throw")
        } catch (e: LocalVaultError.ImageTooLarge) { }
        val dir = File(tmp.root, "files/local_assets/staging")
        assertTrue(dir.listFiles()?.isEmpty() ?: true)
    }

    @Test
    fun unsupportedMimeRejected() {
        try {
            store.importStream("image/heic") { ByteArrayInputStream(ByteArray(4)) }
            fail("unsupported mime must throw")
        } catch (e: LocalVaultError.UnsupportedImage) { }
        try {
            store.importStream(null) { ByteArrayInputStream(ByteArray(4)) }
            fail("missing mime must throw")
        } catch (e: LocalVaultError.UnsupportedImage) { }
    }

    @Test
    fun unreadableStreamRejected() {
        try {
            store.importStream("image/png") { null }
            fail("null stream must throw")
        } catch (e: LocalVaultError.ImageUnreadable) { }
    }

    @Test
    fun pixelBudgetEnforced() {
        val hugeProbe = LocalAssetStore.ImageDimsProbe {
            LocalAssetStore.ImageDims(10000, 5000) // 50 MP > 40 MP budget
        }
        val budgetStore = LocalAssetStore(File(tmp.root, "files2"), hugeProbe)
        try {
            budgetStore.importStream("image/png") { ByteArrayInputStream(ByteArray(64)) }
            fail("pixel-budget violation must throw")
        } catch (e: LocalVaultError.UnsupportedImage) { }
    }

    @Test
    fun undecodableProbeRejected() {
        val badProbe = LocalAssetStore.ImageDimsProbe { null }
        val s = LocalAssetStore(File(tmp.root, "files3"), badProbe)
        try {
            s.importStream("image/png") { ByteArrayInputStream(ByteArray(64)) }
            fail("undecodable must throw")
        } catch (e: LocalVaultError.ImageUnreadable) { }
    }

    @Test
    fun fileForRejectsTraversalAndStaging() {
        assertNull(store.fileFor("../escape.txt"))
        assertNull(store.fileFor("..\\escape.txt"))
        assertNull(store.fileFor("staging/stage_x"))
        assertNull(store.fileFor("nonexistent.png"))
    }

    @Test
    fun fileForResolvesOwnedFile() {
        val staged = store.importStream("image/png") { ByteArrayInputStream(ByteArray(32) { 3 }) }
        val f = store.fileFor(staged.file.name)
        assertNotNull(f)
        assertEquals(staged.file.absolutePath, f!!.absolutePath)
    }

    @Test
    fun reconcileKeepsReferencedAndRemovesOrphans() {
        val kept = store.importStream("image/png") { ByteArrayInputStream(ByteArray(16) { 1 }) }
        val orphan = File(File(tmp.root, "files/local_assets").apply { mkdirs() }, "orphan.png")
        orphan.writeBytes(ByteArray(8))
        val staging = File(tmp.root, "files/local_assets/staging/stage_abandoned")
        staging.parentFile?.mkdirs()
        staging.writeBytes(ByteArray(4))

        store.reconcileOrphans(setOf(kept.file.name))
        assertTrue(kept.file.exists())
        assertFalse(orphan.exists())
        assertFalse(staging.exists())
    }
}
