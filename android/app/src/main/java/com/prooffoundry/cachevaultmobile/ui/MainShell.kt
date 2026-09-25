package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.ui.screens.BrowseScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ConnectionDoctorScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ProofScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ScreenshotsScreen
import com.prooffoundry.cachevaultmobile.ui.screens.SettingsScreen
import com.prooffoundry.cachevaultmobile.ui.screens.VaultHomeScreen
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

/**
 * The paired-PC companion surface (CV-MOBILE-1 M1-E). Rendered inside the
 * local shell's "Paired PC" tab — remote content stays visibly remote. With
 * no pairing this section is a deliberate entry point into the existing
 * pairing flows, not a launch gate.
 */
@Composable
fun PairedPcSection(
    vm: AppViewModel,
    onOpenClip: (String) -> Unit,
    onOpenImage: (com.prooffoundry.cachevaultmobile.data.ClipSummary, List<com.prooffoundry.cachevaultmobile.data.ClipSummary>) -> Unit,
    onDisconnect: () -> Unit,
    onRePair: () -> Unit,
    onKeepConnectedChanged: (Boolean) -> Unit,
    onPairScanQr: () -> Unit,
    onPairFindPc: () -> Unit,
    onPairManualSetup: () -> Unit,
    onPairGuided: () -> Unit,
    onVaultLockSettings: () -> Unit = {},
) {
    val state = vm.uiState
    var settingsSubRoute by rememberSaveable { mutableStateOf<String?>(null) }
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                vm.refreshOnResume()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    if (!state.paired) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(12.dp),
        ) {
            Text("Paired PC", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                "No PC is paired to this phone. Your phone vault works on its own — " +
                    "pairing only adds browsing and sending to your PC.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = onPairGuided, modifier = Modifier.fillMaxWidth()) {
                Text("Set up pairing (guided)")
            }
            OutlinedButton(onClick = onPairScanQr, modifier = Modifier.fillMaxWidth()) {
                Text("Scan pairing QR", color = ProofTeal)
            }
            OutlinedButton(onClick = onPairFindPc, modifier = Modifier.fillMaxWidth()) {
                Text("Find PC on this Wi-Fi", color = ProofTeal)
            }
            OutlinedButton(onClick = onPairManualSetup, modifier = Modifier.fillMaxWidth()) {
                Text("Manual setup", color = ProofTeal)
            }
            Text(
                "Remote items always say “On PC”. Nothing on this screen is stored in your phone vault automatically.",
                style = MaterialTheme.typography.labelSmall,
                color = StampGold.copy(alpha = 0.85f),
            )
        }
        return
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.padding(horizontal = 14.dp)) {
            Text(
                "Paired PC · ${state.hostLabel.ifBlank { "your PC" }}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                connectionSubtitle(
                    resolveConnectionState(state.status, state.error, state.loading, state.hasLoadedVault),
                    state.hostLabel,
                ),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        LazyRow(
            modifier = Modifier.padding(vertical = 8.dp),
            contentPadding = PaddingValues(horizontal = 14.dp),
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(6.dp),
        ) {
            items(MainTab.entries.toList(), key = { it.name }) { t ->
                RemoteTabChip(
                    label = t.label,
                    selected = state.mainTab == t,
                    onClick = {
                        settingsSubRoute = null
                        vm.setMainTab(t)
                    },
                )
            }
        }
        Box(modifier = Modifier.fillMaxSize()) {
            when (state.mainTab) {
                MainTab.VAULT -> VaultHomeScreen(
                    state = state,
                    onSearch = vm::setVaultSearchQuery,
                    onRefresh = vm::refreshAll,
                    onOpenClip = onOpenClip,
                    onBrowseAll = { vm.openBrowse(BrowseFilter.ALL) },
                    onSection = vm::openVaultSection,
                    onRePair = onRePair,
                )
                MainTab.BROWSE -> BrowseScreen(
                    state = state,
                    onSearch = vm::setBrowseSearchQuery,
                    onFilter = vm::setBrowseFilter,
                    onRefresh = vm::refreshBrowseClips,
                    onOpenClip = onOpenClip,
                )
                MainTab.IMAGES -> ScreenshotsScreen(
                    state = state,
                    onRefresh = vm::refreshAll,
                    onOpenImage = onOpenImage,
                )
                MainTab.PROOF -> ProofScreen(
                    state = state,
                    onRefresh = vm::refreshAll,
                    onOpenSettings = { vm.setMainTab(MainTab.SETTINGS) },
                    onCopyDiagnostics = vm::diagnosticsText,
                )
                MainTab.SETTINGS -> {
                    if (settingsSubRoute == "doctor") {
                        ConnectionDoctorScreen(
                            info = vm.connectionDoctor(),
                            onBack = { settingsSubRoute = null },
                        )
                    } else {
                        SettingsScreen(
                            pcName = state.pcName,
                            host = state.hostLabel,
                            port = state.port,
                            deviceId = state.deviceId,
                            lastSeenAt = state.lastSeenAt,
                            autoConnectApproved = state.autoConnectApproved,
                            keepConnectedInBackground = state.keepConnectedInBackground,
                            status = state.status,
                            error = state.error,
                            lastError = state.lastError,
                            hasLoadedVault = state.hasLoadedVault,
                            loading = state.loading,
                            onDisconnect = onDisconnect,
                            onRePair = onRePair,
                            onReconnect = { vm.refreshAll() },
                            onAutoConnectApproved = vm::approveAutoConnect,
                            onKeepConnectedChanged = onKeepConnectedChanged,
                            onConnectionDoctor = { settingsSubRoute = "doctor" },
                            onVaultLockSettings = onVaultLockSettings,
                            onBack = null,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RemoteTabChip(label: String, selected: Boolean, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(20.dp),
        color = if (selected) ProofTeal.copy(alpha = 0.18f) else MaterialTheme.colorScheme.surface,
        modifier = Modifier.height(34.dp),
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
            color = if (selected) ProofTeal else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
