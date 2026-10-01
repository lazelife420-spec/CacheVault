package com.prooffoundry.cachevaultmobile.capture

import android.accessibilityservice.AccessibilityService
import android.content.ClipboardManager
import android.content.Context
import android.provider.Settings
import android.view.accessibility.AccessibilityEvent
import com.prooffoundry.cachevaultmobile.CacheVaultMobileApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Accessibility-level clipboard capture. When enabled by the user, the
 * accessibility service runs continuously in the background and registers
 * a [ClipboardManager.OnPrimaryClipChangedListener]. On each clipboard
 * change the service reads the clip directly — accessibility services are
 * exempt from the Android 10+ background clipboard read restriction — and
 * saves it to the phone-local vault via [ClipboardCapture].
 *
 * This is the fully automatic path: no notification to tap, no app to open.
 * The foreground-service + notification fallback in [ClipboardWatch] and
 * [ResumeDrain] still covers devices where the user has not enabled the
 * accessibility service.
 */
class ClipboardAccessibilityService : AccessibilityService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var listener: ClipboardManager.OnPrimaryClipChangedListener? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        val app = applicationContext as? CacheVaultMobileApp ?: return
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val l = ClipboardManager.OnPrimaryClipChangedListener { onClipChanged(app) }
        runCatching {
            cm.addPrimaryClipChangedListener(l)
            listener = l
            android.util.Log.i(TAG, "clipboard listener registered via accessibility service")
        }.onFailure { android.util.Log.w(TAG, "listener registration failed: ${it.message}") }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // No accessibility events are processed — the service exists solely
        // to hold the clipboard-change listener with elevated read access.
    }

    override fun onInterrupt() {
        // No-op — there is no active feedback to interrupt.
    }

    override fun onDestroy() {
        super.onDestroy()
        listener?.let { l ->
            runCatching {
                getSystemService(Context.CLIPBOARD_SERVICE)
                    ?.let { it as? ClipboardManager }
                    ?.removePrimaryClipChangedListener(l)
            }
        }
        listener = null
        scope.cancel()
    }

    private fun onClipChanged(app: CacheVaultMobileApp) {
        if (!app.captureStore.clipboardEnabled) return
        if (ClipboardEcho.markedRecently()) return
        val locked = app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked
        scope.launch {
            val result = ClipboardCapture.capture(
                context = this@ClipboardAccessibilityService,
                repository = app.localVaultRepository,
                store = app.captureStore,
                vaultLocked = locked,
            )
            android.util.Log.i(TAG, "accessibility capture: $result")
        }
    }

    companion object {
        private const val TAG = "ClipA11y"

        /**
         * Whether this accessibility service is currently enabled in system
         * settings. Checked from [ClipboardWatch] to decide whether to
         * post the fallback notification.
         */
        fun isEnabled(context: Context): Boolean {
            val enabled = runCatching {
                Settings.Secure.getString(
                    context.contentResolver,
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
                )
            }.getOrNull() ?: return false
            val serviceName = "${context.packageName}/${ClipboardAccessibilityService::class.java.name}"
            return enabled.split(':').any { it.equals(serviceName, ignoreCase = true) }
        }
    }
}
