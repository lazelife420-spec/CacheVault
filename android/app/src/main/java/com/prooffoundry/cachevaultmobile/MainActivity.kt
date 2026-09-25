package com.prooffoundry.cachevaultmobile

import android.os.Bundle
import android.content.Intent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.IntentFilter
import androidx.fragment.app.FragmentActivity
import androidx.core.content.ContextCompat
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.LaunchedEffect
import kotlinx.coroutines.delay
import com.prooffoundry.cachevaultmobile.integration.AppShortcutPublisher
import com.prooffoundry.cachevaultmobile.ui.ManualSetupPrefill
import com.prooffoundry.cachevaultmobile.ui.CacheVaultMobileRoot
import com.prooffoundry.cachevaultmobile.ui.theme.CacheVaultMobileTheme
import com.prooffoundry.cachevaultmobile.ui.screens.VaultLockScreen

class MainActivity : FragmentActivity() {
    private val launchTarget = mutableStateOf<String?>(null)
    private val launchRequestId = mutableLongStateOf(0L)
    private val manualSetupPrefill = mutableStateOf(ManualSetupPrefill())
    private val manualSetupRequestId = mutableLongStateOf(0L)
    private val screenOffReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            (application as? CacheVaultMobileApp)?.vaultLockManager?.lock()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        acceptIncomingIntent(intent)
        AppShortcutPublisher.publish(this)
        val app = application as CacheVaultMobileApp
        if (app.vaultLockStore.isEnabled) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        setContent {
            CacheVaultMobileTheme {
                val lockConfigRevision = app.vaultLockManager.configurationRevision
                @Suppress("UNUSED_VARIABLE") val observedConfigRevision = lockConfigRevision
                if (app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked) {
                    VaultLockScreen(app.vaultLockStore, app.vaultLockManager, isGate = true)
                } else {
                    CacheVaultMobileRoot(
                        pairingStore = app.pairingStore,
                        bridgeRepository = app.bridgeRepository,
                        localVaultRepository = app.localVaultRepository,
                        vaultLockStore = app.vaultLockStore,
                        vaultLockManager = app.vaultLockManager,
                        manualSetupPrefill = manualSetupPrefill.value,
                        manualSetupRequestId = manualSetupRequestId.longValue,
                        launchTarget = launchTarget.value,
                        launchRequestId = launchRequestId.longValue,
                        onLaunchRequestHandled = { requestId ->
                            if (requestId == launchRequestId.longValue) launchTarget.value = null
                        },
                    )
                }
                LaunchedEffect(app.vaultLockManager.unlocked) {
                    while (app.vaultLockManager.unlocked && app.vaultLockStore.isEnabled) {
                        delay(1_000)
                        if (app.vaultLockManager.lockIfIdle()) break
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        val app = application as? CacheVaultMobileApp ?: return
        if (app.vaultLockStore.isEnabled) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        else window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        app.vaultLockManager.lockIfIdle()
    }

    override fun onStart() {
        super.onStart()
        ContextCompat.registerReceiver(
            this, screenOffReceiver, IntentFilter(Intent.ACTION_SCREEN_OFF), ContextCompat.RECEIVER_NOT_EXPORTED,
        )
    }

    override fun onStop() {
        runCatching { unregisterReceiver(screenOffReceiver) }
        if (!isChangingConfigurations) (application as? CacheVaultMobileApp)?.vaultLockManager?.lock()
        super.onStop()
    }

    override fun onUserInteraction() {
        super.onUserInteraction()
        (application as? CacheVaultMobileApp)?.vaultLockManager?.noteActivity()
    }


    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        acceptIncomingIntent(intent)
    }

    internal fun acceptIncomingIntent(intent: Intent?) {
        if (intent == null) return
        val setup = ManualSetupPrefill.from(intent)
        if (setup.openManualSetup) {
            manualSetupPrefill.value = setup
            manualSetupRequestId.longValue += 1L
        }

        val uri = intent.data ?: return
        if (intent.action != Intent.ACTION_VIEW || uri.scheme != "cachevault" || uri.host != "open") return
        val target = uri.pathSegments.singleOrNull()?.lowercase() ?: return
        if (target !in setOf("add", "save", "search", "favorites", "safes", "paired-pc", "activity")) return
        launchTarget.value = target
        launchRequestId.longValue += 1L
    }
}
