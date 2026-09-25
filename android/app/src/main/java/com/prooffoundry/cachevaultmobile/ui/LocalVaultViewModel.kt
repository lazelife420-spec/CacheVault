package com.prooffoundry.cachevaultmobile.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.prooffoundry.cachevaultmobile.data.local.LocalActivityEvent
import com.prooffoundry.cachevaultmobile.data.local.LocalFilter
import com.prooffoundry.cachevaultmobile.data.local.LocalAsset
import com.prooffoundry.cachevaultmobile.data.local.LocalIngestion
import com.prooffoundry.cachevaultmobile.data.local.LocalItem
import com.prooffoundry.cachevaultmobile.data.local.LocalItemKind
import com.prooffoundry.cachevaultmobile.data.local.LocalSafe
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultDatabase
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultError
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository
import java.io.InputStream
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * State and intents for the phone-local vault (CV-MOBILE-1).
 *
 * This ViewModel never calls BridgeRepository: every listed operation works
 * with the PC offline or never paired. `ready` means the local store opened;
 * `fatalError` means the local database itself could not be used — a real
 * local failure, never a disguised empty vault.
 */
class LocalVaultViewModel(
    private val repository: LocalVaultRepository,
) : ViewModel() {

    /** Bounded preview fetch for visible image cards; image bytes remain local. */
    suspend fun thumbnailFor(itemId: String): android.graphics.Bitmap? {
        val asset = repository.assetForItem(itemId) ?: return null
        return kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            repository.decodeAssetThumbnail(asset.fileName, maxEdgePx = 256)
        }
    }

    data class LocalUiState(
        val ready: Boolean = false,
        val fatalError: String? = null,
        val items: List<LocalItem> = emptyList(),
        val safes: List<LocalSafe> = emptyList(),
        val safeCounts: Map<String, Int> = emptyMap(),
        val activity: List<LocalActivityEvent> = emptyList(),
        val query: String = "",
        val filter: LocalFilter = LocalFilter.ALL,
        /** null = all items; otherwise the Safe id currently scoped into view. */
        val selectedSafeId: String? = null,
        val selectedItem: LocalItem? = null,
        val selectedAsset: LocalAsset? = null,
        val busy: Boolean = false,
        val transientMessage: String? = null,
        /** Item ids whose sensitive content was deliberately revealed this session. */
        val revealed: Set<String> = emptySet(),
    )

    private val _state = MutableStateFlow(LocalUiState())
    val state: StateFlow<LocalUiState> = _state.asStateFlow()

    /**
     * Monotonic query generation — a slower, older search can never overwrite
     * a newer result set.
     */
    @Volatile
    private var searchGeneration = 0

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            try {
                val items = visibleItems()
                val safes = repository.safes()
                val counts = repository.countBySafe()
                val activity = repository.activity()
                // Re-resolve the open detail against repository truth — a stale
                // snapshot must never outlive a mutation (move/remove/restore)
                // or an external write (share-sheet save while UI was paused).
                val selected = _state.value.selectedItem
                val resolvedSelected = selected?.let { repository.item(it.id) }
                val resolvedAsset = if (resolvedSelected?.kind == LocalItemKind.IMAGE) {
                    repository.assetForItem(resolvedSelected.id)
                } else {
                    null
                }
                _state.update {
                    it.copy(
                        ready = true,
                        fatalError = null,
                        items = items,
                        safes = safes,
                        safeCounts = counts,
                        activity = activity,
                        selectedItem = resolvedSelected,
                        selectedAsset = resolvedAsset,
                        transientMessage = if (selected != null && resolvedSelected == null) {
                            "That item is no longer in this phone's vault."
                        } else {
                            it.transientMessage
                        },
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(ready = false, fatalError = messageFor(e)) }
            }
        }
    }

    fun setQuery(query: String) {
        val generation = ++searchGeneration
        _state.update { it.copy(query = query) }
        viewModelScope.launch {
            try {
                val results = repository.search(
                    query = query,
                    filter = _state.value.filter,
                    safeId = _state.value.selectedSafeId,
                )
                if (generation == searchGeneration) {
                    _state.update { it.copy(items = results, fatalError = null) }
                }
            } catch (e: Exception) {
                if (generation == searchGeneration) {
                    _state.update { it.copy(transientMessage = messageFor(e)) }
                }
            }
        }
    }

    fun setFilter(filter: LocalFilter) {
        _state.update { it.copy(filter = filter) }
        reloadItems()
    }

    fun selectSafe(safeId: String?) {
        _state.update { it.copy(selectedSafeId = safeId) }
        reloadItems()
    }

    private fun reloadItems() {
        val generation = ++searchGeneration
        viewModelScope.launch {
            try {
                val results = visibleItems()
                if (generation == searchGeneration) {
                    _state.update { it.copy(items = results) }
                }
            } catch (e: Exception) {
                if (generation == searchGeneration) {
                    _state.update { it.copy(transientMessage = messageFor(e)) }
                }
            }
        }
    }

    private suspend fun visibleItems(): List<LocalItem> {
        val s = _state.value
        return repository.search(query = s.query, filter = s.filter, safeId = s.selectedSafeId)
    }

    fun openItem(itemId: String) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val item = repository.item(itemId)
                val asset = if (item?.kind == LocalItemKind.IMAGE) {
                    repository.assetForItem(itemId)
                } else {
                    null
                }
                _state.update {
                    it.copy(
                        busy = false,
                        selectedItem = item,
                        selectedAsset = asset,
                        transientMessage = if (item == null) "That item is no longer in this phone's vault." else null,
                    )
                }
                if (item != null) {
                    repository.recordOpen(itemId)
                    refreshActivityIntoState()
                }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, transientMessage = messageFor(e)) }
            }
        }
    }

    fun closeItem() {
        _state.update { it.copy(selectedItem = null, selectedAsset = null) }
    }

    fun saveText(
        content: String,
        safeId: String = LocalVaultDatabase.DEFAULT_SAFE_ID,
        sourceLabel: String = "manual",
    ) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val item = LocalIngestion.saveText(repository, content, safeId, sourceLabel)
                _state.update {
                    it.copy(
                        busy = false,
                        transientMessage = "Saved on this phone",
                        items = listOf(item) + it.items,
                    )
                }
                refresh()
            } catch (e: Exception) {
                runCatching {
                    repository.recordFailedSave(LocalIngestion.failureReason(e))
                    refreshActivityIntoState()
                }
                _state.update { it.copy(busy = false, transientMessage = messageFor(e)) }
            }
        }
    }

    fun saveImage(
        declaredMime: String?,
        displayName: String?,
        safeId: String,
        openStream: () -> InputStream?,
    ) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val item = LocalIngestion.saveImage(repository, declaredMime, displayName, safeId, openStream)
                _state.update {
                    it.copy(
                        busy = false,
                        transientMessage = "Image saved on this phone",
                        items = listOf(item) + it.items,
                    )
                }
                refresh()
            } catch (e: Exception) {
                runCatching {
                    repository.recordFailedSave(LocalIngestion.failureReason(e))
                    refreshActivityIntoState()
                }
                _state.update { it.copy(busy = false, transientMessage = messageFor(e)) }
            }
        }
    }

    fun toggleFavorite(item: LocalItem) {
        mutate(
            action = { repository.setFavorite(item.id, !item.isFavorite) },
            message = if (item.isFavorite) "Removed from favorites" else "Marked favorite",
        )
    }

    fun moveToSafe(itemId: String, safeId: String) {
        mutate(action = { repository.moveToSafe(itemId, safeId) }, message = "Moved to Safe")
    }

    fun removeItem(itemId: String) {
        mutate(action = { repository.removeItem(itemId) }, message = "Moved to Recently Removed")
    }

    fun restoreItem(itemId: String) {
        mutate(action = { repository.restoreItem(itemId) }, message = "Restored on this phone")
    }

    fun createSafe(name: String) {
        mutate(action = { repository.createSafe(name) }, message = "Safe created on this phone")
    }

    fun renameSafe(safeId: String, name: String) {
        mutate(action = { repository.renameSafe(safeId, name) }, message = "Safe renamed")
    }

    /** Call only after the clipboard write has actually been performed. */
    fun markCopied(itemId: String) {
        viewModelScope.launch {
            runCatching {
                repository.recordCopy(itemId)
                refreshActivityIntoState()
            }
        }
    }

    /** A chooser being opened is recorded as initiated — not delivered. */
    fun markShareInitiated(itemId: String) {
        viewModelScope.launch {
            runCatching {
                repository.recordShareInitiated(itemId)
                refreshActivityIntoState()
            }
        }
    }

    fun reveal(itemId: String) {
        _state.update { it.copy(revealed = it.revealed + itemId) }
        viewModelScope.launch {
            runCatching {
                repository.recordReveal(itemId)
                refreshActivityIntoState()
            }
        }
    }

    fun consumeMessage() {
        _state.update { it.copy(transientMessage = null) }
    }

    private fun mutate(action: suspend () -> Unit, message: String) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                action()
                refresh()
                _state.update { it.copy(busy = false, transientMessage = message) }
            } catch (e: Exception) {
                _state.update { it.copy(busy = false, transientMessage = messageFor(e)) }
            }
        }
    }

    /** Merge the freshly written ledger into state so the Activity tab stays current. */
    private suspend fun refreshActivityIntoState() {
        val activity = repository.activity()
        _state.update { it.copy(activity = activity) }
    }

    private fun messageFor(e: Throwable): String =
        (e as? LocalVaultError)?.message ?: "Something went wrong in the local vault."
}
