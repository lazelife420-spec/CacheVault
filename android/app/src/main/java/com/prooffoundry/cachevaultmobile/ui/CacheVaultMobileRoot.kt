package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.ui.screens.ClipDetailScreen
import com.prooffoundry.cachevaultmobile.ui.screens.HomeScreen
import com.prooffoundry.cachevaultmobile.ui.screens.PairScreen
import com.prooffoundry.cachevaultmobile.ui.screens.SettingsScreen

object Routes {
    const val Pair = "pair"
    const val Home = "home"
    const val Settings = "settings"
    const val Detail = "detail"
}

@Composable
fun CacheVaultMobileRoot(
    pairingStore: PairingStore,
    bridgeRepository: BridgeRepository,
) {
    val nav = rememberNavController()
    val vm: AppViewModel = viewModel(
        factory = remember(bridgeRepository) {
            object : androidx.lifecycle.ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T {
                    return AppViewModel(bridgeRepository) as T
                }
            }
        },
    )
    val start = if (pairingStore.isPaired()) Routes.Home else Routes.Pair

    NavHost(navController = nav, startDestination = start, modifier = Modifier.fillMaxSize()) {
        composable(Routes.Pair) {
            PairScreen(
                defaultPort = PairingStore.DEFAULT_PORT,
                loading = vm.uiState.loading,
                error = vm.uiState.error,
                onPair = { host, port, deviceId, token ->
                    vm.pair(host, port, deviceId, token) {
                        nav.navigate(Routes.Home) {
                            popUpTo(Routes.Pair) { inclusive = true }
                        }
                    }
                },
            )
        }
        composable(Routes.Home) {
            HomeScreen(
                state = vm.uiState,
                onSearch = vm::setSearchQuery,
                onFeed = vm::setFeed,
                onOpenClip = { clipId ->
                    vm.openClip(clipId)
                    nav.navigate(Routes.Detail)
                },
                onSettings = { nav.navigate(Routes.Settings) },
                onRefresh = vm::refreshAll,
            )
        }
        composable(Routes.Detail) {
            val clip = vm.uiState.selectedClip
            if (clip != null) {
                ClipDetailScreen(
                    clip = clip,
                    onBack = {
                        vm.closeClipDetail()
                        nav.popBackStack()
                    },
                    onCopy = { vm.logCopy(clip.id) },
                    onShare = { vm.logShare(clip.id) },
                )
            }
        }
        composable(Routes.Settings) {
            SettingsScreen(
                host = vm.uiState.hostLabel,
                status = vm.uiState.status,
                onDisconnect = {
                    vm.disconnect()
                    nav.navigate(Routes.Pair) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onBack = { nav.popBackStack() },
            )
        }
    }
}
