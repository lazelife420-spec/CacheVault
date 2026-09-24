package com.prooffoundry.cachevaultmobile.ui

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.prooffoundry.cachevaultmobile.data.local.LocalFilter
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository
import java.io.File
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * ViewModel tests against a real repository + real SQLite (CV-MOBILE-1).
 * Everything runs on unconfined test dispatchers so launches complete inline —
 * the point is state correctness and the generation-aware search, not timing.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LocalVaultViewModelTest {

    private lateinit var context: Context
    private lateinit var dbName: String
    private lateinit var repository: LocalVaultRepository
    private lateinit var vm: LocalVaultViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        context = ApplicationProvider.getApplicationContext()
        dbName = "vm_${UUID.randomUUID()}.db"
        repository = LocalVaultRepository(
            context = context,
            assetStore = com.prooffoundry.cachevaultmobile.data.local.LocalAssetStore(
                File(context.filesDir, "files_$dbName"),
            ),
            dbName = dbName,
            ioDispatcher = Dispatchers.Unconfined,
        )
        vm = LocalVaultViewModel(repository)
    }

    @After
    fun tearDown() {
        runCatching { repository.close() }
        runCatching { context.deleteDatabase(dbName) }
        Dispatchers.resetMain()
    }

    @Test
    fun opensReadyWithLocalStoreNotNetwork() {
        val s = vm.state.value
        assertTrue(s.ready)
        assertNull(s.fatalError)
        assertTrue(s.safes.isNotEmpty())
    }

    @Test
    fun saveTextUpdatesListAndActivity() {
        vm.saveText("remember this", safeId = com.prooffoundry.cachevaultmobile.data.local.LocalVaultDatabase.DEFAULT_SAFE_ID)
        val s = vm.state.value
        assertEquals("remember this", s.items.first().content)
        assertTrue(s.activity.any { it.action == "save" })
        assertEquals("Saved on this phone", s.transientMessage)
    }

    @Test
    fun searchQueryFiltersAndClears() {
        vm.saveText("alpha note")
        vm.saveText("beta note")
        vm.setQuery("alpha")
        assertEquals(1, vm.state.value.items.size)
        assertEquals("alpha note", vm.state.value.items.first().content)
        vm.setQuery("")
        assertEquals(2, vm.state.value.items.size)
    }

    @Test
    fun favoritesFilterShowsOnlyFavorites() {
        vm.saveText("fav me")
        val id = vm.state.value.items.first().id
        vm.toggleFavorite(vm.state.value.items.first())
        vm.setFilter(LocalFilter.FAVORITES)
        assertEquals(1, vm.state.value.items.size)
        vm.setFilter(LocalFilter.ALL)
        assertEquals(1, vm.state.value.items.size)
        assertTrue(vm.state.value.items.first().id == id)
    }

    @Test
    fun removeMovesToRemovedFilterAndRestoreBringsBack() {
        vm.saveText("temporary")
        val item = vm.state.value.items.first()
        vm.removeItem(item.id)
        assertTrue(vm.state.value.items.none { it.id == item.id })
        vm.setFilter(LocalFilter.REMOVED)
        assertEquals(1, vm.state.value.items.size)
        vm.restoreItem(item.id)
        vm.setFilter(LocalFilter.ALL)
        assertTrue(vm.state.value.items.any { it.id == item.id })
    }

    @Test
    fun openItemLoadsSelectedAndRecordsActivity() {
        vm.saveText("detail me")
        val item = vm.state.value.items.first()
        vm.openItem(item.id)
        val s = vm.state.value
        assertNotNull(s.selectedItem)
        assertEquals(item.id, s.selectedItem!!.id)
        assertTrue(s.activity.any { it.action == "open" && it.itemId == item.id })
        vm.closeItem()
        assertNull(vm.state.value.selectedItem)
    }

    @Test
    fun failedSaveSurfacesMessageAndRecordsFailure() {
        vm.saveText("   ")
        val s = vm.state.value
        assertTrue(s.transientMessage?.contains("empty", ignoreCase = true) == true)
        assertTrue(s.activity.any { it.action == "save" && it.outcome == "failed" })
    }

    @Test
    fun blankClipboardPasteIsFailedOutcomeNotPlaceholder() {
        vm.saveText("")
        assertTrue(vm.state.value.items.isEmpty())
        assertTrue(vm.state.value.activity.any { it.outcome == "failed" })
    }

    @Test
    fun safeSelectionScopesList() {
        vm.saveText("in default")
        vm.createSafe("Scoped")
        val safe = vm.state.value.safes.first { it.name == "Scoped" }
        vm.saveText("in scoped", safeId = safe.id)
        vm.selectSafe(safe.id)
        assertEquals(1, vm.state.value.items.size)
        vm.selectSafe(null)
        assertEquals(2, vm.state.value.items.size)
    }

    @Test
    fun sensitiveItemIsStoredMaskedInListState() {
        vm.saveText("api_key = abcd1234secret")
        val s = vm.state.value
        assertTrue(s.items.first().isSensitive)
        // Item exists with full content; masking is a display rule enforced in UI.
        assertEquals("api_key = abcd1234secret", s.items.first().content)
        assertFalse(s.revealed.contains(s.items.first().id))
        vm.reveal(s.items.first().id)
        assertTrue(vm.state.value.revealed.contains(s.items.first().id))
    }
}
