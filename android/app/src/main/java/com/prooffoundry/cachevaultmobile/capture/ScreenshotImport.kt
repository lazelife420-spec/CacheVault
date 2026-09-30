package com.prooffoundry.cachevaultmobile.capture

import android.content.ContentUris
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.provider.MediaStore
import androidx.core.content.ContextCompat
import com.prooffoundry.cachevaultmobile.data.local.LocalIngestion
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultDatabase
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Watches MediaStore for new screenshots and imports them into the phone-local
 * vault. Screenshot detection is conventional: a path under a `Screenshots`
 * directory or a `Screenshot`-prefixed filename. Only rows newer than the
 * stored watermark are imported — enabling capture never bulk-imports history.
 */
class ScreenshotImport(
    private val context: Context,
    private val repository: LocalVaultRepository,
    private val store: CaptureStore,
) {
    private val resolver get() = context.contentResolver
    private val mutex = Mutex()

    /** IDs that failed import this session — skipped so one bad row can't wedge the queue. */
    private val failedIds = mutableSetOf<Long>()

    suspend fun seedWatermarkIfNeeded() {
        if (store.screenshotWatermarkSeeded) return
        store.screenshotWatermark = queryMaxId()
        store.screenshotWatermarkSeeded = true
    }

    /**
     * Import every new screenshot row above the watermark. Returns count
     * imported. Serialized: MediaStore fires onChange for the insert AND the
     * scanner's update of the same row — without the mutex, two observers pass
     * the watermark check concurrently and the row imports twice.
     */
    suspend fun importNew(vaultLocked: Boolean): Int = mutex.withLock {
        if (!hasImagePermission(context)) return@withLock 0
        seedWatermarkIfNeeded()
        if (vaultLocked) return@withLock 0
        val watermark = store.screenshotWatermark
        val rows = queryAfter(watermark)
        var imported = 0
        var maxSeen = watermark
        for (row in rows.sortedBy { it.id }) {
            maxSeen = maxOf(maxSeen, row.id)
            if (row.id in failedIds) {
                store.screenshotWatermark = maxSeen
                continue
            }
            val uri = ContentUris.withAppendedId(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, row.id)
            try {
                repository.saveImage(
                    declaredMime = row.mime,
                    displayName = row.displayName,
                    safeId = LocalVaultDatabase.DEFAULT_SAFE_ID,
                    openStream = { resolver.openInputStream(uri) },
                    sourceLabel = "screenshot",
                )
                imported++
            } catch (e: Throwable) {
                failedIds += row.id
                runCatching {
                    repository.recordFailedSave("screenshot_${LocalIngestion.failureReason(e)}")
                }
            }
            store.screenshotWatermark = maxSeen
        }
        imported
    }

    private data class Row(val id: Long, val displayName: String?, val path: String?, val mime: String?)

    private fun queryAfter(watermark: Long): List<Row> {
        val projection = mutableListOf(
            MediaStore.Images.Media._ID,
            MediaStore.Images.Media.DISPLAY_NAME,
            MediaStore.Images.Media.MIME_TYPE,
        )
        val pathColumn = if (Build.VERSION.SDK_INT >= 29) {
            MediaStore.Images.Media.RELATIVE_PATH.also { projection += it }
        } else {
            @Suppress("DEPRECATION")
            MediaStore.Images.Media.DATA.also { projection += it }
        }
        val collection = if (Build.VERSION.SDK_INT >= 29) {
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
        } else {
            MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        }
        val out = mutableListOf<Row>()
        runCatching {
            resolver.query(
                collection,
                projection.toTypedArray(),
                "${MediaStore.Images.Media._ID} > ?",
                arrayOf(watermark.toString()),
                "${MediaStore.Images.Media._ID} DESC",
            )?.use { c ->
                val idCol = c.getColumnIndexOrThrow(MediaStore.Images.Media._ID)
                val nameCol = c.getColumnIndexOrThrow(MediaStore.Images.Media.DISPLAY_NAME)
                val mimeCol = c.getColumnIndexOrThrow(MediaStore.Images.Media.MIME_TYPE)
                val pathCol = c.getColumnIndexOrThrow(pathColumn)
                var scanned = 0
                while (c.moveToNext() && scanned < SCAN_LIMIT) {
                    scanned++
                    val path = c.getString(pathCol)
                    val name = c.getString(nameCol)
                    if (looksLikeScreenshot(path, name)) {
                        out += Row(
                            id = c.getLong(idCol),
                            displayName = name,
                            path = path,
                            mime = c.getString(mimeCol),
                        )
                    }
                }
            }
        }
        return out
    }

    private fun queryMaxId(): Long {
        runCatching {
            resolver.query(
                if (Build.VERSION.SDK_INT >= 29) {
                    MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
                } else {
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI
                },
                arrayOf(MediaStore.Images.Media._ID),
                null,
                null,
                "${MediaStore.Images.Media._ID} DESC",
            )?.use { c -> if (c.moveToFirst()) return c.getLong(0) }
        }
        return 0L
    }

    companion object {
        private const val SCAN_LIMIT = 50

        fun hasImagePermission(context: Context): Boolean {
            val perm = when {
                Build.VERSION.SDK_INT >= 34 -> android.Manifest.permission.READ_MEDIA_IMAGES
                Build.VERSION.SDK_INT >= 33 -> android.Manifest.permission.READ_MEDIA_IMAGES
                else -> android.Manifest.permission.READ_EXTERNAL_STORAGE
            }
            return ContextCompat.checkSelfPermission(context, perm) ==
                PackageManager.PERMISSION_GRANTED ||
                (
                    Build.VERSION.SDK_INT >= 34 &&
                        ContextCompat.checkSelfPermission(
                            context,
                            android.Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED,
                        ) == PackageManager.PERMISSION_GRANTED
                    )
        }

        /** Pure predicate — unit-tested. */
        internal fun looksLikeScreenshot(path: String?, displayName: String?): Boolean {
            val p = path?.replace('\\', '/') ?: ""
            if (p.contains("/Screenshots/", ignoreCase = true) ||
                p.endsWith("/Screenshots", ignoreCase = true)
            ) {
                return true
            }
            val n = displayName ?: ""
            return n.startsWith("Screenshot", ignoreCase = true)
        }
    }
}
