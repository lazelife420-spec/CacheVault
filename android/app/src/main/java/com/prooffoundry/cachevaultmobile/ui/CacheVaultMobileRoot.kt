package com.prooffoundry.cachevaultmobile.ui

import android.content.Context
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcDiscovery
import com.prooffoundry.cachevaultmobile.connect.WifiSettingsHelper
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.ui.screens.ClipDetailScreen
import com.prooffoundry.cachevaultmobile.ui.screens.DiscoverPcScreen
import com.prooffoundry.cachevaultmobile.ui.screens.EasyConnectScreen
import com.prooffoundry.cachevaultmobile.ui.screens.HomeScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ManualSetupScreen
import com.prooffoundry.cachevaultmobile.ui.screens.QrScanScreen
import com.prooffoundry.cachevaultmobile.ui.screens.SettingsScreen
import com.prooffoundry.cachevaultmobile.ui.screens.WelcomeScreen
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object Routes {
    const val Welcome = "welcome"
    const val EasyConnect = "easy_connect"
    const val Discover = "discover"
    const val ManualSetup = "manual_setup"
    const val QrScan = "qr_scan"
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
    val context = LocalContext.current
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
    var manualHost by remember { mutableStateOf("") }
    var manualPort by remember { mutableStateOf<Int?>(null) }
    val start = if (pairingStore.isPaired()) Routes.Home else Routes.Welcome

    fun goHomeAfterPair() {
        nav.navigate(Routes.Home) {
            popUpTo(Routes.Welcome) { inclusive = true }
        }
    }

    NavHost(navController = nav, startDestination = start, modifier = Modifier.fillMaxSize()) {
        composable(Routes.Welcome) {
            WelcomeScreen(
                onConnectToPc = { nav.navigate(Routes.EasyConnect) },
                onScanQr = { nav.navigate(Routes.QrScan) },
                onFindPc = { nav.navigate(Routes.Discover) },
                onManualSetup = {
                    manualHost = ""
                    manualPort = null
                    nav.navigate(Routes.ManualSetup)
                },
            )
        }
        composable(Routes.EasyConnect) {
            EasyConnectScreen(
                onOpenWifiSettings = { WifiSettingsHelper.openWifiSettings(context) },
                onSameWifi = { nav.navigate(Routes.Discover) },
                onManualSetup = {
                    manualHost = ""
                    manualPort = null
                    nav.navigate(Routes.ManualSetup)
                },
                onBack = { nav.popBackStack() },
            )
        }
        composable(Routes.Discover) {
            DiscoverRoute(
                context = context,
                onConnect = { pc ->
                    manualHost = pc.host
                    manualPort = pc.port
                    nav.navigate(Routes.ManualSetup)
                },
                onManualSetup = {
                    manualHost = ""
                    manualPort = null
                    nav.navigate(Routes.ManualSetup)
                },
                onBack = { nav.popBackStack() },
            )
        }
        composable(Routes.QrScan) {
            QrScanScreen(
                onManualSetup = { nav.navigate(Routes.ManualSetup) },
                onBack = { nav.popBackStack() },
            )
        }
        composable(Routes.ManualSetup) {
            ManualSetupScreen(
                defaultPort = PairingStore.DEFAULT_PORT,
                initialHost = manualHost,
                initialPort = manualPort,
                loading = vm.uiState.loading,
                error = vm.uiState.error,
                onPair = { host, port, deviceId, token ->
                    vm.pair(host, port, deviceId, token, ::goHomeAfterPair)
                },
                onBack = { nav.popBackStack() },
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
                    nav.navigate(Routes.Welcome) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onBack = { nav.popBackStack() },
            )
        }
    }
}

@Composable
private fun DiscoverRoute(
    context: Context,
    onConnect: (DiscoveredPc) -> Unit,
    onManualSetup: () -> Unit,
    onBack: () -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var discovered by remember { mutableStateOf<DiscoveredPc?>(null) }
    var failed by remember { mutableStateOf(false) }
    var attempt by remember { mutableStateOf(0) }

    LaunchedEffect(attempt) {
        loading = true
        failed = false
        discovered = null
        val pc = withContext(Dispatchers.IO) {
            PcDiscovery(context.applicationContext).findDesktop()
        }
        loading = false
        if (pc != null) {
            discovered = pc
        } else {
            failed = true
        }
    }

    DiscoverPcScreen(
        loading = loading,
        discovered = discovered,
        failed = failed,
        onConnect = onConnect,
        onRetry = { attempt++ },
        onManualSetup = onManualSetup,
        onBack = onBack,
    )
}
