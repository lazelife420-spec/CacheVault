package com.prooffoundry.cachevaultmobile

import android.os.Bundle
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import com.prooffoundry.cachevaultmobile.integration.AppShortcutPublisher
import com.prooffoundry.cachevaultmobile.ui.ManualSetupPrefill
import com.prooffoundry.cachevaultmobile.ui.CacheVaultMobileRoot
import com.prooffoundry.cachevaultmobile.ui.theme.CacheVaultMobileTheme

class MainActivity : ComponentActivity() {
    private val launchTarget = mutableStateOf<String?>(null)
    private val launchRequestId = mutableLongStateOf(0L)
    private val manualSetupPrefill = mutableStateOf(ManualSetupPrefill())
    private val manualSetupRequestId = mutableLongStateOf(0L)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        acceptIncomingIntent(intent)
        AppShortcutPublisher.publish(this)
        val app = application as CacheVaultMobileApp
        setContent {
            CacheVaultMobileTheme {
                CacheVaultMobileRoot(
                    pairingStore = app.pairingStore,
                    bridgeRepository = app.bridgeRepository,
                    localVaultRepository = app.localVaultRepository,
                    manualSetupPrefill = manualSetupPrefill.value,
                    manualSetupRequestId = manualSetupRequestId.longValue,
                    launchTarget = launchTarget.value,
                    launchRequestId = launchRequestId.longValue,
                    onLaunchRequestHandled = { requestId ->
                        if (requestId == launchRequestId.longValue) launchTarget.value = null
                    },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        acceptIncomingIntent(intent)
    }

    private fun acceptIncomingIntent(intent: Intent?) {
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
