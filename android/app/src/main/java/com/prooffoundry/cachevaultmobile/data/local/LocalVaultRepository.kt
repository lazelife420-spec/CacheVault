package com.prooffoundry.cachevaultmobile.data.local

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import com.prooffoundry.cachevaultmobile.data.SensitiveText
import java.io.InputStream
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * Single application-scoped boundary for the phone-local vault (CV-MOBILE-1).
 *
 * All database work runs on a cancellable IO dispatcher and every mutation is
 * serialized through one Mutex. This class never touches PairingStore,
 * BridgeRepository or the network — local saves must succeed with the PC
 * offline and with no pairing at all.
 *
 * Every state-changing call also writes a bounded [LocalActivityEvent] inside
 * the same transaction. The ledger never receives item bodies, tokens, or
 * image bytes — only ids, action/outcome codes and a short reason code.
 */
class LocalVaultRepository(
    context: Context,
    private val assetStore: LocalAssetStore = LocalAssetStore(context),
    dbName: String = LocalVaultDatabase.DATABASE_NAME,
    dbVersion: Int = LocalVaultDatabase.DATABASE_VERSION,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) {
    private val helper = LocalVaultDatabase(context, dbName, dbVersion)
    private val writes = Mutex()

    @Volatile
    private var reconciled = false

    private fun db(): SQLiteDatabase = try {
        helper.writableDatabase
    } catch (e: Exception) {
        throw LocalVaultError.DatabaseUnavailable(e)
    }

    /** First-open housekeeping: drop failed asset rows and orphan/staging files. */
    private fun ensureReconciled(database: SQLiteDatabase) {
        if (reconciled) return
        val keep = mutableSetOf<String>()
        database.rawQuery("SELECT file_name FROM assets WHERE state = ?", arrayOf(LocalAsset.STATE_COMPLETE)).use { c ->
            while (c.moveToNext()) keep += c.getString(0)
        }
        database.delete("assets", "state != ?", arrayOf(LocalAsset.STATE_COMPLETE))
        assetStore.reconcileOrphans(keep)
        reconciled = true
    }

    // ---- items ---------------------------------------------------------------

    suspend fun saveText(
        content: String,
        safeId: String = LocalVaultDatabase.DEFAULT_SAFE_ID,
        sourceLabel: String? = null,
    ): LocalItem = write { database ->
        val trimmed = content.trim()
        if (trimmed.isEmpty()) throw LocalVaultError.Empty()
        if (LocalVaultPolicy.utf8Bytes(content) > LocalVaultPolicy.MAX_TEXT_BYTES) {
            throw LocalVaultError.TextTooLarge()
        }
        requireSafe(database, safeId)
        val kind = LocalVaultPolicy.classifyText(content)
        val sensitiveReason = SensitiveText.reason(content)
        val now = Instant.now().toString()
        val item = LocalItem(
            id = newId(),
            kind = kind,
            title = LocalVaultPolicy.titleFor(content),
            preview = LocalVaultPolicy.previewFor(content),
            content = content,
            safeId = safeId,
            isFavorite = false,
            isSensitive = sensitiveReason != null,
            sensitiveReason = sensitiveReason,
            contentHash = LocalVaultPolicy.sha256HexText(content),
            createdAt = now,
            updatedAt = now,
            removedAt = null,
        )
        insertItem(database, item)
        recordActivity(
            database, item.id, LocalActivityAction.SAVE,
            LocalActivityOutcome.COMPLETED,
            reason = boundedReason(sourceLabel ?: kind.wireName),
        )
        item
    }

    suspend fun saveImage(
        declaredMime: String?,
        displayName: String?,
        safeId: String = LocalVaultDatabase.DEFAULT_SAFE_ID,
        openStream: () -> InputStream?,
    ): LocalItem {
        // Reconcile BEFORE the file is finalized — otherwise a first-call
        // reconcile inside `write` would treat the just-staged file (no
        // committed asset row yet) as an orphan and delete it.
        withContext(ioDispatcher) {
            ensureReconciled(db())
        }
        val staged = withContext(ioDispatcher) {
            assetStore.importStream(declaredMime, openStream)
        }
        return write { database ->
            requireSafe(database, safeId)
            val now = Instant.now().toString()
            val assetId = newId()
            val itemId = newId()
            val kb = staged.byteCount / 1024
            val item = LocalItem(
                id = itemId,
                kind = LocalItemKind.IMAGE,
                title = imageTitle(displayName, staged),
                preview = "Image · ${staged.mime.substringAfter('/')} · $kb KB",
                content = null,
                safeId = safeId,
                isFavorite = false,
                isSensitive = false,
                sensitiveReason = null,
                contentHash = staged.sha256,
                createdAt = now,
                updatedAt = now,
                removedAt = null,
            )
            try {
                // `write` already holds the transaction — item + asset + activity
                // commit together or not at all. Filesystem/DB atomicity is not
                // claimed: on DB failure we remove only the file this call
                // finalized (staging orphans are reconciled at next open).
                insertItem(database, item.copy(contentHash = staged.sha256), assetIdOverride = assetId)
                insertAsset(
                    database,
                    LocalAsset(
                        id = assetId,
                        itemId = itemId,
                        fileName = staged.file.name,
                        mime = staged.mime,
                        byteCount = staged.byteCount,
                        sha256 = staged.sha256,
                        width = staged.width,
                        height = staged.height,
                        state = LocalAsset.STATE_COMPLETE,
                    ),
                )
                recordActivity(
                    database, itemId, LocalActivityAction.SAVE,
                    LocalActivityOutcome.COMPLETED, reason = "image",
                )
            } catch (e: Exception) {
                assetStore.delete(staged.file.name)
                if (e is LocalVaultError) throw e else throw LocalVaultError.DatabaseUnavailable(e)
            }
            item
        }
    }

    suspend fun item(id: String): LocalItem? = read { database ->
        database.rawQuery("$ITEM_SELECT WHERE i.id = ?", arrayOf(id)).use { c ->
            if (c.moveToFirst()) c.toItem() else null
        }
    }

    suspend fun assetForItem(itemId: String): LocalAsset? = read { database ->
        database.rawQuery(
            "SELECT id, item_id, file_name, mime, byte_count, sha256, width, height, state " +
                "FROM assets WHERE item_id = ? AND state = ?",
            arrayOf(itemId, LocalAsset.STATE_COMPLETE),
        ).use { c -> if (c.moveToFirst()) c.toAsset() else null }
    }

    suspend fun openAssetStream(fileName: String): InputStream? = withContext(ioDispatcher) {
        assetStore.openRead(fileName)
    }

    fun assetFileFor(fileName: String): java.io.File? = assetStore.fileFor(fileName)

    /** Bounded decode for list/detail rendering — never full-resolution in lists. */
    fun decodeAssetThumbnail(
        fileName: String,
        maxEdgePx: Int = LocalVaultPolicy.MAX_THUMBNAIL_EDGE,
    ): android.graphics.Bitmap? = assetStore.decodeThumbnail(fileName, maxEdgePx)

    suspend fun recent(limit: Int = LocalVaultPolicy.RECENT_LIMIT): List<LocalItem> = read { database ->
        queryItems(
            database,
            where = "i.removed_at IS NULL",
            orderBy = "i.created_at DESC",
            limit = limit,
        )
    }

    suspend fun removedItems(limit: Int = LocalVaultPolicy.RECENT_LIMIT): List<LocalItem> = read { database ->
        queryItems(
            database,
            where = "i.removed_at IS NOT NULL",
            orderBy = "i.removed_at DESC",
            limit = limit,
        )
    }

    suspend fun itemsInSafe(safeId: String): List<LocalItem> = read { database ->
        queryItems(
            database,
            where = "i.removed_at IS NULL AND i.safe_id = ?",
            args = arrayOf(safeId),
            orderBy = "i.created_at DESC",
            limit = LocalVaultPolicy.SEARCH_SCAN_LIMIT,
        )
    }

    /**
     * Unicode-aware contains-match over title/preview/text body.
     * Runs Kotlin-side (SQLite LIKE is ASCII-only for case-insensitivity) over a
     * bounded scan; wildcard characters and quotes are literal user input.
     * Removed items are excluded unless [filter] is REMOVED.
     */
    suspend fun search(
        query: String,
        filter: LocalFilter = LocalFilter.ALL,
        safeId: String? = null,
    ): List<LocalItem> = read { database ->
        val candidates = when (filter) {
            LocalFilter.REMOVED -> queryItems(
                database,
                where = "i.removed_at IS NOT NULL",
                orderBy = "i.removed_at DESC",
                limit = LocalVaultPolicy.SEARCH_SCAN_LIMIT,
            )
            else -> {
                val clauses = mutableListOf("i.removed_at IS NULL")
                val args = mutableListOf<String>()
                safeId?.let {
                    clauses += "i.safe_id = ?"
                    args += it
                }
                queryItems(
                    database,
                    where = clauses.joinToString(" AND "),
                    args = args.toTypedArray(),
                    orderBy = "i.created_at DESC",
                    limit = LocalVaultPolicy.SEARCH_SCAN_LIMIT,
                )
            }
        }
        val filteredByKind = when (filter) {
            LocalFilter.FAVORITES -> candidates.filter { it.isFavorite }
            LocalFilter.IMAGES -> candidates.filter { it.kind == LocalItemKind.IMAGE }
            else -> candidates
        }
        val q = query.trim()
        if (q.isEmpty()) return@read filteredByKind.take(LocalVaultPolicy.SEARCH_LIMIT)
        val needle = q.lowercase()
        filteredByKind.filter { item ->
            item.title.lowercase().contains(needle) ||
                item.preview.lowercase().contains(needle) ||
                item.content?.lowercase()?.contains(needle) == true
        }.take(LocalVaultPolicy.SEARCH_LIMIT)
    }

    suspend fun setFavorite(itemId: String, favorite: Boolean): LocalItem = write { database ->
        val item = requireItem(database, itemId)
        database.execSQL(
            "UPDATE items SET is_favorite = ?, updated_at = ? WHERE id = ?",
            arrayOf(if (favorite) 1 else 0, Instant.now().toString(), itemId),
        )
        recordActivity(
            database, itemId,
            if (favorite) LocalActivityAction.FAVORITE else LocalActivityAction.UNFAVORITE,
            LocalActivityOutcome.COMPLETED, reason = null,
        )
        item.copy(isFavorite = favorite, updatedAt = Instant.now().toString())
    }

    suspend fun moveToSafe(itemId: String, safeId: String): LocalItem = write { database ->
        requireSafe(database, safeId)
        val item = requireItem(database, itemId)
        database.execSQL(
            "UPDATE items SET safe_id = ?, updated_at = ? WHERE id = ?",
            arrayOf(safeId, Instant.now().toString(), itemId),
        )
        recordActivity(
            database, itemId, LocalActivityAction.MOVE,
            LocalActivityOutcome.COMPLETED, reason = boundedReason(safeId),
        )
        item.copy(safeId = safeId, updatedAt = Instant.now().toString())
    }

    /** Reversible local remove — sets removed_at; never deletes rows, files, or desktop data. */
    suspend fun removeItem(itemId: String): LocalItem = write { database ->
        val item = requireItem(database, itemId)
        val now = Instant.now().toString()
        database.execSQL(
            "UPDATE items SET removed_at = ?, updated_at = ? WHERE id = ?",
            arrayOf(now, now, itemId),
        )
        recordActivity(
            database, itemId, LocalActivityAction.REMOVE,
            LocalActivityOutcome.COMPLETED, reason = null,
        )
        item.copy(removedAt = now, updatedAt = now)
    }

    suspend fun restoreItem(itemId: String): LocalItem = write { database ->
        val item = requireItem(database, itemId)
        val now = Instant.now().toString()
        database.execSQL(
            "UPDATE items SET removed_at = NULL, updated_at = ? WHERE id = ?",
            arrayOf(now, itemId),
        )
        recordActivity(
            database, itemId, LocalActivityAction.RESTORE,
            LocalActivityOutcome.COMPLETED, reason = null,
        )
        item.copy(removedAt = null, updatedAt = now)
    }

    // ---- safes ---------------------------------------------------------------

    suspend fun safes(): List<LocalSafe> = read { database ->
        database.rawQuery("SELECT id, name, is_default, created_at FROM safes ORDER BY is_default DESC, name ASC", emptyArray())
            .use { c ->
                val out = mutableListOf<LocalSafe>()
                while (c.moveToNext()) {
                    out += LocalSafe(
                        id = c.getString(0),
                        name = c.getString(1),
                        isDefault = c.getInt(2) == 1,
                        createdAt = c.getString(3),
                    )
                }
                out
            }
    }

    suspend fun createSafe(name: String): LocalSafe = write { database ->
        val trimmed = name.trim().take(LocalVaultPolicy.SAFE_NAME_MAX_CHARS)
        if (trimmed.isEmpty()) throw LocalVaultError.SafeNameInvalid()
        val safe = LocalSafe(
            id = newId(),
            name = trimmed,
            isDefault = false,
            createdAt = Instant.now().toString(),
        )
        database.insertOrThrow(
            "safes", null,
            ContentValues().apply {
                put("id", safe.id)
                put("name", safe.name)
                put("is_default", 0)
                put("created_at", safe.createdAt)
            },
        )
        recordActivity(database, null, LocalActivityAction.SAFE_CREATE, LocalActivityOutcome.COMPLETED, null)
        safe
    }

    suspend fun renameSafe(safeId: String, newName: String): LocalSafe = write { database ->
        val trimmed = newName.trim().take(LocalVaultPolicy.SAFE_NAME_MAX_CHARS)
        if (trimmed.isEmpty()) throw LocalVaultError.SafeNameInvalid()
        val existing = database.rawQuery(
            "SELECT id, name, is_default, created_at FROM safes WHERE id = ?",
            arrayOf(safeId),
        ).use { c ->
            if (c.moveToFirst()) {
                LocalSafe(c.getString(0), c.getString(1), c.getInt(2) == 1, c.getString(3))
            } else {
                throw LocalVaultError.SafeNotFound()
            }
        }
        if (existing.isDefault) throw LocalVaultError.DefaultSafeProtected()
        database.execSQL("UPDATE safes SET name = ? WHERE id = ?", arrayOf(trimmed, safeId))
        recordActivity(database, null, LocalActivityAction.SAFE_RENAME, LocalActivityOutcome.COMPLETED, null)
        existing.copy(name = trimmed)
    }

    suspend fun countBySafe(): Map<String, Int> = read { database ->
        database.rawQuery(
            "SELECT safe_id, COUNT(*) FROM items WHERE removed_at IS NULL GROUP BY safe_id",
            emptyArray(),
        ).use { c ->
            val out = mutableMapOf<String, Int>()
            while (c.moveToNext()) out[c.getString(0)] = c.getInt(1)
            out
        }
    }

    // ---- activity ledger -----------------------------------------------------

    suspend fun activity(limit: Int = LocalVaultPolicy.ACTIVITY_LIMIT): List<LocalActivityEvent> =
        read { database ->
            database.rawQuery(
                "SELECT id, item_id, at, action, outcome, reason FROM activity ORDER BY at DESC LIMIT ?",
                arrayOf(limit.toString()),
            ).use { c ->
                val out = mutableListOf<LocalActivityEvent>()
                while (c.moveToNext()) out += c.toActivity()
                out
            }
        }

    /** Copy is completed the moment the clipboard write returns. */
    suspend fun recordCopy(itemId: String) = write { database ->
        recordActivity(database, itemId, LocalActivityAction.COPY, LocalActivityOutcome.COMPLETED, null)
    }

    /** A chooser opening is share-initiated, never proof another app received data. */
    suspend fun recordShareInitiated(itemId: String) = write { database ->
        recordActivity(database, itemId, LocalActivityAction.SHARE, LocalActivityOutcome.INITIATED, null)
    }

    suspend fun recordOpen(itemId: String) = write { database ->
        recordActivity(database, itemId, LocalActivityAction.OPEN, LocalActivityOutcome.COMPLETED, null)
    }

    suspend fun recordReveal(itemId: String) = write { database ->
        recordActivity(database, itemId, LocalActivityAction.REVEAL, LocalActivityOutcome.COMPLETED, null)
    }

    suspend fun recordFailedSave(reason: String) = write { database ->
        recordActivity(database, null, LocalActivityAction.SAVE, LocalActivityOutcome.FAILED, boundedReason(reason))
    }

    suspend fun recordCancelledSave() = write { database ->
        recordActivity(database, null, LocalActivityAction.SAVE, LocalActivityOutcome.CANCELLED, boundedReason("user_cancelled"))
    }

    // ---- meta ----------------------------------------------------------------

    /** Stable per-install vault identifier — independent of any paired-device credential. */
    suspend fun vaultId(): String = read { database ->
        database.rawQuery("SELECT value FROM meta WHERE key = 'vault_id'", emptyArray()).use { c ->
            if (c.moveToFirst()) return@read c.getString(0)
        }
        val id = newId()
        database.insertOrThrow(
            "meta", null,
            ContentValues().apply { put("key", "vault_id"); put("value", id) },
        )
        id
    }

    fun close() = helper.close()

    // ---- internals -----------------------------------------------------------

    private suspend fun <T> write(block: (SQLiteDatabase) -> T): T =
        withContext(ioDispatcher) {
            writes.withLock {
                val database = db()
                ensureReconciled(database)
                database.beginTransaction()
                try {
                    val result = block(database)
                    database.setTransactionSuccessful()
                    result
                } finally {
                    database.endTransaction()
                }
            }
        }

    private suspend fun <T> read(block: (SQLiteDatabase) -> T): T =
        withContext(ioDispatcher) {
            val database = db()
            ensureReconciled(database)
            block(database)
        }

    private fun requireItem(database: SQLiteDatabase, id: String): LocalItem =
        database.rawQuery("$ITEM_SELECT WHERE i.id = ?", arrayOf(id)).use { c ->
            if (c.moveToFirst()) c.toItem() else throw LocalVaultError.NotFound()
        }

    private fun requireSafe(database: SQLiteDatabase, safeId: String) {
        database.rawQuery("SELECT id FROM safes WHERE id = ?", arrayOf(safeId)).use { c ->
            if (!c.moveToFirst()) throw LocalVaultError.SafeNotFound()
        }
    }

    private fun insertItem(database: SQLiteDatabase, item: LocalItem, assetIdOverride: String? = null) {
        database.insertOrThrow(
            "items", null,
            ContentValues().apply {
                put("id", item.id)
                put("kind", item.kind.wireName)
                put("title", item.title)
                put("preview", item.preview)
                put("content", item.content)
                put("asset_id", assetIdOverride)
                put("content_hash", item.contentHash)
                put("safe_id", item.safeId)
                put("is_favorite", if (item.isFavorite) 1 else 0)
                put("is_sensitive", if (item.isSensitive) 1 else 0)
                put("sensitive_reason", item.sensitiveReason)
                put("created_at", item.createdAt)
                put("updated_at", item.updatedAt)
                put("removed_at", item.removedAt)
            },
        )
    }

    private fun insertAsset(database: SQLiteDatabase, asset: LocalAsset) {
        database.insertOrThrow(
            "assets", null,
            ContentValues().apply {
                put("id", asset.id)
                put("item_id", asset.itemId)
                put("file_name", asset.fileName)
                put("mime", asset.mime)
                put("byte_count", asset.byteCount)
                put("sha256", asset.sha256)
                put("width", asset.width)
                put("height", asset.height)
                put("state", asset.state)
            },
        )
    }

    private fun recordActivity(
        database: SQLiteDatabase,
        itemId: String?,
        action: LocalActivityAction,
        outcome: LocalActivityOutcome,
        reason: String?,
    ) {
        database.insertOrThrow(
            "activity", null,
            ContentValues().apply {
                put("id", newId())
                put("item_id", itemId)
                put("at", Instant.now().toString())
                put("action", action.wireName)
                put("outcome", outcome.wireName)
                put("reason", reason)
            },
        )
    }

    private fun queryItems(
        database: SQLiteDatabase,
        where: String,
        args: Array<String> = emptyArray(),
        orderBy: String,
        limit: Int,
    ): List<LocalItem> {
        return database.rawQuery(
            "$ITEM_SELECT WHERE $where ORDER BY $orderBy LIMIT ?",
            args + limit.toString(),
        ).use { c ->
            val out = mutableListOf<LocalItem>()
            while (c.moveToNext()) out += c.toItem()
            out
        }
    }

    private fun boundedReason(reason: String): String =
        reason.take(LocalVaultPolicy.REASON_MAX_CHARS)

    private fun newId(): String = UUID.randomUUID().toString()

    private fun imageTitle(displayName: String?, staged: LocalAssetStore.StagedImage): String {
        val dims = if (staged.width != null && staged.height != null) {
            " ${staged.width}×${staged.height}"
        } else {
            ""
        }
        val base = displayName?.substringAfterLast('/')?.substringAfterLast('\\')
            ?.takeIf { it.isNotBlank() } ?: "Image"
        return LocalVaultPolicy.truncate("$base$dims", LocalVaultPolicy.TITLE_MAX_CHARS)
    }

    companion object {
        private const val ITEM_SELECT =
            "SELECT i.id, i.kind, i.title, i.preview, i.content, i.safe_id, i.is_favorite, " +
                "i.is_sensitive, i.sensitive_reason, i.content_hash, i.created_at, i.updated_at, " +
                "i.removed_at FROM items i"

        private fun Cursor.toItem() = LocalItem(
            id = getString(0),
            kind = LocalItemKind.fromWire(getString(1)),
            title = getString(2),
            preview = getString(3),
            content = if (isNull(4)) null else getString(4),
            safeId = getString(5),
            isFavorite = getInt(6) == 1,
            isSensitive = getInt(7) == 1,
            sensitiveReason = if (isNull(8)) null else getString(8),
            contentHash = if (isNull(9)) null else getString(9),
            createdAt = getString(10),
            updatedAt = getString(11),
            removedAt = if (isNull(12)) null else getString(12),
        )

        private fun Cursor.toAsset() = LocalAsset(
            id = getString(0),
            itemId = getString(1),
            fileName = getString(2),
            mime = getString(3),
            byteCount = getLong(4),
            sha256 = getString(5),
            width = if (isNull(6)) null else getInt(6),
            height = if (isNull(7)) null else getInt(7),
            state = getString(8),
        )

        private fun Cursor.toActivity() = LocalActivityEvent(
            id = getString(0),
            itemId = if (isNull(1)) null else getString(1),
            at = getString(2),
            action = getString(3),
            outcome = getString(4),
            reason = if (isNull(5)) null else getString(5),
        )
    }
}
