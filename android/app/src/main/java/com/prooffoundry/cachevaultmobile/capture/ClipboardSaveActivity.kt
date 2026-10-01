package com.prooffoundry.cachevaultmobile.capture

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import com.prooffoundry.cachevaultmobile.CacheVaultMobileApp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Transparent trampoline: notifications can't read the clipboard, but a
 * user-tapped activity runs foreground where the read is legal. The read is
 * done in onWindowFocusChanged — Android grants clipboard access on window
 * focus, not on activity start, and a translucent window may take a beat to
 * actually gain focus. A delayed onResume retry covers the pathological case
 * where focus lands but the event ordering differed.
 */
class ClipboardSaveActivity : ComponentActivity() {
    private var finished0 = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        overridePendingTransition(0, 0)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) runCapture()
    }

    override fun onResume() {
        super.onResume()
        lifecycleScope.launch {
            delay(600)
            runCapture()
        }
    }

    private fun runCapture() {
        if (finished0) return
        finished0 = true
        val app = application as CacheVaultMobileApp
        lifecycleScope.launch {
            val locked = app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked
            val result = ClipboardCapture.capture(
                context = this@ClipboardSaveActivity,
                repository = app.localVaultRepository,
                store = app.captureStore,
                vaultLocked = locked,
            )
            android.util.Log.i("ClipboardSave", "capture result: $result")
            val message = when (result) {
                is ClipboardCapture.Result.Saved -> "Saved to this phone's vault"
                is ClipboardCapture.Result.Skipped -> when (result.reason) {
                    "locked" -> "Vault is locked — unlock to capture"
                    "sensitive" -> "Looks sensitive — not auto-saved"
                    "duplicate", "already_in_vault", "own_copy" -> "Already in your vault"
                    "empty" -> "Nothing on the clipboard to save"
                    else -> "Nothing to save"
                }
                is ClipboardCapture.Result.Failed -> "Couldn't save (${result.reason})"
            }
            Toast.makeText(this@ClipboardSaveActivity, message, Toast.LENGTH_SHORT).show()
            finish()
        }
    }
}
