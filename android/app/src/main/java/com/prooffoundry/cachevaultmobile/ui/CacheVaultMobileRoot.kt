package com.prooffoundry.cachevaultmobile.ui

import android.Manifest
import android.os.Build
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.prooffoundry.cachevaultmobile.connect.BackgroundConnectionService
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.PcDiscovery
import com.prooffoundry.cachevaultmobile.connect.WifiSettingsHelper
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.ui.screens.ClipDetailScreen
import com.prooffoundry.cachevaultmobile.ui.screens.DiscoverPcScreen
import com.prooffoundry.cachevaultmobile.ui.screens.EasyConnectScreen
import com.prooffoundry.cachevaultmobile.ui.screens.ImageViewerScreen
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
    const val ImageViewer = "image_viewer"
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
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            runCatching { BackgroundConnectionService.start(context) }
                .onSuccess { vm.setKeepConnectedInBackground(true) }
                .onFailure {
                    vm.reportBackgroundConnectionFailure(
                        context.getString(R.string.background_start_failed),
                    )
                }
        } else {
            vm.reportBackgroundConnectionFailure(
                context.getString(R.string.background_permission_needed),
            )
        }
    }
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
        if (manualSetupPrefill.openManualSetup) {
            vm.dismissPcOffer()
            nav.navigate(Routes.ManualSetup)
        } else if (pairingStore.isPaired()) {
            vm.initializeConnectionLifecycle()
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
                    vm.pairDiscoveredPc(pc, ::goHomeAfterPair)
                },
                onManualSetup = { openManualSetup() },
                onBack = { nav.popBackStack() },
            )
        }
        composable(Routes.QrScan) {
            val qrPayloadExtra = (context as? android.app.Activity)?.intent?.getStringExtra("qr_payload").orEmpty()
            QrScanScreen(
                initialPayload = qrPayloadExtra,
                loading = vm.uiState.loading,
                error = vm.uiState.error,
                onPairQr = { payload ->
                    vm.pairWithQrOffer(payload, ::goHomeAfterPair)
                },
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
                onOpenImage = { clip, gallery ->
                    vm.openImageInGallery(clip, gallery)
                    nav.navigate(Routes.Detail)
                },
                onDisconnect = {
                    BackgroundConnectionService.stop(context)
                    vm.disconnect()
                    nav.navigate(Routes.Welcome) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onRePair = { openManualSetupForRePair() },
                onKeepConnectedChanged = { enabled ->
                    if (!enabled) {
                        vm.setKeepConnectedInBackground(false)
                        BackgroundConnectionService.stop(context)
                    } else {
                        val needsNotificationPermission =
                            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                                ContextCompat.checkSelfPermission(
                                    context,
                                    Manifest.permission.POST_NOTIFICATIONS,
                                ) != PackageManager.PERMISSION_GRANTED

                        if (needsNotificationPermission) {
                            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        } else {
                            runCatching {
                                BackgroundConnectionService.start(context)
                            }.onSuccess {
                                vm.setKeepConnectedInBackground(true)
                            }.onFailure {
                                vm.reportBackgroundConnectionFailure(
                                    context.getString(R.string.background_start_failed),
                                )
                            }
                        }
                    }
                },
            )
        }
        composable(Routes.Detail) {
            val clip = vm.uiState.selectedClip
            val activeClipId = vm.uiState.activeClipId
            ClipDetailScreen(
                clip = clip,
                imageAsset = vm.uiState.imageAsset,
                loading = vm.uiState.loading && clip == null,
                error = vm.uiState.detailError,
                onBack = {
                    vm.closeClipDetail()
                    nav.popBackStack()
                },
                onRetry = activeClipId?.let { clipId ->
                    { vm.openClip(clipId) }
                },
                onCopy = { clip?.let { vm.logCopy(it.id) } },
                onShare = { clip?.let { vm.logShare(it.id) } },
                onSave = { clip?.let { vm.logSave(it.id) } },
                onViewAsset = { clip?.let { vm.logAssetOpen(it.id) } },
                onOpenFullScreen = { nav.navigate(Routes.ImageViewer) },
            )
        }
        composable(Routes.ImageViewer) {
            val clip = vm.uiState.selectedClip
            val activeClipId = vm.uiState.activeClipId
            ImageViewerScreen(
                gallery = vm.uiState.imageGallery,
                currentIndex = vm.uiState.imageGalleryIndex,
                currentAsset = vm.uiState.imageAsset,
                neighborAssets = vm.uiState.preloadedAssets,
                onIndexChanged = { newIndex -> vm.navigateGalleryTo(newIndex) },
                onBack = { nav.popBackStack() },
                onRetry = activeClipId?.let { clipId ->
                    { vm.loadImageAsset(clipId) }
                },
                onShare = { clip?.let { vm.logShare(it.id) } },
                onSave = { clip?.let { vm.logSave(it.id) } },
            )
        }
    }

    vm.uiState.pcFoundOffer?.let { offer ->
        PcFoundBottomSheet(
            offer = offer,
            loading = vm.uiState.loading,
            onConnect = { vm.connectOfferedPc(::goHomeAfterPair) },
            onTrustAndConnect = {
                vm.approveAutoConnect(true)
                vm.connectOfferedPc(::goHomeAfterPair)
            },
            onPairNewDevice = {
                vm.pairDiscoveredPc(
                    DiscoveredPc(
                        displayName = offer.displayName,
                        host = offer.host,
                        port = offer.port,
                    ),
                    ::goHomeAfterPair,
                )
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
                    nav.navigate(Routes.QrScan)
                }) { Text("Scan QR Code") }
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
