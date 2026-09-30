package com.prooffoundry.cachevaultmobile.capture

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.database.ContentObserver
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.prooffoundry.cachevaultmobile.CacheVaultMobileApp
import com.prooffoundry.cachevaultmobile.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Foreground watch for the standalone phone vault. It keeps the process warm
 * so two capture surfaces stay live while the app is away:
 *
 * Clipboard — [ClipboardWatch] posts a "tap to save" heads-up on each foreign
 * copy. Android 10+ never lets a background process read clip contents, so the
 * actual save happens in the foreground trampoline [ClipboardSaveActivity], or
 * silently in the MainActivity resume drain the next time the app opens.
 *
 * Screenshots — a MediaStore observer imports genuinely new screenshots
 * directly (photo permission required; the only truly automatic capture path).
 */
class CaptureWatchService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var shotObserver: ContentObserver? = null

    override fun onCreate() {
        super.onCreate()
        ensureChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val app = application as CacheVaultMobileApp
        when (intent?.action) {
            ACTION_STOP -> {
                teardown()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
                return START_NOT_STICKY
            }
            else -> {
                if (!app.captureStore.anyEnabled) {
                    stopSelf()
                    return START_NOT_STICKY
                }
                startForeground(NOTIFICATION_ID, persistentNotification(app))
                syncSurfaces(app)
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?) = null

    override fun onDestroy() {
        teardown()
        scope.cancel()
        super.onDestroy()
    }

    private fun teardown() {
        shotObserver?.let { runCatching { contentResolver.unregisterContentObserver(it) } }
        shotObserver = null
    }

    private fun syncSurfaces(app: CacheVaultMobileApp) {
        val store = app.captureStore

        // Best-effort here; the durable registration path is
        // MainActivity.onResume (foreground — listener registration is denied
        // to background processes on newer Android).
        if (store.clipboardEnabled) ClipboardWatch.ensureRegistered(this)

        if (store.screenshotsEnabled && ScreenshotImport.hasImagePermission(this) && shotObserver == null) {
            val imp = ScreenshotImport(this, app.localVaultRepository, store)
            val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
                override fun onChange(selfChange: Boolean, uri: Uri?) {
                    android.util.Log.i(TAG, "mediastore change: $uri")
                    scope.launch {
                        val n = imp.importNew(
                            vaultLocked = app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked,
                        )
                        if (n > 0) android.util.Log.i(TAG, "imported $n screenshot(s)")
                    }
                }
            }
            runCatching {
                contentResolver.registerContentObserver(
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                    true,
                    observer,
                )
            }.onSuccess {
                shotObserver = observer
                android.util.Log.i(TAG, "mediastore observer registered")
            }.onFailure { android.util.Log.w(TAG, "mediastore observer registration failed", it) }
        } else if ((!store.screenshotsEnabled || !ScreenshotImport.hasImagePermission(this)) && shotObserver != null) {
            runCatching { contentResolver.unregisterContentObserver(shotObserver!!) }
            shotObserver = null
        }
    }

    private fun persistentNotification(app: CacheVaultMobileApp) =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Vault capture is on")
            .setContentText(persistentBody(app))
            .setStyle(NotificationCompat.BigTextStyle().bigText(persistentBody(app)))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(
                0,
                "Save last copy",
                PendingIntent.getActivity(
                    this,
                    2001,
                    Intent(this, ClipboardSaveActivity::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .addAction(
                0,
                "Stop capture",
                PendingIntent.getService(
                    this,
                    2002,
                    Intent(this, CaptureWatchService::class.java).apply { action = ACTION_STOP },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .build()

    private fun persistentBody(app: CacheVaultMobileApp): String {
        val parts = mutableListOf<String>()
        if (app.captureStore.clipboardEnabled) parts += "copies (tap \"Save last copy\" after copying)"
        if (app.captureStore.screenshotsEnabled) {
            parts += if (ScreenshotImport.hasImagePermission(this)) {
                "screenshots automatically"
            } else {
                "screenshots once photo access is allowed in Settings"
            }
        }
        return "Phone-local only. Capturing " + (parts.joinToString(" and ").ifBlank { "nothing" }) + "."
    }

    private fun ensureChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Vault capture", NotificationManager.IMPORTANCE_LOW),
        )
        ClipboardWatch.ensureChannels(this)
    }

    companion object {
        private const val TAG = "CaptureWatch"
        private const val CHANNEL_ID = "cache_vault_capture"
        private const val NOTIFICATION_ID = 8743
        private const val ACTION_SYNC = "com.prooffoundry.cachevaultmobile.capture.SYNC"
        private const val ACTION_STOP = "com.prooffoundry.cachevaultmobile.capture.STOP"

        /**
         * Single entry point — start/reconfigure when anything is enabled,
         * stop when nothing is. Safe from app start, settings changes, and boot.
         */
        fun sync(context: Context) {
            val app = context.applicationContext as? CacheVaultMobileApp ?: return
            if (app.captureStore.anyEnabled) {
                runCatching {
                    ContextCompat.startForegroundService(
                        context,
                        Intent(context, CaptureWatchService::class.java).apply { action = ACTION_SYNC },
                    )
                }
            } else {
                runCatching {
                    context.startService(
                        Intent(context, CaptureWatchService::class.java).apply { action = ACTION_STOP },
                    )
                }
            }
        }
    }
}
