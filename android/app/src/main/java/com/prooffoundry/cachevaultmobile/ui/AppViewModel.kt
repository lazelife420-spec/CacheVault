package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.prooffoundry.cachevaultmobile.data.BridgeError
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import com.prooffoundry.cachevaultmobile.data.ClipFeed
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.data.ImageAssetState
import com.prooffoundry.cachevaultmobile.data.PairingConfig
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.data.UserMessages
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class AppUiState(
    val paired: Boolean = false,
    val status: BridgeStatus? = null,
    val hostLabel: String = "",
    val clips: List<ClipSummary> = emptyList(),
    val collections: List<com.prooffoundry.cachevaultmobile.data.CollectionEntry> = emptyList(),
    val selectedCollection: String? = null,
    val searchQuery: String = "",
    val activeFeed: ClipFeed = ClipFeed.ALL,
    val loading: Boolean = false,
    val error: String? = null,
    val selectedClip: ClipSummary? = null,
    val imageAsset: ImageAssetState = ImageAssetState(),
)

class AppViewModel(
    private val repository: BridgeRepository,
) : ViewModel() {
    var uiState by mutableStateOf(AppUiState(paired = repository.isPaired()))
        private set

    init {
        if (repository.isPaired()) {
            refreshAll()
        }
    }

    fun pair(host: String, port: Int, deviceId: String, token: String, onSuccess: () -> Unit) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                val config = PairingConfig(host, port, deviceId, token)
                val status = withContext(Dispatchers.IO) {
                    repository.verifyConnection(config)
                }
                status
            }.onSuccess { status ->
                uiState = uiState.copy(
                    paired = true,
                    status = status,
                    hostLabel = host,
                    loading = false,
                    error = null,
                )
                refreshClips()
                onSuccess()
            }.onFailure { err ->
                uiState = uiState.copy(
                    loading = false,
                    error = err.toUserMessage(),
                )
            }
        }
    }

    fun disconnect() {
        repository.disconnect()
        uiState = AppUiState(paired = false)
    }

    fun refreshAll() {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) {
                    val client = repository.client()
                    val status = client.status()
                    val collections = client.listCollections().collections
                    Triple(status, collections, repository.loadPairing()?.host.orEmpty())
                }
            }.onSuccess { (status, collections, host) ->
                uiState = uiState.copy(
                    paired = true,
                    status = status,
                    collections = collections,
                    hostLabel = host,
                    loading = false,
                )
                refreshClips()
            }.onFailure { err ->
                uiState = uiState.copy(loading = false, error = err.toUserMessage())
            }
        }
    }

    fun setSearchQuery(query: String) {
        uiState = uiState.copy(searchQuery = query)
        if (query.isBlank()) {
            refreshClips()
        } else {
            viewModelScope.launch {
                uiState = uiState.copy(loading = true, error = null)
                runCatching {
                    withContext(Dispatchers.IO) { repository.client().search(query).clips }
                }.onSuccess { clips ->
                    uiState = uiState.copy(clips = clips, loading = false)
                }.onFailure { err ->
                    uiState = uiState.copy(loading = false, error = err.toUserMessage())
                }
            }
        }
    }

    fun setFeed(feed: ClipFeed, collection: String? = null) {
        uiState = uiState.copy(activeFeed = feed, selectedCollection = collection, searchQuery = "")
        refreshClips()
    }

    fun openClip(clipId: String) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) { repository.client().clipDetail(clipId).clip }
            }.onSuccess { clip ->
                uiState = uiState.copy(selectedClip = clip, loading = false)
            }.onFailure { err ->
                uiState = uiState.copy(loading = false, error = err.toUserMessage())
            }
        }
    }

    fun closeClipDetail() {
        uiState = uiState.copy(selectedClip = null, imageAsset = ImageAssetState())
    }

    fun loadImageAsset(clipId: String) {
        viewModelScope.launch {
            uiState = uiState.copy(
                imageAsset = ImageAssetState(loading = true),
                error = null,
            )
            runCatching {
                withContext(Dispatchers.IO) { repository.client().fetchImageAsset(clipId) }
            }.onSuccess { result ->
                uiState = uiState.copy(
                    imageAsset = ImageAssetState(
                        bytes = result.bytes,
                        contentType = result.contentType,
                    ),
                )
            }.onFailure { err ->
                uiState = uiState.copy(
                    imageAsset = ImageAssetState(error = err.toUserMessage()),
                )
            }
        }
    }

    fun logCopy(clipId: String) {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { repository.client().logCopy(clipId) }
            }
        }
    }

    fun logShare(clipId: String) {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { repository.client().logShare(clipId) }
            }
        }
    }

    fun logSave(clipId: String) {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { repository.client().logSave(clipId) }
            }
        }
    }

    fun logAssetOpen(clipId: String) {
        loadImageAsset(clipId)
    }

    private fun refreshClips() {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) {
                    val client = repository.client()
                    when (uiState.activeFeed) {
                        ClipFeed.ALL -> client.listClips().clips
                        ClipFeed.FAVORITES -> client.listFavorites().clips
                        ClipFeed.SCREENSHOTS -> client.listClips().clips.filter {
                            com.prooffoundry.cachevaultmobile.data.ClipKinds.isImageReference(it)
                        }
                        ClipFeed.RECENTLY_REMOVED -> client.listRecentlyRemoved().clips
                        ClipFeed.COLLECTION -> {
                            val name = uiState.selectedCollection
                            client.listClips().clips.filter { it.collection == name }
                        }
                    }
                }
            }.onSuccess { clips ->
                uiState = uiState.copy(clips = clips, loading = false)
            }.onFailure { err ->
                uiState = uiState.copy(loading = false, error = err.toUserMessage())
            }
        }
    }

    private fun Throwable.toUserMessage(): String =
        if (this is BridgeError) UserMessages.forBridgeError(this)
        else message ?: UserMessages.PC_UNREACHABLE
}
