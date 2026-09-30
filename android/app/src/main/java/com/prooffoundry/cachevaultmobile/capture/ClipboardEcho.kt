package com.prooffoundry.cachevaultmobile.capture

import android.os.SystemClock
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultPolicy

/**
 * Suppresses re-capturing text this app itself just wrote to the clipboard
 * (copy-out of a vault item, "Copy text" from the share sheet, diagnostics).
 * Without this, every own-copy would come back in as a duplicate capture.
 * In-memory only — the window is short by design; staleness fails safe to
 * "not an echo".
 */
object ClipboardEcho {
    private const val ECHO_WINDOW_MS = 30_000L
    private const val RECENT_MARK_MS = 2_000L

    @Volatile private var signature: String? = null
    @Volatile private var markedAt: Long = 0L

    fun mark(content: String, nowMs: Long = SystemClock.elapsedRealtime()) {
        signature = LocalVaultPolicy.sha256HexText(content)
        markedAt = nowMs
    }

    fun isEcho(content: String, nowMs: Long = SystemClock.elapsedRealtime()): Boolean {
        val at = markedAt
        return at > 0 &&
            nowMs - at < ECHO_WINDOW_MS &&
            signature == LocalVaultPolicy.sha256HexText(content)
    }

    /**
     * Timing-only check usable where clipboard contents cannot legally be read
     * (background service) — answers "did we very likely just write the clip".
     */
    fun markedRecently(nowMs: Long = SystemClock.elapsedRealtime()): Boolean =
        markedAt > 0 && nowMs - markedAt < RECENT_MARK_MS
}
