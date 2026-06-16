package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.prooffoundry.cachevaultmobile.connect.ConnectionPlanner
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcFoundOffer
import com.prooffoundry.cachevaultmobile.connect.PcOfferMode
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
    val pcFoundOffer: PcFoundOffer? = null,
    val showNoPcFound: Boolean = false,
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

    fun discoverPcOnLaunch() {
        if (repository.isPaired()) return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, showNoPcFound = false)
            runCatching {
                withContext(Dispatchers.IO) { repository.discoverPc() }
            }.onSuccess { pc ->
                uiState = uiState.copy(loading = false)
                if (pc != null) {
                    uiState = uiState.copy(pcFoundOffer = buildOffer(pc, null))
                } else {
                    uiState = uiState.copy(showNoPcFound = true)
                }
            }.onFailure {
                uiState = uiState.copy(loading = false, showNoPcFound = true)
            }
        }
    }

    fun dismissPcOffer() {
        uiState = uiState.copy(pcFoundOffer = null, showNoPcFound = false)
    }

    fun connectOfferedPc(onSuccess: () -> Unit) {
        val offer = uiState.pcFoundOffer ?: return
        val pairing = repository.loadPairing()
        if (pairing == null || offer.mode == PcOfferMode.NO_TOKEN) {
            uiState = uiState.copy(pcFoundOffer = offer.copy(mode = PcOfferMode.NO_TOKEN))
            return
        }
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) { repository.verifyConnection(pairing) }
            }.onSuccess { status ->
                uiState = uiState.copy(
                    paired = true,
                    status = status,
                    hostLabel = offer.host,
                    loading = false,
                    pcFoundOffer = null,
                    error = null,
                )
                refreshClips()
                onSuccess()
            }.onFailure { err ->
                val mode = if (ConnectionPlanner.isRepairNeeded(err)) {
                    PcOfferMode.REPAIR_NEEDED
                } else {
                    offer.mode
                }
                uiState = uiState.copy(
                    loading = false,
                    pcFoundOffer = offer.copy(mode = mode),
                    error = err.toUserMessage(),
                )
            }
        }
    }

    private fun buildOffer(pc: DiscoveredPc, lastError: BridgeError?): PcFoundOffer {
        val hasPairing = repository.isPaired()
        return PcFoundOffer(
            displayName = pc.displayName,
            host = pc.host,
            port = pc.port,
            mode = ConnectionPlanner.offerMode(hasPairing, lastError),
        )
    }

    fun pair(host: String, port: Int, deviceId: String, token: String, onSuccess: () -> Unit) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                val config = PairingConfig.sanitize(host, port, deviceId, token)
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
                if (ConnectionPlanner.isRepairNeeded(err)) {
                    val host = repository.loadPairing()?.host.orEmpty()
                    if (host.isNotBlank()) {
                        uiState = uiState.copy(
                            pcFoundOffer = PcFoundOffer(
                                displayName = "Cache Vault PC",
                                host = host,
                                port = repository.loadPairing()?.port ?: PairingStore.DEFAULT_PORT,
                                mode = PcOfferMode.REPAIR_NEEDED,
                            ),
                        )
                    }
                }
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

    private fun Throwable.toUserMessage(): String = when {
        this is BridgeError -> UserMessages.forBridgeError(this)
        message?.contains("Unexpected char", ignoreCase = true) == true ->
            "Pairing token looks invalid.\nPaste only the token line, or use Copy Token on your PC."
        else -> message ?: UserMessages.PC_UNREACHABLE
    }
}
