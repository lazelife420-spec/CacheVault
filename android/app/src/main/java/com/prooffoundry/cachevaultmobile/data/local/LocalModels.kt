package com.prooffoundry.cachevaultmobile.data.local

import java.security.MessageDigest
import java.util.Locale

/**
 * Phone-local vault models (CV-MOBILE-1).
 *
 * These records describe content the user deliberately saved on this device.
 * They are not synchronized with, derived from, or evidence about any desktop
 * vault state — a local Safe is a phone-side organizer, not an encryption
 * container, and a local item ID never denotes a desktop clip.
 */

enum class LocalItemKind(val wireName: String) {
    TEXT("text"),
    LINK("link"),
    IMAGE("image"),
    ;

    companion object {
        fun fromWire(name: String): LocalItemKind =
            entries.firstOrNull { it.wireName == name } ?: TEXT
    }
}

enum class LocalFilter(val label: String) {
    ALL("All"),
    FAVORITES("Favorites"),
    IMAGES("Images"),
    REMOVED("Removed"),
}

enum class LocalActivityAction(val wireName: String) {
    SAVE("save"),
    FAVORITE("favorite"),
    UNFAVORITE("unfavorite"),
    MOVE("move"),
    REMOVE("remove"),
    RESTORE("restore"),
    COPY("copy"),
    SHARE("share"),
    OPEN("open"),
    REVEAL("reveal"),
    SAFE_CREATE("safe_create"),
    SAFE_RENAME("safe_rename"),
}

/**
 * Truthful outcome vocabulary. `INITIATED` means a hand-off was started
 * (e.g. an Android share sheet was opened) — never that another app
 * actually received data.
 */
enum class LocalActivityOutcome(val wireName: String) {
    COMPLETED("completed"),
    FAILED("failed"),
    CANCELLED("cancelled"),
    INITIATED("initiated"),
}

data class LocalItem(
    val id: String,
    val kind: LocalItemKind,
    val title: String,
    val preview: String,
    /** Exact saved text for TEXT/LINK items; null for IMAGE items. */
    val content: String?,
    val safeId: String,
    val isFavorite: Boolean,
    val isSensitive: Boolean,
    val sensitiveReason: String?,
    /** SHA-256 of the exact saved bytes (UTF-8 text or image bytes), lowercase hex. */
    val contentHash: String?,
    val createdAt: String,
    val updatedAt: String,
    val removedAt: String?,
) {
    val isRemoved: Boolean get() = removedAt != null
}

data class LocalSafe(
    val id: String,
    val name: String,
    val isDefault: Boolean,
    val createdAt: String,
)

/** A phone-owned asset row. `state` distinguishes a committed asset from a failed/abandoned ingest. */
data class LocalAsset(
    val id: String,
    val itemId: String,
    /** Generated filename under the app-private `local_assets/` directory — never a user-supplied path. */
    val fileName: String,
    val mime: String,
    val byteCount: Long,
    val sha256: String,
    val width: Int?,
    val height: Int?,
    val state: String,
) {
    companion object {
        const val STATE_COMPLETE = "complete"
        const val STATE_FAILED = "failed"
    }
}

/** One local activity row. Carries no item bodies, tokens, or image bytes. */
data class LocalActivityEvent(
    val id: String,
    val itemId: String?,
    val at: String,
    val action: String,
    val outcome: String,
    /** Bounded reason code (e.g. "share_sheet", "oversized") — never a payload. */
    val reason: String?,
)

/** User-visible failures of the local vault boundary. */
sealed class LocalVaultError(message: String) : Exception(message) {
    class Empty : LocalVaultError("Nothing to save — the item was empty.")
    class TextTooLarge : LocalVaultError("That text is too large to save on this phone (limit 256 KB).")
    class ImageTooLarge : LocalVaultError("That image is too large to save on this phone (limit 10 MB).")
    class UnsupportedImage : LocalVaultError("That image type is not supported (PNG, JPEG, GIF, WebP, BMP).")
    class ImageUnreadable : LocalVaultError("Could not read that image.")
    class NotFound : LocalVaultError("That item is no longer in this phone's vault.")
    class SafeNotFound : LocalVaultError("That Safe does not exist on this phone.")
    class DefaultSafeProtected : LocalVaultError("The default Safe cannot be renamed or removed.")
    class SafeNameInvalid : LocalVaultError("Give the Safe a name first.")
    class DatabaseUnavailable(cause: Throwable) :
        LocalVaultError("The phone vault could not be opened: ${cause.message ?: "storage error"}")
}

/** Shared bounds, hashing and presentation rules for the phone-local vault. */
object LocalVaultPolicy {
    const val MAX_TEXT_BYTES = 256 * 1024
    const val MAX_IMAGE_BYTES = 10 * 1024 * 1024
    const val MAX_IMAGE_PIXELS = 40_000_000L
    const val MAX_THUMBNAIL_EDGE = 512
    const val TITLE_MAX_CHARS = 70
    const val PREVIEW_MAX_CHARS = 100
    const val SAFE_NAME_MAX_CHARS = 60
    const val RECENT_LIMIT = 200
    const val SEARCH_LIMIT = 200
    const val SEARCH_SCAN_LIMIT = 2_000
    const val ACTIVITY_LIMIT = 200
    const val REASON_MAX_CHARS = 64

    val ALLOWED_IMAGE_MIME = setOf(
        "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/bmp",
    )

    fun sha256Hex(bytes: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
        return digest.joinToString("") { "%02x".format(it) }
    }

    /**
     * Hash of the exact saved text, UTF-8 with no trimming or newline
     * normalization — the raw-saved-content digest, kept deliberately separate
     * from any future duplicate-normalization digest.
     */
    fun sha256HexText(text: String): String = sha256Hex(text.toByteArray(Charsets.UTF_8))

    /** A trimmed, single-line http(s) URL is a LINK; everything else is TEXT. */
    fun classifyText(content: String): LocalItemKind {
        val trimmed = content.trim()
        return if (isBareUrl(trimmed)) LocalItemKind.LINK else LocalItemKind.TEXT
    }

    fun isBareUrl(text: String): Boolean {
        val t = text.trim()
        if (t.isEmpty() || t.any { it.isWhitespace() }) return false
        return t.startsWith("http://") || t.startsWith("https://")
    }

    fun titleFor(content: String): String {
        val firstLine = content.replace("\r\n", "\n").replace('\r', '\n')
            .split('\n').firstOrNull { it.isNotBlank() }?.trim() ?: return "(empty)"
        return truncate(firstLine, TITLE_MAX_CHARS)
    }

    fun previewFor(content: String): String {
        val lines = content.replace("\r\n", "\n").replace('\r', '\n')
            .split('\n').map { it.trim() }.filter { it.isNotBlank() }
        if (lines.isEmpty()) return ""
        return truncate(lines.drop(1).take(2).joinToString("\n"), PREVIEW_MAX_CHARS)
    }

    fun truncate(text: String, max: Int): String =
        if (text.length <= max) text else text.take(max - 1).trimEnd() + "…"

    fun utf8Bytes(text: String): Int = text.toByteArray(Charsets.UTF_8).size

    /** Extension used only for the generated local filename — input names are never trusted as paths. */
    fun extensionForMime(mime: String): String = when (mime.lowercase(Locale.ROOT)) {
        "image/png" -> "png"
        "image/jpeg", "image/jpg" -> "jpg"
        "image/gif" -> "gif"
        "image/webp" -> "webp"
        "image/bmp" -> "bmp"
        else -> "img"
    }

    /** Escape LIKE wildcards so user searches treat %, _ and \ literally. */
    fun escapeLike(query: String): String = buildString(query.length) {
        for (c in query) {
            if (c == '%' || c == '_' || c == '\\') append('\\')
            append(c)
        }
    }
}
