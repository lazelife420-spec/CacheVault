package com.prooffoundry.cachevaultmobile.capture

import android.content.ClipboardManager
import android.content.Context
import com.prooffoundry.cachevaultmobile.data.SensitiveText
import com.prooffoundry.cachevaultmobile.data.local.LocalIngestion
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultDatabase
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultPolicy
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository

/**
 * Shared clipboard→vault capture. Callers must be foreground (or the
 * foreground trampoline activity) — Android 10+ refuses clipboard reads to
 * anything else, so there is deliberately no background read path here.
 */
object ClipboardCapture {
    private const val TAG = "ClipboardCapture"

    sealed class Result {
        data class Saved(val kind: String) : Result()
        data class Skipped(val reason: String) : Result()
        data class Failed(val reason: String) : Result()
    }

    suspend fun capture(
        context: Context,
        repository: LocalVaultRepository,
        store: CaptureStore,
        vaultLocked: Boolean,
    ): Result {
        if (!store.clipboardEnabled) return Result.Skipped("disabled")
        if (vaultLocked) return Result.Skipped("locked")

        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = runCatching { cm.primaryClip }
            .onFailure { android.util.Log.w(TAG, "primaryClip read denied: ${it.message}") }
            .getOrNull() ?: return Result.Skipped("empty")
        if (clip.itemCount == 0) return Result.Skipped("empty")
        val item = clip.getItemAt(0)

        // Image clip first: a uri-bearing image item coerces to its URI string,
        // which must never be persisted as if it were user text.
        val uri = item.uri
        if (uri != null) {
            val mime = runCatching { context.contentResolver.getType(uri) }.getOrNull()
            if (LocalIngestion.recognizeImage(mime, null) is LocalIngestion.Incoming.Image) {
                val sig = "img:${uri}"
                if (sig == store.lastClipSignature) return Result.Skipped("duplicate")
                return try {
                    repository.saveImage(
                        declaredMime = mime,
                        displayName = null,
                        safeId = LocalVaultDatabase.DEFAULT_SAFE_ID,
                        openStream = { context.contentResolver.openInputStream(uri) },
                        sourceLabel = "clipboard_image",
                    )
                    store.lastClipSignature = sig
                    Result.Saved("image")
                } catch (e: Throwable) {
                    val reason = LocalIngestion.failureReason(e)
                    runCatching { repository.recordFailedSave("clipboard_image_$reason") }
                    Result.Failed(reason)
                }
            }
            return Result.Skipped("unsupported")
        }

        val text = item.text?.toString() ?: item.coerceToText(context)?.toString()
        if (text.isNullOrBlank()) return Result.Skipped("empty")
        if (LocalIngestion.recognizeText(text) !is LocalIngestion.Incoming.Text) {
            return Result.Skipped("empty")
        }
        val sig = LocalVaultPolicy.sha256HexText(text)
        if (sig == store.lastClipSignature) return Result.Skipped("duplicate")
        if (ClipboardEcho.isEcho(text)) return Result.Skipped("own_copy")
        if (repository.hasActiveItemWithHash(sig)) {
            store.lastClipSignature = sig
            return Result.Skipped("already_in_vault")
        }
        if (shouldBlockSensitive(text, store.sensitiveBlockEnabled)) {
            return Result.Skipped("sensitive")
        }
        return try {
            repository.saveText(
                text,
                safeId = LocalVaultDatabase.DEFAULT_SAFE_ID,
                sourceLabel = "clipboard",
            )
            store.lastClipSignature = sig
            Result.Saved("text")
        } catch (e: Throwable) {
            val reason = LocalIngestion.failureReason(e)
            runCatching { repository.recordFailedSave("clipboard_$reason") }
            Result.Failed(reason)
        }
    }

    /**
     * Desktop-doctrine parity: automatic capture refuses sensitive-looking
     * clips (passwords, keys, tokens, cards) when the block is enabled.
     * Pure predicate — unit-tested. Manual save paths never consult it.
     */
    internal fun shouldBlockSensitive(text: String, blockEnabled: Boolean): Boolean =
        blockEnabled && SensitiveText.isSensitive(text)
}
