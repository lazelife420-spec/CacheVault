package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcDiscovery
import com.prooffoundry.cachevaultmobile.connect.WifiSettingsHelper
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.ui.screens.ClipDetailScreen
import com.prooffoundry.cachevaultmobile.ui.screens.DiscoverPcScreen
import com.prooffoundry.cachevaultmobile.ui.screens.EasyConnectScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ManualSetupScreen
import com.prooffoundry.cachevaultmobile.ui.screens.PcFoundBottomSheet
import com.prooffoundry.cachevaultmobile.ui.screens.QrScanScreen
import com.prooffoundry.cachevaultmobile.ui.MainShell
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
    const val ConnectionDoctor = "connection_doctor"
    const val Detail = "detail"
}

@Composable
fun CacheVaultMobileRoot(
    pairingStore: PairingStore,
    bridgeRepository: BridgeRepository,
    manualSetupPrefill: ManualSetupPrefill = ManualSetupPrefill(),
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
    var manualHost by remember { mutableStateOf(manualSetupPrefill.host) }
    var manualPort by remember { mutableStateOf(manualSetupPrefill.port) }
    var manualDeviceId by remember { mutableStateOf(manualSetupPrefill.deviceId) }
    var manualToken by remember { mutableStateOf(manualSetupPrefill.token) }
    val start = if (pairingStore.isPaired()) Routes.Home else Routes.Welcome

    fun goHomeAfterPair() {
        nav.navigate(Routes.Home) {
            popUpTo(0) { inclusive = true }
            launchSingleTop = true
        }
    }

    fun openManualSetup(
        host: String = "",
        port: Int? = null,
        deviceId: String = "",
        token: String = "",
    ) {
        vm.dismissPcOffer()
        manualHost = host
        manualPort = port
        manualDeviceId = deviceId
        manualToken = token
        nav.navigate(Routes.ManualSetup)
    }

    fun openManualSetupForRePair() {
        val pairing = pairingStore.load()
        openManualSetup(
            host = pairing?.host.orEmpty(),
            port = pairing?.port,
            deviceId = pairing?.deviceId.orEmpty(),
        )
    }

    LaunchedEffect(Unit) {
        if (pairingStore.isPaired()) return@LaunchedEffect
        if (manualSetupPrefill.openManualSetup) {
            vm.dismissPcOffer()
            nav.navigate(Routes.ManualSetup)
        } else {
            vm.discoverPcOnLaunch()
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
    NavHost(navController = nav, startDestination = start, modifier = Modifier.fillMaxSize()) {
        composable(Routes.Welcome) {
            WelcomeScreen(
                onConnectToPc = { nav.navigate(Routes.EasyConnect) },
                onScanQr = { nav.navigate(Routes.QrScan) },
                onFindPc = { nav.navigate(Routes.Discover) },
                onManualSetup = { openManualSetup() },
            )
        }
        composable(Routes.EasyConnect) {
            EasyConnectScreen(
                onOpenWifiSettings = { WifiSettingsHelper.openWifiSettings(context) },
                onSameWifi = { nav.navigate(Routes.Discover) },
                onManualSetup = { openManualSetup() },
                onBack = { nav.popBackStack() },
            )
        }
        composable(Routes.Discover) {
            DiscoverRoute(
                context = context,
                onConnect = { pc ->
                    openManualSetup(host = pc.host, port = pc.port)
                },
                onManualSetup = { openManualSetup() },
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
                initialDeviceId = manualDeviceId,
                initialToken = manualToken,
                loading = vm.uiState.loading,
                error = vm.uiState.error,
                successMessage = vm.uiState.pairSuccessMessage,
                onPair = { host, port, deviceId, token ->
                    vm.pair(host, port, deviceId, token, ::goHomeAfterPair)
                },
                onBack = { nav.popBackStack() },
            )
        }
        composable(Routes.Home) {
            MainShell(
                vm = vm,
                onOpenClip = { clipId ->
                    vm.openClip(clipId)
                    nav.navigate(Routes.Detail)
                },
                onDisconnect = {
                    vm.disconnect()
                    nav.navigate(Routes.Welcome) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onRePair = { openManualSetupForRePair() },
            )
        }
        composable(Routes.Detail) {
            val clip = vm.uiState.selectedClip
            if (clip != null) {
                ClipDetailScreen(
                    clip = clip,
                    imageAsset = vm.uiState.imageAsset,
                    onBack = {
                        vm.closeClipDetail()
                        nav.popBackStack()
                    },
                    onCopy = { vm.logCopy(clip.id) },
                    onShare = { vm.logShare(clip.id) },
                    onSave = { vm.logSave(clip.id) },
                    onViewAsset = { vm.logAssetOpen(clip.id) },
                )
            }
        }
    }

    vm.uiState.pcFoundOffer?.let { offer ->
        PcFoundBottomSheet(
            offer = offer,
            loading = vm.uiState.loading,
            onConnect = { vm.connectOfferedPc(::goHomeAfterPair) },
            onPairNewDevice = {
                openManualSetup(host = offer.host, port = offer.port)
            },
            onManualSetup = {
                openManualSetup(host = offer.host, port = offer.port)
            },
            onDismiss = { vm.dismissPcOffer() },
        )
    }

    if (vm.uiState.showNoPcFound) {
        AlertDialog(
            onDismissRequest = { vm.dismissPcOffer() },
            title = { Text(stringResource(R.string.no_pc_found_title)) },
            text = { Text(stringResource(R.string.no_pc_found_body)) },
            confirmButton = {
                TextButton(onClick = {
                    vm.dismissPcOffer()
                    vm.discoverPcOnLaunch()
                }) { Text("Try Again") }
            },
            dismissButton = {
                TextButton(onClick = {
                    vm.dismissPcOffer()
                    openManualSetup()
                }) { Text(stringResource(R.string.manual_setup)) }
            },
        )
    }
    }
}

@Composable
private fun DiscoverRoute(
    context: android.content.Context,
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
