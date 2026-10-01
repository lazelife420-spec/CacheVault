package com.prooffoundry.cachevaultmobile.capture

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Debug-only clipboard probe. Lives in the debug source set, so it is never
 * part of a release APK.
 *
 * Why it exists: adb cannot produce a clipboard change on the test image.
 * `cmd clipboard` is unimplemented, `input keycombination` (Ctrl+A/Ctrl+C)
 * selects nothing, `input motionevent` does not exist, and long-press never
 * raises a Copy affordance in Chrome or Settings. Without a synthetic copy
 * there is no way to exercise the clipboard capture paths on a device.
 *
 * Platform limits this harness measured (Android 14/15 emulator):
 *
 * - A clipboard **read** is denied unless the calling app holds window focus:
 *   `ClipboardService: Denying clipboard access to <pkg>, application is not in
 *   focus nor is it a system service for user <n>`. Accessibility services
 *   are not exempt, which is why there is no silent background capture path.
 * - A clipboard **write** from an unfocused app is refused the same way, even
 *   though `setPrimaryClip` returns without throwing. So background mode below
 *   documents a limit rather than exercising capture.
 * - This emulator also mirrors the clipboard to the host and sometimes writes
 *   the host value back over a guest write minutes later; probe runs that span
 *   that window can observe their write reverted. Reads within seconds of the
 *   write are reliable.
 *
 * Modes:
 *
 * `--es text "..."` (focused write, the useful one)
 *   Opens, waits, writes the clipboard while this app still has window focus,
 *   then finishes. The delay lets the focus drain in
 *   [ResumeDrain] consume its debounce first, so the write lands as a real
 *   clipboard change and [ClipboardWatch] posts the "Copied - tap to save"
 *   notification. Tapping that notification then runs [ClipboardSaveActivity],
 *   which is the end-to-end path for a copy made while another app is in front.
 *
 * `--es text "..." --ez trampoline true` (deterministic save-path test)
 *   Same focused write, then directly starts [ClipboardSaveActivity] — the
 *   exact activity the notification's content intent launches. Exists because
 *   opening the shade and tapping the notification via adb is flaky on this
 *   image; the read path is identical to a real notification tap.
 *
 * `--es text "..." --ez background true` (backgrounded write)
 *   Hands focus to another app, finishes, then writes a few seconds later.
 *   Expected result on current Android: the write is refused. Kept as the
 *   reproduction for that limit.
 *
 * The write is deliberately NOT marked in [ClipboardEcho]. An echo mark would
 * make it look like the app's own copy and get it suppressed, whereas the
 * point is to simulate a copy made by some other app.
 *
 * Usage:
 * ```
 * adb shell am start -n <appId>/com.prooffoundry.cachevaultmobile.capture.ClipboardProbeActivity \
 *   --es text "text to place on the clipboard"
 * ```
 */
class ClipboardProbeActivity : ComponentActivity() {

    /**
     * Survives [finish] in background mode, where the write is deliberately
     * scheduled after this activity is gone.
     */
    private val probeScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val text = intent.getStringExtra(EXTRA_TEXT)
        if (intent.getBooleanExtra(EXTRA_BACKGROUND, false)) {
            Log.i(TAG, "background mode: handing focus to $HANDOFF_URL")
            runCatching {
                startActivity(
                    Intent(Intent.ACTION_VIEW, Uri.parse(HANDOFF_URL))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
            }.onFailure { Log.w(TAG, "handoff failed: ${it.message}") }
            finish()
            probeScope.launch {
                delay(BACKGROUND_WRITE_DELAY_MS)
                write(text)
            }
        } else {
            lifecycleScope.launch {
                delay(FOCUSED_WRITE_DELAY_MS)
                write(text)
                if (intent.getBooleanExtra(EXTRA_TRAMPOLINE, false)) {
                    // Same activity, same launch semantics as the notification
                    // tap — just without the shade interaction adb cannot do
                    // reliably here.
                    startActivity(
                        Intent(this@ClipboardProbeActivity, ClipboardSaveActivity::class.java),
                    )
                }
                finish()
            }
        }
    }

    private fun write(text: String?) {
        if (text.isNullOrEmpty()) {
            Log.i(TAG, "no --es text supplied; clipboard left untouched")
            return
        }
        val ok = runCatching {
            val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("probe", text))
        }.isSuccess
        // Note: ok=true only means the call did not throw. An unfocused write
        // is refused by the platform while still returning normally.
        Log.i(TAG, "setPrimaryClip ok=$ok text=$text")
    }

    companion object {
        private const val TAG = "ClipProbe"

        /** Long enough for the focus drain to consume its debounce first. */
        private const val FOCUSED_WRITE_DELAY_MS = 2_500L

        /** Long enough for the handoff app to actually take focus. */
        private const val BACKGROUND_WRITE_DELAY_MS = 3_000L

        private const val HANDOFF_URL = "https://example.com"

        const val EXTRA_TEXT = "text"
        const val EXTRA_BACKGROUND = "background"
        const val EXTRA_TRAMPOLINE = "trampoline"
    }
}
