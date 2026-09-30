package com.prooffoundry.cachevaultmobile.capture

import android.content.Context

/**
 * User-facing capture toggles plus capture bookkeeping for the standalone
 * phone vault. Capture writes only into the phone-local vault — nothing here
 * touches pairing, the bridge, or the network.
 */
class CaptureStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Clipboard capture: drain on app open + "copied, tap to save" notification. */
    var clipboardEnabled: Boolean
        get() = prefs.getBoolean(KEY_CLIPBOARD_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_CLIPBOARD_ENABLED, value).apply()

    /** Screenshot capture: auto-import new screenshots into the phone vault. */
    var screenshotsEnabled: Boolean
        get() = prefs.getBoolean(KEY_SCREENSHOTS_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_SCREENSHOTS_ENABLED, value).apply()

    /** Signature of the last clipboard payload saved — suppresses re-save loops. */
    var lastClipSignature: String?
        get() = prefs.getString(KEY_LAST_CLIP_SIG, null)
        set(value) = prefs.edit().putString(KEY_LAST_CLIP_SIG, value).apply()

    /** Highest MediaStore row id already imported — survives service restarts. */
    var screenshotWatermark: Long
        get() = prefs.getLong(KEY_SHOT_WATERMARK, 0L)
        set(value) = prefs.edit().putLong(KEY_SHOT_WATERMARK, value).apply()

    /**
     * Whether the screenshot watermark was ever seeded. On first enable the
     * watermark jumps to the current max so capture starts with *new*
     * screenshots only — enabling it never bulk-imports existing history.
     */
    var screenshotWatermarkSeeded: Boolean
        get() = prefs.getBoolean(KEY_SHOT_SEEDED, false)
        set(value) = prefs.edit().putBoolean(KEY_SHOT_SEEDED, value).apply()

    val anyEnabled: Boolean
        get() = clipboardEnabled || screenshotsEnabled

    companion object {
        private const val PREFS = "cache_vault_capture"
        private const val KEY_CLIPBOARD_ENABLED = "clipboard_enabled"
        private const val KEY_SCREENSHOTS_ENABLED = "screenshots_enabled"
        private const val KEY_LAST_CLIP_SIG = "last_clip_sig"
        private const val KEY_SHOT_WATERMARK = "screenshot_watermark"
        private const val KEY_SHOT_SEEDED = "screenshot_watermark_seeded"
    }
}
