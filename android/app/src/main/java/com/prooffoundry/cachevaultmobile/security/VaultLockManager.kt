package com.prooffoundry.cachevaultmobile.security

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue

/** Process-only session state. Unlocked is never persisted across process death. */
class VaultLockManager(val store: VaultLockStore) {
    var configurationRevision by mutableIntStateOf(0)
        private set
    var unlocked by mutableStateOf(!store.isEnabled)
        private set
    private var lastActivityAt = android.os.SystemClock.elapsedRealtime()

    fun lock() {
        if (store.isEnabled) unlocked = false
    }

    fun unlock() {
        unlocked = true
        configurationRevision++
        lastActivityAt = android.os.SystemClock.elapsedRealtime()
    }

    fun configurationChanged() { configurationRevision++ }

    fun noteActivity() {
        if (unlocked) lastActivityAt = android.os.SystemClock.elapsedRealtime()
    }

    fun lockIfIdle(): Boolean {
        if (!unlocked || !store.isEnabled) return false
        if (android.os.SystemClock.elapsedRealtime() - lastActivityAt >= store.lockTimeoutMs) {
            lock()
            return true
        }
        return false
    }
}
