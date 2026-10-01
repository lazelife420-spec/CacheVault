package com.prooffoundry.cachevaultmobile.capture

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.prooffoundry.cachevaultmobile.CacheVaultMobileApp
import com.prooffoundry.cachevaultmobile.R
import kotlinx.coroutines.launch

/**
 * Process-wide clipboard-change watcher. Registration must happen while the
 * app is foreground — Android 15 denies [addPrimaryClipChangedListener] from
 * background/starting processes — so this is called from MainActivity.onResume
 * (guaranteed foreground) and best-effort from the capture service. Once
 * registered, the callback keeps firing while the process stays alive; the
 * capture service exists mainly to keep that process warm.
 */
object ClipboardWatch {
    private const val TAG = "ClipboardWatch"
    const val CHANNEL_ALERT_ID = "cache_vault_capture_alert"
    const val NOTIFICATION_CLIP_ID = 8744

    @Volatile private var registered = false
    @Volatile private var listener: ClipboardManager.OnPrimaryClipChangedListener? = null

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ALERT_ID, "Vault capture alerts", NotificationManager.IMPORTANCE_HIGH),
        )
    }

    fun ensureRegistered(context: Context) {
        if (registered) return
        val app = context.applicationContext as? CacheVaultMobileApp ?: return
        if (!app.captureStore.clipboardEnabled) return
        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val l = ClipboardManager.OnPrimaryClipChangedListener { onChanged(app) }
        try {
            cm.addPrimaryClipChangedListener(l)
            listener = l
            registered = true
            android.util.Log.i(TAG, "clipboard listener registered")
        } catch (e: Throwable) {
            android.util.Log.w(TAG, "clipboard listener registration denied: ${e.message}")
        }
    }

    private fun onChanged(app: CacheVaultMobileApp) {
        if (!app.captureStore.clipboardEnabled) return
        if (app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked) return
        if (ClipboardEcho.markedRecently()) return
        // If the accessibility service is enabled it captures the clipboard
        // directly — no notification needed.
        if (ClipboardAccessibilityService.isEnabled(app)) return
        if (!canPostNotification(app)) return
        android.util.Log.i(TAG, "clipboard changed — posting save notification")
        ensureChannels(app)
        val nm = app.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_CLIP_ID, alertNotification(app))
    }

    private fun alertNotification(context: Context) =
        NotificationCompat.Builder(context, CHANNEL_ALERT_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Copied")
            .setContentText("Tap to save to this phone's vault")
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(
                PendingIntent.getActivity(
                    context,
                    2003,
                    Intent(context, ClipboardSaveActivity::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .build()

    private fun canPostNotification(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
}

/**
 * The silent half of clipboard capture: drains the clipboard whenever any app
 * activity regains focus (window focus is what unlocks the read — Android 15
 * denies both reads and listener callbacks to unfocused apps). Lives at the
 * Application level because the foreground activity can be MainActivity, the
 * share sheet, or anything else; debounced so a multi-activity task doesn't
 * drain twice per open.
 */
object ResumeDrain {
    private const val TAG = "CaptureDrain"
    private const val DEBOUNCE_MS = 10_000L

    @Volatile private var lastDrainAt = 0L
    private val scope = kotlinx.coroutines.CoroutineScope(
        kotlinx.coroutines.SupervisorJob() + kotlinx.coroutines.Dispatchers.Default,
    )

    fun attach(app: CacheVaultMobileApp) {
        app.registerActivityLifecycleCallbacks(object : android.app.Application.ActivityLifecycleCallbacks {
            override fun onActivityResumed(activity: android.app.Activity) {
                // The trampoline does its own save; don't double-capture.
                if (activity is ClipboardSaveActivity) return
                // Clipboard access unlocks on window focus — which can land
                // seconds after resume on a cold start — so hook the window's
                // focus event rather than guessing a delay.
                val decor = activity.window?.decorView ?: return
                if (decor.hasWindowFocus()) {
                    onFocused(app, activity)
                } else {
                    decor.viewTreeObserver.addOnWindowFocusChangeListener(
                        object : android.view.ViewTreeObserver.OnWindowFocusChangeListener {
                            override fun onWindowFocusChanged(hasFocus: Boolean) {
                                if (!hasFocus) return
                                decor.viewTreeObserver.removeOnWindowFocusChangeListener(this)
                                onFocused(app, activity)
                            }
                        },
                    )
                }
            }

            override fun onActivityCreated(a: android.app.Activity, b: android.os.Bundle?) {}
            override fun onActivityStarted(a: android.app.Activity) {}
            override fun onActivityPaused(a: android.app.Activity) {}
            override fun onActivityStopped(a: android.app.Activity) {}
            override fun onActivitySaveInstanceState(a: android.app.Activity, b: android.os.Bundle) {}
            override fun onActivityDestroyed(a: android.app.Activity) {}
        })
    }

    private fun onFocused(app: CacheVaultMobileApp, activity: android.app.Activity) {
        // First focus of any window is also the safest place to (re)register
        // the change listener — registration is denied to unfocused apps.
        ClipboardWatch.ensureRegistered(activity)
        if (SystemClock.elapsedRealtime() - lastDrainAt < DEBOUNCE_MS) return
        if (!app.captureStore.clipboardEnabled) return
        if (app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked) return
        lastDrainAt = SystemClock.elapsedRealtime()
        scope.launch {
            val result = ClipboardCapture.capture(
                context = activity,
                repository = app.localVaultRepository,
                store = app.captureStore,
                vaultLocked = false,
            )
            android.util.Log.i(TAG, "resume drain: $result")
            if (result is ClipboardCapture.Result.Saved) {
                kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) {
                    android.widget.Toast.makeText(
                        app,
                        "Copied item saved to this phone's vault",
                        android.widget.Toast.LENGTH_SHORT,
                    ).show()
                }
            }
        }
    }
}
