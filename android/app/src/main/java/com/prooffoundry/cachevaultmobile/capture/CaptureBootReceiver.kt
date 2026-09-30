package com.prooffoundry.cachevaultmobile.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Restores the capture watch after reboot when the user left it enabled. */
class CaptureBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        CaptureWatchService.sync(context)
    }
}
