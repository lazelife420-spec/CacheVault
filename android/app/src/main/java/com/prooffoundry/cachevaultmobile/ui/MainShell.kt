package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.sp
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

@Composable
fun MainShell(
    vm: AppViewModel,
    onOpenClip: (String) -> Unit,
    onDisconnect: () -> Unit,
    onRePair: () -> Unit,
    onKeepConnectedChanged: (Boolean) -> Unit,
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

    Scaffold(
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.background) {
                MainTab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = state.mainTab == tab,
                        onClick = {
                            settingsSubRoute = null
                            vm.setMainTab(tab)
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = {
                            Text(
                                tab.label,
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
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
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
                    onOpenClip = onOpenClip,
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
                            onBack = null,
                        )
                    }
                }
            }
        }
    }
}
