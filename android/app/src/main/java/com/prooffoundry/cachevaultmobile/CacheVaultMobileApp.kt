package com.prooffoundry.cachevaultmobile

import android.app.Application
import com.prooffoundry.cachevaultmobile.data.BridgeRepository
import com.prooffoundry.cachevaultmobile.data.PairingStore

class CacheVaultMobileApp : Application() {
    lateinit var pairingStore: PairingStore
        private set
    lateinit var bridgeRepository: BridgeRepository
        private set

    override fun onCreate() {
        super.onCreate()
        pairingStore = PairingStore(this)
        bridgeRepository = BridgeRepository(pairingStore)
    }
}
