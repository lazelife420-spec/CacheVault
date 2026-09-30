package com.prooffoundry.cachevaultmobile

import android.app.Application
import com.prooffoundry.cachevaultmobile.capture.CaptureStore
import com.prooffoundry.cachevaultmobile.capture.CaptureWatchService
import com.prooffoundry.cachevaultmobile.capture.ResumeDrain
import com.prooffoundry.cachevaultmobile.connect.BackgroundConnectionService
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.security.VaultLockManager
import com.prooffoundry.cachevaultmobile.security.VaultLockStore

class CacheVaultMobileApp : Application() {
    lateinit var pairingStore: PairingStore
        private set
    lateinit var bridgeRepository: BridgeRepository
        private set
    lateinit var vaultLockStore: VaultLockStore
        private set
    lateinit var vaultLockManager: VaultLockManager
        private set
    lateinit var captureStore: CaptureStore
        private set

    /**
     * Phone-local vault (CV-MOBILE-1). Constructed lazily and opened off the
     * UI thread — it must never block app start on storage work.
     */
    val localVaultRepository: com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository by lazy {
        com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository(this)
    }

    override fun onCreate() {
        super.onCreate()
        pairingStore = PairingStore(this)
        vaultLockStore = VaultLockStore(this)
        vaultLockManager = VaultLockManager(vaultLockStore)
        bridgeRepository = BridgeRepository(pairingStore, appContext = this)
        captureStore = CaptureStore(this)
        if (pairingStore.load()?.keepConnectedInBackground == true &&
            BackgroundConnectionService.canPostNotification(this)
        ) {
            BackgroundConnectionService.start(this)
        }
        CaptureWatchService.sync(this)
        ResumeDrain.attach(this)
    }
}
