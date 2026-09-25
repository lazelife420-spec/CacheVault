package com.prooffoundry.cachevaultmobile.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.prooffoundry.cachevaultmobile.data.local.LocalFilter
import com.prooffoundry.cachevaultmobile.data.local.LocalItem
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultDatabase
import com.prooffoundry.cachevaultmobile.ui.screens.LocalActivityScreen
import com.prooffoundry.cachevaultmobile.ui.screens.LocalSafesScreen
import com.prooffoundry.cachevaultmobile.ui.screens.LocalVaultHomeScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ConnectionDoctorScreen
import com.prooffoundry.cachevaultmobile.ui.screens.SettingsScreen

private enum class LocalTab(val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    VAULT("Vault", Icons.Default.Home),
    SAFES("Safes", Icons.Default.Lock),
    ACTIVITY("Activity", Icons.Default.History),
    PC("Paired PC", Icons.Default.Computer),
}

/**
 * Local-first application shell (CV-MOBILE-1). The phone's own vault is the
 * primary surface; the paired-PC companion lives one tab over as an explicit,
 * separately identified area. Nothing on the local tabs touches the network.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LocalShell(
    localVm: LocalVaultViewModel,
    remoteVm: AppViewModel,
    /** Tab to show first — "pc" after a successful pair, "vault" otherwise. */
    initialTab: String = "vault",
    onOpenItem: (String) -> Unit,
    onOpenClip: (String) -> Unit,
    onOpenImage: (com.prooffoundry.cachevaultmobile.data.ClipSummary, List<com.prooffoundry.cachevaultmobile.data.ClipSummary>) -> Unit,
    onDisconnect: () -> Unit,
    onRePair: () -> Unit,
    onKeepConnectedChanged: (Boolean) -> Unit,
    onPairScanQr: () -> Unit,
    onPairFindPc: () -> Unit,
    onPairManualSetup: () -> Unit,
    onPairGuided: () -> Unit,
) {
    val state by localVm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val snackbar = remember { SnackbarHostState() }

    // Refresh local vault truth whenever this shell resumes — writes can land
    // while the UI is paused (e.g. ShareAssistantActivity "Save on this
    // phone"), and the list/detail must reflect the repository on return.
    // Local reads only: no bridge, discovery, or network call is involved.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, localVm) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) localVm.refresh()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    var tab by rememberSaveable {
        mutableStateOf(
            if (initialTab.equals("pc", ignoreCase = true)) LocalTab.PC.name else LocalTab.VAULT.name,
        )
    }

    var showAddSheet by rememberSaveable { mutableStateOf(false) }
    var showTextEditor by rememberSaveable { mutableStateOf(false) }
    var editorText by rememberSaveable { mutableStateOf("") }
    var editorSafeId by rememberSaveable { mutableStateOf(LocalVaultDatabase.DEFAULT_SAFE_ID) }
    var showSettings by rememberSaveable { mutableStateOf(false) }
    var showConnectionDoctor by rememberSaveable { mutableStateOf(false) }

    BackHandler(enabled = showConnectionDoctor || showSettings) {
        if (showConnectionDoctor) showConnectionDoctor = false else showSettings = false
    }
    BackHandler(enabled = !showSettings && tab != LocalTab.VAULT.name) {
        tab = LocalTab.VAULT.name
    }
    BackHandler(
        enabled = !showSettings && tab == LocalTab.VAULT.name &&
            (state.query.isNotBlank() || state.selectedSafeId != null || state.filter != LocalFilter.ALL),
    ) {
        when {
            state.query.isNotBlank() -> localVm.setQuery("")
            state.selectedSafeId != null -> localVm.selectSafe(null)
            else -> localVm.setFilter(LocalFilter.ALL)
        }
    }

    val imagePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        if (uri != null) {
            val mime = context.contentResolver.getType(uri)
            val name = runCatching {
                context.contentResolver.query(
                    uri,
                    arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),
                    null, null, null,
                )?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
            }.getOrNull()
            localVm.saveImage(
                declaredMime = mime,
                displayName = name,
                safeId = editorSafeId,
                openStream = { context.contentResolver.openInputStream(uri) },
            )
        }
    }
    val imagePickerFallback = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent(),
    ) { uri: Uri? ->
        if (uri != null) {
            val mime = context.contentResolver.getType(uri)
            localVm.saveImage(
                declaredMime = mime,
                displayName = null,
                safeId = editorSafeId,
                openStream = { context.contentResolver.openInputStream(uri) },
            )
        }
    }

    LaunchedEffect(state.transientMessage) {
        state.transientMessage?.let {
            snackbar.showSnackbar(it)
            localVm.consumeMessage()
        }
    }

    Scaffold(
        topBar = {
            if (!showSettings) {
                val selectedSafe = state.safes.firstOrNull { it.id == state.selectedSafeId }
                val contextLabel = when (LocalTab.valueOf(tab)) {
                    LocalTab.VAULT -> when {
                        state.filter == LocalFilter.REMOVED -> "Recently Removed · This phone"
                        selectedSafe != null -> "Safe · ${selectedSafe.name}"
                        else -> "Local vault · This phone"
                    }
                    LocalTab.SAFES -> "Organize this phone"
                    LocalTab.ACTIVITY -> "Local history"
                    LocalTab.PC -> "Remote vault · On PC"
                }
                TopAppBar(
                    title = {
                        Column {
                            Text("Cache Vault", style = MaterialTheme.typography.titleMedium)
                            Text(contextLabel, style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    },
                    navigationIcon = if (LocalTab.valueOf(tab) == LocalTab.VAULT &&
                        (state.filter == LocalFilter.REMOVED || selectedSafe != null)
                    ) {
                        {
                            IconButton(onClick = {
                                if (state.filter == LocalFilter.REMOVED) {
                                    localVm.setFilter(LocalFilter.ALL)
                                } else {
                                    localVm.selectSafe(null)
                                }
                            }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to Vault")
                            }
                        }
                    } else {
                        {}
                    },
                    actions = {
                        IconButton(onClick = {
                            showConnectionDoctor = false
                            showSettings = true
                        }) {
                            Icon(Icons.Default.Settings, contentDescription = "Settings")
                        }
                    },
                )
            }
        },
        bottomBar = {
            if (!showSettings) NavigationBar(containerColor = MaterialTheme.colorScheme.background) {
                LocalTab.entries.forEach { t ->
                    NavigationBarItem(
                        selected = tab == t.name,
                        onClick = { tab = t.name },
                        icon = { Icon(t.icon, contentDescription = t.label) },
                        label = {
                            Text(
                                t.label,
                                style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        },
                        alwaysShowLabel = true,
                    )
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            when {
                showSettings && showConnectionDoctor -> ConnectionDoctorScreen(
                    info = remoteVm.connectionDoctor(),
                    onBack = { showConnectionDoctor = false },
                )
                showSettings -> {
                    val remote = remoteVm.uiState
                    SettingsScreen(
                        pcName = remote.pcName,
                        host = remote.hostLabel,
                        port = remote.port,
                        deviceId = remote.deviceId,
                        lastSeenAt = remote.lastSeenAt,
                        autoConnectApproved = remote.autoConnectApproved,
                        keepConnectedInBackground = remote.keepConnectedInBackground,
                        status = remote.status,
                        error = remote.error,
                        lastError = remote.lastError,
                        hasLoadedVault = remote.hasLoadedVault,
                        loading = remote.loading,
                        onDisconnect = onDisconnect,
                        onRePair = onRePair,
                        onReconnect = remoteVm::refreshAll,
                        onAutoConnectApproved = remoteVm::approveAutoConnect,
                        onKeepConnectedChanged = onKeepConnectedChanged,
                        onConnectionDoctor = { showConnectionDoctor = true },
                        onBack = { showSettings = false },
                    )
                }
                else -> when (LocalTab.valueOf(tab)) {
                LocalTab.VAULT -> LocalVaultHomeScreen(
                    state = state,
                    onSearch = localVm::setQuery,
                    onFilter = localVm::setFilter,
                    onOpenItem = onOpenItem,
                    onCopyItem = { id ->
                        state.items.firstOrNull { it.id == id }?.let { item ->
                            copyLocalText(context, item)
                            localVm.markCopied(item.id)
                        }
                    },
                    onAdd = { showAddSheet = true },
                    onOpenSafes = { tab = LocalTab.SAFES.name },
                    loadThumbnail = localVm::thumbnailFor,
                )
                LocalTab.SAFES -> LocalSafesScreen(
                    state = state,
                    onSelectSafe = { safeId ->
                        localVm.selectSafe(safeId)
                        localVm.setFilter(LocalFilter.ALL)
                        localVm.setQuery("")
                        tab = LocalTab.VAULT.name
                    },
                    onCreateSafe = localVm::createSafe,
                    onRenameSafe = localVm::renameSafe,
                )
                LocalTab.ACTIVITY -> LocalActivityScreen(state = state)
                LocalTab.PC -> PairedPcSection(
                    vm = remoteVm,
                    onOpenClip = onOpenClip,
                    onOpenImage = onOpenImage,
                    onDisconnect = onDisconnect,
                    onRePair = onRePair,
                    onKeepConnectedChanged = onKeepConnectedChanged,
                    onPairScanQr = onPairScanQr,
                    onPairFindPc = onPairFindPc,
                    onPairManualSetup = onPairManualSetup,
                    onPairGuided = onPairGuided,
                )
                }
            }
        }
    }

    if (showAddSheet) {
        ModalBottomSheet(onDismissRequest = { showAddSheet = false }) {
            Column(modifier = Modifier.padding(bottom = 24.dp)) {
                Text(
                    "Save on this phone",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 6.dp),
                )
                AddSheetRow(
                    icon = Icons.Default.ContentPaste,
                    title = "Paste from clipboard",
                    subtitle = "Save what you copied",
                    onClick = {
                        showAddSheet = false
                        val clip = clipboard.getText()?.text.orEmpty()
                        if (clip.isBlank()) {
                            localVm.saveText("", editorSafeId, "paste")
                        } else {
                            editorText = clip
                            showTextEditor = true
                        }
                    },
                )
                AddSheetRow(
                    icon = Icons.Default.Edit,
                    title = "Type or paste text",
                    subtitle = "Write a note or drop in a link",
                    onClick = {
                        showAddSheet = false
                        editorText = ""
                        showTextEditor = true
                    },
                )
                AddSheetRow(
                    icon = Icons.Default.Image,
                    title = "Add an image",
                    subtitle = "Save a picture to this phone's vault",
                    onClick = {
                        showAddSheet = false
                        runCatching {
                            imagePicker.launch(
                                PickVisualMediaRequest(
                                    ActivityResultContracts.PickVisualMedia.ImageOnly,
                                ),
                            )
                        }.onFailure {
                            imagePickerFallback.launch("image/*")
                        }
                    },
                )
            }
        }
    }

    if (showTextEditor) {
        AlertDialog(
            onDismissRequest = { showTextEditor = false },
            title = { Text("Save text on this phone") },
            text = {
                Column {
                    OutlinedTextField(
                        value = editorText,
                        onValueChange = { editorText = it },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 4,
                        maxLines = 8,
                        label = { Text("Text or link") },
                    )
                    Text(
                        "Will be saved to: " +
                            (state.safes.firstOrNull { it.id == editorSafeId }?.name ?: "Default Safe"),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    enabled = editorText.isNotBlank(),
                    onClick = {
                        showTextEditor = false
                        localVm.saveText(editorText, editorSafeId, "manual")
                    },
                ) { Text("Save") }
            },
            dismissButton = {
                TextButton(onClick = { showTextEditor = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun AddSheetRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        color = androidx.compose.ui.graphics.Color.Transparent,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(22.dp),
            )
            Column(modifier = Modifier.padding(start = 16.dp)) {
                Text(title, style = MaterialTheme.typography.bodyLarge)
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private fun copyLocalText(context: android.content.Context, item: LocalItem) {
    val cm = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE)
        as android.content.ClipboardManager
    val clip = android.content.ClipData.newPlainText("Cache Vault", item.content.orEmpty())
    if (item.isSensitive && android.os.Build.VERSION.SDK_INT >= 33) {
        clip.description.extras = android.os.PersistableBundle().apply {
            putBoolean("android.content.extra.IS_SENSITIVE", true)
        }
    }
    cm.setPrimaryClip(clip)
}
