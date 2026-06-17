package com.prooffoundry.cachevaultmobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.prooffoundry.cachevaultmobile.ui.CacheVaultMobileRoot
import com.prooffoundry.cachevaultmobile.ui.ManualSetupPrefill
import com.prooffoundry.cachevaultmobile.ui.theme.CacheVaultMobileTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as CacheVaultMobileApp
        val manualSetupPrefill = ManualSetupPrefill.from(intent)
        setContent {
            CacheVaultMobileTheme {
                CacheVaultMobileRoot(
                    pairingStore = app.pairingStore,
                    bridgeRepository = app.bridgeRepository,
                    manualSetupPrefill = manualSetupPrefill,
                )
            }
        }
    }
}
