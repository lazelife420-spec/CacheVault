package com.prooffoundry.cachevaultmobile.data.local

import java.io.InputStream

/**
 * Shared ingestion use-case for CV-MOBILE-1 — one code path behind the
 * Android Share target, the in-app Add/Paste flow, and the single-image
 * picker. It decides *what* an incoming payload is and asks the repository
 * to persist it; the caller decides when (explicit user confirmation) and
 * reports outcomes truthfully.
 */
object LocalIngestion {

    /** What an incoming share/add payload was recognized as. */
    sealed class Incoming {
        data class Text(val content: String, val url: String?) : Incoming()
        data class Image(val declaredMime: String?, val displayName: String?) : Incoming()
        data class Invalid(val reason: String) : Incoming()
    }

    /**
     * Recognize a shared/typed text payload. Blank and placeholder text is
     * invalid — it must never be persisted as a user item. A trimmed bare
     * http(s) URL becomes a LINK; the verbatim content is still what gets
     * stored and hashed.
     */
    fun recognizeText(raw: String?): Incoming {
        val content = raw ?: return Incoming.Invalid("empty")
        if (content.isBlank()) return Incoming.Invalid("empty")
        val url = content.trim().takeIf { LocalVaultPolicy.isBareUrl(it) }
        return Incoming.Text(content = content, url = url)
    }

    fun recognizeImage(declaredMime: String?, displayName: String?): Incoming {
        val mime = (declaredMime ?: "").lowercase()
        if (mime !in LocalVaultPolicy.ALLOWED_IMAGE_MIME) {
            return Incoming.Invalid("unsupported_mime")
        }
        return Incoming.Image(declaredMime = mime, displayName = displayName)
    }

    /**
     * Persist recognized text. Throws [LocalVaultError] on rejection so the
     * caller can show the real failure and record it in the activity ledger.
     */
    suspend fun saveText(
        repository: LocalVaultRepository,
        content: String,
        safeId: String,
        sourceLabel: String,
    ): LocalItem = repository.saveText(content, safeId = safeId, sourceLabel = sourceLabel)

    /** Persist a recognized image stream through the bounded asset pipeline. */
    suspend fun saveImage(
        repository: LocalVaultRepository,
        declaredMime: String?,
        displayName: String?,
        safeId: String,
        openStream: () -> InputStream?,
    ): LocalItem = repository.saveImage(
        declaredMime = declaredMime,
        displayName = displayName,
        safeId = safeId,
        openStream = openStream,
    )

    /** Stable short reason codes for the activity ledger / UI — never payloads. */
    fun failureReason(error: Throwable): String = when (error) {
        is LocalVaultError.Empty -> "empty"
        is LocalVaultError.TextTooLarge -> "text_too_large"
        is LocalVaultError.ImageTooLarge -> "image_too_large"
        is LocalVaultError.UnsupportedImage -> "unsupported_mime"
        is LocalVaultError.ImageUnreadable -> "image_unreadable"
        is LocalVaultError.NotFound -> "not_found"
        is LocalVaultError.SafeNotFound -> "safe_not_found"
        is LocalVaultError.DefaultSafeProtected -> "default_safe_protected"
        is LocalVaultError.SafeNameInvalid -> "safe_name_invalid"
        is LocalVaultError.DatabaseUnavailable -> "database_unavailable"
        else -> "io_error"
    }
}
