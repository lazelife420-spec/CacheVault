package com.prooffoundry.cachevaultmobile.connect

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat.checkSelfPermission
import androidx.core.content.ContextCompat
import com.prooffoundry.cachevaultmobile.CacheVaultMobileApp
import com.prooffoundry.cachevaultmobile.MainActivity
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.BridgeError
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class BackgroundConnectionService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var loopStarted = false

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val app = application as CacheVaultMobileApp
        when (intent?.action) {
            ACTION_STOP -> {
                app.bridgeRepository.updateConnectionPreferences(keepConnectedInBackground = false)
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
                return START_NOT_STICKY
            }
            else -> {
                startForeground(
                    NOTIFICATION_ID,
                    buildNotification(
                        title = getString(R.string.keep_connected_notification_title),
                        body = getString(R.string.keep_connected_notification_starting),
                    ),
                )
                if (!loopStarted) {
                    loopStarted = true
                    scope.launch { runLoop(app) }
                }
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?) = null

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private suspend fun runLoop(app: CacheVaultMobileApp) {
        while (scope.isActive) {
            val pairing = app.pairingStore.load()
            if (pairing == null || !pairing.keepConnectedInBackground) {
                stopSelf()
                return
            }
            val body = runCatching {
                val discovered = app.bridgeRepository.discoverPc()
                if (discovered != null) {
                    app.bridgeRepository.updatePairingHost(
                        host = discovered.host,
                        port = discovered.port,
                        displayName = discovered.displayName,
                    )
                }
                val current = app.pairingStore.load() ?: pairing
                if (current.autoConnectApproved) {
                    app.bridgeRepository.verifyConnection(current)
                    getString(
                        R.string.keep_connected_notification_connected,
                        current.pcLabel.ifBlank { current.host },
                    )
                } else if (discovered != null) {
                    getString(
                        R.string.keep_connected_notification_approval,
                        discovered.displayName,
                    )
                } else {
                    getString(R.string.keep_connected_notification_waiting)
                }
            }.getOrElse { error ->
                when (error) {
                    is BridgeError.Unauthorized ->
                        getString(R.string.keep_connected_notification_repair)
                    else -> getString(R.string.keep_connected_notification_waiting)
                }
            }
            notificationManager().notify(
                NOTIFICATION_ID,
                buildNotification(
                    title = getString(R.string.keep_connected_notification_title),
                    body = body,
                ),
            )
            delay(POLL_MS)
        }
    }

    private fun buildNotification(title: String, body: String) =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(
                PendingIntent.getActivity(
                    this,
                    1001,
                    Intent(this, MainActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .addAction(
                0,
                getString(R.string.stop_background_connection),
                PendingIntent.getService(
                    this,
                    1002,
                    Intent(this, BackgroundConnectionService::class.java).apply {
                        action = ACTION_STOP
                    },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .build()

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Cache Vault background connection",
            NotificationManager.IMPORTANCE_LOW,
        )
        notificationManager().createNotificationChannel(channel)
    }

    private fun notificationManager(): NotificationManager =
        getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    companion object {
        private const val CHANNEL_ID = "cache_vault_mobile_connection"
        private const val NOTIFICATION_ID = 8742
        private const val POLL_MS = 45_000L
        private const val ACTION_STOP = "com.prooffoundry.cachevaultmobile.STOP_BACKGROUND_CONNECTION"

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, BackgroundConnectionService::class.java),
            )
        }

        fun canPostNotification(context: Context): Boolean {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
            return checkSelfPermission(
                context,
                android.Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        }

        fun stop(context: Context) {
            context.startService(
                Intent(context, BackgroundConnectionService::class.java).apply {
                    action = ACTION_STOP
                },
            )
        }
    }
}
