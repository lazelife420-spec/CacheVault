package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent

/**
 * Where a Send-to-PC attempt currently stands.
 *
 * Drives the primary button so one tap cannot become several in-flight sends:
 * repeated taps against an unresponsive button previously created duplicate
 * vault items on the desktop.
 */
enum class SendPhase { IDLE, SENDING, SENT, FAILED }

/**
 * True when a new send must be ignored.
 *
 * Single source of truth shared by the button's enabled state and the tap
 * handler, so the two cannot drift apart. FAILED is deliberately not blocking:
 * a failed send must stay retryable.
 */
fun SendPhase.blocksNewSend(): Boolean =
    this == SendPhase.SENDING || this == SendPhase.SENT

fun copyCleanText(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Cache Vault", text))
}

fun shareTextExternal(context: Context, text: String) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(intent, "Share with someone"))
}
