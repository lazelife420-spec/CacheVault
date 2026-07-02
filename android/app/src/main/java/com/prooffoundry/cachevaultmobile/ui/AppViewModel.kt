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
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.BridgeError
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import com.prooffoundry.cachevaultmobile.data.ClipListResponse
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.data.VaultSectionCounts
import com.prooffoundry.cachevaultmobile.data.VaultSectionKind
import com.prooffoundry.cachevaultmobile.data.ImageAssetState
import com.prooffoundry.cachevaultmobile.data.PairingConfig
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.data.UserMessages
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class VaultSummary(
    val totalClips: Int,
    val screenshotCount: Int,
    val favoriteCount: Int,
)

data class ConnectionDoctorInfo(
    val host: String,
    val port: Int,
    val deviceId: String,
    val lastError: String?,
    val connectionState: ConnectionState,
    val statusOk: Boolean,
    val suggestedFix: String,
)

data class AppUiState(
    val paired: Boolean = false,
    val status: BridgeStatus? = null,
    val pcName: String = "",
    val hostLabel: String = "",
    val deviceId: String = "",
    val port: Int = PairingStore.DEFAULT_PORT,
    val lastSeenAt: String? = null,
    val autoConnectApproved: Boolean = false,
    val keepConnectedInBackground: Boolean = false,
    val allClips: List<com.prooffoundry.cachevaultmobile.data.ClipSummary> = emptyList(),
    val removedClips: List<com.prooffoundry.cachevaultmobile.data.ClipSummary> = emptyList(),
    val clips: List<com.prooffoundry.cachevaultmobile.data.ClipSummary> = emptyList(),
    val sectionCounts: VaultSectionCounts = VaultSectionCounts(),
    val vaultSummary: VaultSummary? = null,
    val collections: List<com.prooffoundry.cachevaultmobile.data.CollectionEntry> = emptyList(),
    val selectedCollection: String? = null,
    val vaultSearchQuery: String = "",
    val browseSearchQuery: String = "",
    val browseFilter: BrowseFilter = BrowseFilter.ALL,
    val mainTab: MainTab = MainTab.VAULT,
    val loading: Boolean = false,
    val hasLoadedVault: Boolean = false,
    val error: String? = null,
    val detailError: String? = null,
    val lastError: String? = null,
    val selectedClip: com.prooffoundry.cachevaultmobile.data.ClipSummary? = null,
    val imageAsset: ImageAssetState = ImageAssetState(),
    val thumbnailBytes: Map<String, ByteArray> = emptyMap(),
    val pcFoundOffer: PcFoundOffer? = null,
    val showNoPcFound: Boolean = false,
    val pairSuccessMessage: String? = null,
)

class AppViewModel(
    private val repository: BridgeRepository,
) : ViewModel() {
    var uiState by mutableStateOf(
        AppUiState(
            paired = repository.isPaired(),
            loading = false,
            lastSeenAt = repository.loadPairing()?.lastSeenAt,
            autoConnectApproved = repository.loadPairing()?.autoConnectApproved ?: false,
            keepConnectedInBackground = repository.loadPairing()?.keepConnectedInBackground ?: false,
        ),
    )
        private set

    init {
        if (repository.isPaired()) {
            val pairing = repository.loadPairing()
            uiState = uiState.copy(
                pcName = pairing?.pcLabel.orEmpty(),
                hostLabel = pairing?.pcLabel.orEmpty().ifBlank { pairing?.host.orEmpty() },
                deviceId = pairing?.deviceId.orEmpty(),
                port = pairing?.port ?: PairingStore.DEFAULT_PORT,
            )
        }
    }

    /** Refresh vault when app returns to foreground (including first resume after cold start). */
    fun refreshOnResume() {
        if (!repository.isPaired() || uiState.loading) return
        if (!uiState.autoConnectApproved && uiState.status == null) {
            initializeConnectionLifecycle()
            return
        }
        refreshAll()
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
                val updated = pairing.copy(
                    host = offer.host,
                    port = offer.port,
                    pcLabel = offer.displayName,
                )
                withContext(Dispatchers.IO) { repository.verifyConnection(updated) }
            }.onSuccess { status ->
                val refreshedPairing = repository.loadPairing()
                uiState = uiState.copy(
                    paired = true,
                    status = status,
                    pcName = offer.displayName,
                    hostLabel = offer.displayName.ifBlank { offer.host },
                    port = offer.port,
                    loading = false,
                    pcFoundOffer = null,
                    error = null,
                    lastSeenAt = refreshedPairing?.lastSeenAt,
                    autoConnectApproved = refreshedPairing?.autoConnectApproved
                        ?: uiState.autoConnectApproved,
                    keepConnectedInBackground = refreshedPairing?.keepConnectedInBackground
                        ?: uiState.keepConnectedInBackground,
                )
                refreshVaultData()
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
        val pairing = repository.loadPairing()
        val hasPairing = pairing != null
        return PcFoundOffer(
            displayName = pc.displayName,
            host = pc.host,
            port = pc.port,
            mode = ConnectionPlanner.offerMode(
                hasStoredPairing = hasPairing,
                lastError = lastError,
                autoConnectApproved = pairing?.autoConnectApproved ?: false,
            ),
            remembered = hasPairing,
        )
    }

    fun initializeConnectionLifecycle(onAutoConnect: () -> Unit = {}) {
        val pairing = repository.loadPairing() ?: return
        if (uiState.loading) return
        uiState = uiState.copy(
            paired = true,
            pcName = pairing.pcLabel,
            hostLabel = pairing.pcLabel.ifBlank { pairing.host },
            deviceId = pairing.deviceId,
            port = pairing.port,
            lastSeenAt = pairing.lastSeenAt,
            autoConnectApproved = pairing.autoConnectApproved,
            keepConnectedInBackground = pairing.keepConnectedInBackground,
        )
        if (pairing.autoConnectApproved) {
            refreshAll(onSuccess = onAutoConnect)
            return
        }
        viewModelScope.launch {
            val pc = runCatching {
                withContext(Dispatchers.IO) { repository.discoverPc() }
            }.getOrNull()
            if (pc != null) {
                uiState = uiState.copy(
                    pcFoundOffer = buildOffer(pc, null),
                    showNoPcFound = false,
                )
            }
        }
    }

    fun approveAutoConnect(approved: Boolean) {
        repository.updateConnectionPreferences(autoConnectApproved = approved)
        uiState = uiState.copy(autoConnectApproved = approved)
    }

    fun setKeepConnectedInBackground(enabled: Boolean) {
        repository.updateConnectionPreferences(keepConnectedInBackground = enabled)
        uiState = uiState.copy(keepConnectedInBackground = enabled)
    }

    fun reportBackgroundConnectionFailure(message: String) {
        repository.updateConnectionPreferences(keepConnectedInBackground = false)
        uiState = uiState.copy(
            keepConnectedInBackground = false,
            error = message,
            lastError = message,
        )
    }

    fun pair(
        host: String,
        port: Int,
        deviceId: String,
        token: String,
        onSuccess: () -> Unit,
    ) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null, pairSuccessMessage = null)
            runCatching {
                val existing = repository.loadPairing()
                val config = PairingConfig.sanitize(
                    host = host,
                    port = port,
                    deviceId = deviceId,
                    token = token,
                    pcLabel = existing?.pcLabel.orEmpty(),
                    autoConnectApproved = existing?.autoConnectApproved ?: false,
                    keepConnectedInBackground = existing?.keepConnectedInBackground ?: false,
                )
                val status = withContext(Dispatchers.IO) {
                    repository.verifyConnection(config)
                }
                status
            }.onSuccess {
                val pairing = repository.loadPairing()
                uiState = uiState.copy(
                    paired = true,
                    status = it,
                    pcName = pairing?.pcLabel.orEmpty(),
                    hostLabel = pairing?.pcLabel.orEmpty().ifBlank { host },
                    deviceId = pairing?.deviceId.orEmpty().ifBlank { deviceId },
                    port = pairing?.port ?: port,
                    loading = false,
                    error = null,
                    pairSuccessMessage = UserMessages.PAIRING_SAVED,
                    lastSeenAt = pairing?.lastSeenAt,
                    autoConnectApproved = pairing?.autoConnectApproved ?: false,
                    keepConnectedInBackground = pairing?.keepConnectedInBackground ?: false,
                )
                refreshAll()
                onSuccess()
            }.onFailure { err ->
                uiState = uiState.copy(
                    loading = false,
                    error = err.toUserMessage(),
                    pairSuccessMessage = null,
                )
            }
        }
    }

    fun disconnect() {
        repository.disconnect()
        uiState = AppUiState(paired = false)
    }

    fun diagnosticsText(): String {
        val info = connectionDoctor()
        return buildString {
            appendLine("Cache Vault Mobile diagnostics")
            appendLine("Host: ${info.host}:${info.port}")
            appendLine("Device: ${info.deviceId}")
            appendLine("State: ${info.connectionState.label}")
            appendLine("Status ok: ${info.statusOk}")
            info.lastError?.let { appendLine("Last error: $it") }
            appendLine("Suggested fix: ${info.suggestedFix}")
        }
    }

    fun setMainTab(tab: MainTab) {
        uiState = uiState.copy(mainTab = tab)
        when (tab) {
            MainTab.VAULT -> if (repository.isPaired() && !uiState.hasLoadedVault && !uiState.loading) {
                refreshAll()
            }
            MainTab.BROWSE -> applyBrowseList()
            MainTab.IMAGES -> {
                prefetchThumbnails(VaultSections.screenshotClips(uiState.allClips))
                if (repository.isPaired() && !uiState.hasLoadedVault) refreshAll()
            }
            else -> Unit
        }
    }

    fun setBrowseFilter(filter: BrowseFilter) {
        uiState = uiState.copy(browseFilter = filter, browseSearchQuery = "")
        applyBrowseList()
    }

    fun openBrowse(filter: BrowseFilter) {
        uiState = uiState.copy(mainTab = MainTab.BROWSE, browseFilter = filter, browseSearchQuery = "")
        applyBrowseList()
    }

    fun openVaultSection(kind: VaultSectionKind) {
        when (kind) {
            VaultSectionKind.TEXT -> openBrowse(BrowseFilter.TEXT)
            VaultSectionKind.LINKS -> openBrowse(BrowseFilter.LINKS)
            VaultSectionKind.CODE -> openBrowse(BrowseFilter.CODE)
            VaultSectionKind.COMMANDS -> openBrowse(BrowseFilter.COMMANDS)
            VaultSectionKind.FAVORITES -> openBrowse(BrowseFilter.FAVORITES)
            VaultSectionKind.RECENT -> openBrowse(BrowseFilter.ALL)
            VaultSectionKind.SENSITIVE -> openBrowse(BrowseFilter.SENSITIVE)
            VaultSectionKind.REMOVED -> openBrowse(BrowseFilter.REMOVED)
            VaultSectionKind.SCREENSHOTS -> setMainTab(MainTab.IMAGES)
            VaultSectionKind.PROOF -> setMainTab(MainTab.PROOF)
        }
    }

    fun setVaultSearchQuery(query: String) {
        uiState = uiState.copy(vaultSearchQuery = query)
    }

    fun submitVaultSearch() {
        val query = uiState.vaultSearchQuery.trim()
        uiState = uiState.copy(
            mainTab = MainTab.BROWSE,
            browseSearchQuery = query,
            browseFilter = BrowseFilter.ALL,
        )
        if (query.isBlank()) {
            applyBrowseList()
        } else {
            searchBrowse(query)
        }
    }

    fun setBrowseSearchQuery(query: String) {
        uiState = uiState.copy(browseSearchQuery = query)
        if (query.isBlank()) {
            applyBrowseList()
        } else {
            searchBrowse(query)
        }
    }

    fun refreshBrowseClips() {
        if (uiState.browseSearchQuery.isNotBlank()) {
            searchBrowse(uiState.browseSearchQuery)
        } else {
            applyBrowseList()
        }
    }

    private fun searchBrowse(query: String) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) { repository.client().search(query).clips }
            }.onSuccess { clips ->
                uiState = uiState.copy(clips = clips, loading = false)
                prefetchThumbnails(clips)
            }.onFailure { err ->
                val msg = err.toUserMessage()
                uiState = uiState.copy(loading = false, error = msg, lastError = msg)
            }
        }
    }

    private fun applyBrowseList() {
        val filtered = VaultSections.filterClips(
            uiState.allClips,
            uiState.browseFilter,
            uiState.removedClips,
        )
        uiState = uiState.copy(clips = filtered)
        prefetchThumbnails(filtered)
    }

    private fun refreshVaultData() {
        applyBrowseList()
        if (uiState.mainTab == MainTab.IMAGES) {
            prefetchThumbnails(VaultSections.screenshotClips(uiState.allClips))
        }
    }

    fun connectionDoctor(): ConnectionDoctorInfo {
        val pairing = repository.loadPairing()
        val state = resolveConnectionState(uiState.status, uiState.error, uiState.loading, uiState.hasLoadedVault)
        val fix = when (state) {
            ConnectionState.REVOKED ->
                "Generate a fresh pairing code on your PC, then tap Disconnect / Re-pair on this phone."
            ConnectionState.REPAIR_NEEDED ->
                "Your phone reached the PC, but the token was rejected. Copy Token on the PC and re-pair."
            ConnectionState.MOBILE_ACCESS_OFF ->
                "Turn on Mobile Access in Cache Vault on your PC."
            ConnectionState.OFFLINE ->
                "Use the same Wi-Fi as your PC, open Cache Vault on the PC, turn on Mobile Access, then tap Retry."
            ConnectionState.CONNECTED -> "Connection looks good. If a clip fails, refresh the vault list."
            ConnectionState.CHECKING -> "Wait for the status check to finish, then try Refresh."
        }
        return ConnectionDoctorInfo(
            host = pairing?.host.orEmpty().ifBlank { uiState.hostLabel },
            port = pairing?.port ?: uiState.port,
            deviceId = pairing?.deviceId.orEmpty().ifBlank { uiState.deviceId },
            lastError = uiState.lastError ?: uiState.error,
            connectionState = state,
            statusOk = uiState.status != null && uiState.error.isNullOrBlank(),
            suggestedFix = fix,
        )
    }

    fun refreshAll(onSuccess: (() -> Unit)? = null) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                withContext(Dispatchers.IO) {
                    val client = repository.client()
                    val status = client.status()
                    val collections = client.listCollections().collections
                    val pairing = repository.loadPairing()
                    val all = client.listClips()
                    val removed = runCatching { client.listRecentlyRemoved() }
                        .getOrElse { ClipListResponse(emptyList(), 0) }
                    val summary = VaultSummary(
                        totalClips = all.count,
                        screenshotCount = all.clips.count {
                            ClipKinds.isImageReference(it) && it.hasAsset
                        },
                        favoriteCount = all.clips.count { it.isFavorite },
                    )
                    VaultRefreshPayload(
                        status = status,
                        collections = collections,
                        host = pairing?.host.orEmpty(),
                        deviceId = pairing?.deviceId.orEmpty(),
                        port = pairing?.port ?: PairingStore.DEFAULT_PORT,
                        allClips = all.clips,
                        removedClips = removed.clips,
                        summary = summary,
                    )
                }
            }.onSuccess { payload ->
                uiState = uiState.copy(
                    paired = true,
                    status = payload.status,
                    pcName = repository.loadPairing()?.pcLabel.orEmpty(),
                    collections = payload.collections,
                    hostLabel = payload.host,
                    deviceId = payload.deviceId.ifBlank { payload.status.deviceId },
                    port = payload.port,
                    allClips = payload.allClips,
                    removedClips = payload.removedClips,
                    sectionCounts = VaultSections.computeCounts(payload.allClips, payload.removedClips),
                    vaultSummary = payload.summary,
                    loading = false,
                    hasLoadedVault = true,
                    error = null,
                    lastError = null,
                    lastSeenAt = repository.loadPairing()?.lastSeenAt,
                    autoConnectApproved = repository.loadPairing()?.autoConnectApproved
                        ?: uiState.autoConnectApproved,
                    keepConnectedInBackground = repository.loadPairing()?.keepConnectedInBackground
                        ?: uiState.keepConnectedInBackground,
                )
                refreshVaultData()
                onSuccess?.invoke()
            }.onFailure { err ->
                val msg = err.toUserMessage()
                uiState = uiState.copy(
                    loading = false,
                    hasLoadedVault = true,
                    error = msg,
                    lastError = msg,
                    status = null,
                    clips = emptyList(),
                )
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

    fun setSearchQuery(query: String) = setBrowseSearchQuery(query)

    fun setFeed(@Suppress("UNUSED_PARAMETER") feed: com.prooffoundry.cachevaultmobile.data.ClipFeed, collection: String? = null) {
        uiState = uiState.copy(selectedCollection = collection)
        openBrowse(BrowseFilter.ALL)
    }

    fun openClip(clipId: String) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, detailError = null)
            runCatching {
                withContext(Dispatchers.IO) { repository.client().clipDetail(clipId).clip }
            }.onSuccess { clip ->
                uiState = uiState.copy(
                    selectedClip = clip,
                    loading = false,
                    imageAsset = ImageAssetState(),
                )
                if (ClipKinds.isImageReference(clip) && clip.hasAsset) {
                    loadImageAsset(clip.id)
                }
            }.onFailure { err ->
                uiState = uiState.copy(loading = false, detailError = err.toUserMessage())
            }
        }
    }

    fun closeClipDetail() {
        uiState = uiState.copy(selectedClip = null, imageAsset = ImageAssetState(), detailError = null)
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

    private fun prefetchThumbnails(clips: List<ClipSummary>) {
        val imageClips = clips.filter { ClipKinds.isImageReference(it) && it.hasAsset }.take(12)
        if (imageClips.isEmpty()) return
        viewModelScope.launch {
            val loaded = mutableMapOf<String, ByteArray>()
            runCatching {
                withContext(Dispatchers.IO) {
                    val client = repository.client()
                    for (clip in imageClips) {
                        if (uiState.thumbnailBytes.containsKey(clip.id)) {
                            uiState.thumbnailBytes[clip.id]?.let { loaded[clip.id] = it }
                            continue
                        }
                        runCatching {
                            client.fetchImageAsset(clip.id).bytes
                        }.onSuccess { bytes ->
                            loaded[clip.id] = bytes
                        }
                    }
                }
            }
            if (loaded.isNotEmpty()) {
                uiState = uiState.copy(
                    thumbnailBytes = uiState.thumbnailBytes + loaded,
                )
            }
        }
    }

    private fun Throwable.toUserMessage(): String = when {
        this is BridgeError -> UserMessages.forBridgeError(this)
        message?.contains("Unexpected char", ignoreCase = true) == true ->
            "Pairing token looks invalid.\nPaste only the token line, or use Copy Token on your PC."
        else -> message ?: UserMessages.PC_UNREACHABLE
    }

    private data class VaultRefreshPayload(
        val status: BridgeStatus,
        val collections: List<com.prooffoundry.cachevaultmobile.data.CollectionEntry>,
        val host: String,
        val deviceId: String,
        val port: Int,
        val allClips: List<com.prooffoundry.cachevaultmobile.data.ClipSummary>,
        val removedClips: List<com.prooffoundry.cachevaultmobile.data.ClipSummary>,
        val summary: VaultSummary,
    )
}
