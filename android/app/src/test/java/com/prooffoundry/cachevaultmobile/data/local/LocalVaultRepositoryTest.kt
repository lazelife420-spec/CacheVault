package com.prooffoundry.cachevaultmobile.data.local

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import java.io.ByteArrayInputStream
import java.io.File
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Real-SQLite tests of the phone-local vault (CV-MOBILE-1). Robolectric gives
 * these a genuine on-disk database and files dir, so "close the repository and
 * open a fresh instance" exercises the same persistence path a process
 * restart does — no mocks involved.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LocalVaultRepositoryTest {

    private lateinit var context: Context
    private lateinit var dbName: String
    private val repos = mutableListOf<LocalVaultRepository>()

    private fun newRepo(): LocalVaultRepository {
        val repo = LocalVaultRepository(
            context = context,
            assetStore = LocalAssetStore(File(context.filesDir, "files_$dbName")),
            dbName = dbName,
            ioDispatcher = Dispatchers.Unconfined,
        )
        repos += repo
        return repo
    }

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        dbName = "test_${UUID.randomUUID()}.db"
    }

    @After
    fun tearDown() {
        repos.forEach { runCatching { it.close() } }
        runCatching { context.deleteDatabase(dbName) }
    }

    private fun fakeImage(bytes: ByteArray = ByteArray(64) { it.toByte() }) =
        ByteArrayInputStream(bytes)

    private fun fakeProbe(width: Int = 10, height: Int = 10) =
        LocalAssetStore.ImageDimsProbe { LocalAssetStore.ImageDims(width, height) }

    private suspend fun pngItem(): LocalItem {
        val store = LocalAssetStore(
            File(context.filesDir, "files_$dbName"),
            dimsProbe = fakeProbe(),
        )
        val direct = LocalVaultRepository(
            context = context,
            assetStore = store,
            dbName = dbName,
            ioDispatcher = Dispatchers.Unconfined,
        )
        repos += direct
        return direct.saveImage("image/png", "shot.png") { fakeImage() }
    }

    @Test
    fun saveTextPersistsVerbatimAcrossReopen() = runTest {
        val repo = newRepo()
        val content = "  spaced text \r\nsecond line 🎉"
        val saved = repo.saveText(content)
        assertEquals(content, saved.content)
        assertEquals(LocalVaultPolicy.sha256HexText(content), saved.contentHash)
        repo.close()

        val reopened = newRepo()
        val reloaded = reopened.item(saved.id)
        assertNotNull(reloaded)
        assertEquals(content, reloaded!!.content)
        assertEquals(saved.contentHash, reloaded.contentHash)
    }

    @Test
    fun bareUrlSavedAsLink() = runTest {
        val repo = newRepo()
        val item = repo.saveText("https://example.com/path?q=1")
        assertEquals(LocalItemKind.LINK, item.kind)
        assertEquals("https://example.com/path?q=1", item.content)
    }

    @Test
    fun blankTextRejectedAndNotPersisted() = runTest {
        val repo = newRepo()
        try {
            repo.saveText("   \n  ")
            fail("blank save must throw")
        } catch (e: LocalVaultError.Empty) {
            // expected
        }
        assertTrue(repo.recent().isEmpty())
    }

    @Test
    fun oversizedTextRejected() = runTest {
        val repo = newRepo()
        val big = "x".repeat(LocalVaultPolicy.MAX_TEXT_BYTES + 1)
        try {
            repo.saveText(big)
            fail("oversized text must throw")
        } catch (e: LocalVaultError.TextTooLarge) {
            // expected
        }
    }

    @Test
    fun textExactlyAtLimitIsAccepted() = runTest {
        val repo = newRepo()
        val exact = "x".repeat(LocalVaultPolicy.MAX_TEXT_BYTES)
        val saved = repo.saveText(exact)
        assertEquals(exact, saved.content)
    }

    @Test
    fun imageSavePersistsAssetAndSurvivesReopen() = runTest {
        val item = pngItem()
        assertEquals(LocalItemKind.IMAGE, item.kind)
        val repo = newRepo()
        val asset = repo.assetForItem(item.id)
        assertNotNull(asset)
        assertTrue(repo.assetFileFor(asset!!.fileName)!!.exists())
        // Reopen → same asset still resolves to an owned file.
        val repo2 = newRepo()
        assertTrue(repo2.assetFileFor(asset.fileName)!!.exists())
    }

    @Test
    fun zeroByteAndOversizedImagesRejected() = runTest {
        val repo = LocalVaultRepository(
            context = context,
            assetStore = LocalAssetStore(File(context.filesDir, "files_$dbName"), fakeProbe()),
            dbName = dbName,
            ioDispatcher = Dispatchers.Unconfined,
        )
        repos += repo
        try {
            repo.saveImage("image/png", null) { ByteArrayInputStream(ByteArray(0)) }
            fail("zero-byte image must throw")
        } catch (e: LocalVaultError.ImageUnreadable) { }
        try {
            repo.saveImage("image/png", null) {
                ByteArrayInputStream(ByteArray(LocalVaultPolicy.MAX_IMAGE_BYTES + 1))
            }
            fail("oversized image must throw")
        } catch (e: LocalVaultError.ImageTooLarge) { }
        try {
            repo.saveImage("image/heic", null) { fakeImage() }
            fail("unsupported mime must throw")
        } catch (e: LocalVaultError.UnsupportedImage) { }
        assertTrue(repo.recent().isEmpty())
    }

    @Test
    fun sensitiveContentIsFlaggedButStored() = runTest {
        val repo = newRepo()
        val item = repo.saveText("password = hunter2secret")
        assertTrue(item.isSensitive)
        assertNotNull(item.sensitiveReason)
        assertEquals("password = hunter2secret", item.content)
    }

    @Test
    fun favoriteMoveRemoveRestoreRoundTrip() = runTest {
        val repo = newRepo()
        val item = repo.saveText("note to self")
        repo.setFavorite(item.id, true)
        assertTrue(repo.item(item.id)!!.isFavorite)
        val safe = repo.createSafe("Recipes")
        repo.moveToSafe(item.id, safe.id)
        assertEquals(safe.id, repo.item(item.id)!!.safeId)
        repo.removeItem(item.id)
        assertTrue(repo.item(item.id)!!.isRemoved)
        assertTrue(repo.recent().isEmpty())
        assertEquals(1, repo.removedItems().size)
        repo.restoreItem(item.id)
        assertFalse(repo.item(item.id)!!.isRemoved)
        assertEquals(1, repo.recent().size)
    }

    @Test
    fun searchIsUnicodeAwareAndExcludesRemoved() = runTest {
        val repo = newRepo()
        repo.saveText("café menu for today")
        repo.saveText("plain ascii note")
        val removed = repo.saveText("hidden thing")
        repo.removeItem(removed.id)

        assertEquals(1, repo.search("café").size)
        assertEquals(1, repo.search("CAFÉ").size)   // unicode-insensitive
        assertEquals(0, repo.search("hidden").size)
        assertEquals(1, repo.search("hidden", filter = LocalFilter.REMOVED).size)
        assertEquals(2, repo.search("").size)
    }

    @Test
    fun searchTreatsWildcardsAndQuotesLiterally() = runTest {
        val repo = newRepo()
        repo.saveText("progress at 100%")
        repo.saveText("he said \"hi\"")
        repo.saveText("under_score_name")
        assertEquals(1, repo.search("100%").size)
        assertEquals(1, repo.search("\"hi\"").size)
        assertEquals(1, repo.search("under_score").size)
        // % must not act as a wildcard
        assertEquals(0, repo.search("progress%anything").size)
    }

    @Test
    fun defaultSafeExistsAndIsProtected() = runTest {
        val repo = newRepo()
        val safes = repo.safes()
        assertTrue(safes.any { it.id == LocalVaultDatabase.DEFAULT_SAFE_ID && it.isDefault })
        try {
            repo.renameSafe(LocalVaultDatabase.DEFAULT_SAFE_ID, "Renamed")
            fail("default safe rename must throw")
        } catch (e: LocalVaultError.DefaultSafeProtected) { }
        try {
            repo.moveToSafe("nonexistent", "also-not-there")
            fail("unknown safe must throw")
        } catch (e: LocalVaultError.SafeNotFound) { }
    }

    @Test
    fun safeCreateRenameAndItemCounts() = runTest {
        val repo = newRepo()
        val safe = repo.createSafe("  Ideas  ")
        assertEquals("Ideas", safe.name)
        repo.renameSafe(safe.id, "Better Ideas")
        assertEquals("Better Ideas", repo.safes().first { it.id == safe.id }.name)
        repo.saveText("into ideas", safeId = safe.id)
        assertEquals(1, repo.countBySafe()[safe.id])
        assertEquals(1, repo.itemsInSafe(safe.id).size)
    }

    @Test
    fun activityLedgerRecordsActionsWithoutPayloads() = runTest {
        val repo = newRepo()
        val secret = "sk-testsecrettoken12345"
        val item = repo.saveText(secret)
        repo.recordCopy(item.id)
        repo.recordShareInitiated(item.id)
        repo.recordCancelledSave()
        val events = repo.activity()
        assertTrue(events.any { it.action == "save" && it.outcome == "completed" })
        assertTrue(events.any { it.action == "copy" && it.outcome == "completed" })
        assertTrue(events.any { it.action == "share" && it.outcome == "initiated" })
        assertTrue(events.any { it.action == "save" && it.outcome == "cancelled" })
        // No item body ever lands in the ledger.
        assertFalse(events.any { it.reason == secret || it.action.contains(secret) })
        assertTrue(events.all { (it.reason?.length ?: 0) <= LocalVaultPolicy.REASON_MAX_CHARS })
    }

    @Test
    fun vaultIdIsStableAcrossReopen() = runTest {
        val repo = newRepo()
        val id1 = repo.vaultId()
        repo.close()
        val id2 = newRepo().vaultId()
        assertEquals(id1, id2)
    }

    @Test
    fun orphanAssetFilesAreReconciledOnOpen() = runTest {
        val dir = File(context.filesDir, "files_$dbName/local_assets")
        dir.mkdirs()
        val stray = File(dir, "orphan.png").apply { writeBytes(ByteArray(8) { 1 }) }
        assertTrue(stray.exists())
        val repo = newRepo()
        repo.recent() // any read triggers reconcile
        assertFalse("orphan file must be removed on open", stray.exists())
    }

    @Test
    fun newerSchemaFailsClosedAndPreservesFile() = runTest {
        val repo = newRepo()
        repo.saveText("keep me")
        repo.close()

        // Simulate a newer schema on disk, then open with a v1 helper.
        val dbFile = context.getDatabasePath(dbName)
        val rawDb = android.database.sqlite.SQLiteDatabase.openDatabase(
            dbFile.absolutePath, null, android.database.sqlite.SQLiteDatabase.OPEN_READWRITE,
        )
        rawDb.version = 2
        rawDb.close()

        val old = LocalVaultDatabase(context, dbName, dbVersion = 1)
        try {
            old.writableDatabase
            fail("downgrade must throw")
        } catch (e: android.database.sqlite.SQLiteException) {
            // expected — data preserved, never silently wiped
        }
        assertTrue(dbFile.exists())
    }
}
