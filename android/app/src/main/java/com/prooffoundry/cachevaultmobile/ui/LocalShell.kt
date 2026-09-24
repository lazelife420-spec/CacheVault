package com.prooffoundry.cachevaultmobile.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Lock
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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
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
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.background) {
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
            when (LocalTab.valueOf(tab)) {
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
                )
                LocalTab.SAFES -> LocalSafesScreen(
                    state = state,
                    onSelectSafe = { safeId ->
                        localVm.selectSafe(safeId)
                        localVm.setFilter(LocalFilter.ALL)
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

    if (showAddSheet) {
        ModalBottomSheet(onDismissRequest = { showAddSheet = false }) {
            Column(modifier = Modifier.padding(bottom = 24.dp)) {
                TextButton(
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
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                ) { Text("Paste from clipboard") }
                TextButton(
                    onClick = {
                        showAddSheet = false
                        editorText = ""
                        showTextEditor = true
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                ) { Text("Type or paste text") }
                TextButton(
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
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                ) { Text("Add an image") }
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
