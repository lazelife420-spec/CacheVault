package com.prooffoundry.cachevaultmobile.data.local

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.InputStream
import java.util.UUID

/**
 * App-private image file ownership for the phone-local vault.
 *
 * Ingest stages bytes into a uniquely named file inside
 * `<files>/local_assets/staging/` with a bounded read (never an unbounded
 * `readBytes()` allocation on an unvalidated stream), validates MIME and
 * decode dimensions, hashes the bytes, then renames into
 * `<files>/local_assets/`. Database commit happens separately in
 * [LocalVaultRepository]; a crash between the two leaves a staging file that
 * `reconcileOrphans()` removes on the next open — this is a narrow,
 * documented recovery policy, not a claim that file renames are atomic with
 * SQL.
 */
class LocalAssetStore(
    private val filesDir: File,
    private val dimsProbe: ImageDimsProbe = AndroidImageDimsProbe,
) {
    constructor(context: Context) : this(context.filesDir)

    private val assetsDir: File get() = File(filesDir, ASSETS_DIR_NAME)
    private val stagingDir: File get() = File(assetsDir, STAGING_DIR_NAME)

    data class StagedImage(
        val file: File,
        val mime: String,
        val byteCount: Long,
        val sha256: String,
        val width: Int?,
        val height: Int?,
    )

    /**
     * Stage + validate + finalize an image stream into app-owned storage.
     * Throws [LocalVaultError] subclasses on rejection; removes only the
     * staging file it created on failure.
     */
    fun importStream(declaredMime: String?, openStream: () -> InputStream?): StagedImage {
        val mime = (declaredMime ?: "").lowercase()
        if (mime !in LocalVaultPolicy.ALLOWED_IMAGE_MIME) {
            throw LocalVaultError.UnsupportedImage()
        }
        val staging = File(stagingDir.also { it.mkdirs() }, "stage_${UUID.randomUUID()}")
        val sha = MessageDigestHolder()
        var total = 0L
        try {
            openStream()?.use { input ->
                FileOutputStream(staging).use { out ->
                    val buffer = ByteArray(COPY_BUFFER)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        total += read
                        if (total > LocalVaultPolicy.MAX_IMAGE_BYTES) {
                            throw LocalVaultError.ImageTooLarge()
                        }
                        sha.update(buffer, 0, read)
                        out.write(buffer, 0, read)
                    }
                }
            } ?: throw LocalVaultError.ImageUnreadable()
        } catch (e: LocalVaultError) {
            staging.delete()
            throw e
        } catch (e: Exception) {
            staging.delete()
            throw LocalVaultError.ImageUnreadable()
        }
        if (total <= 0) {
            staging.delete()
            throw LocalVaultError.ImageUnreadable()
        }

        val dims = dimsProbe.probe(staging) ?: run {
            staging.delete()
            throw LocalVaultError.ImageUnreadable()
        }
        if (dims.width <= 0 || dims.height <= 0 ||
            dims.width.toLong() * dims.height.toLong() > LocalVaultPolicy.MAX_IMAGE_PIXELS
        ) {
            staging.delete()
            throw LocalVaultError.UnsupportedImage()
        }

        val digestHex = sha.hex()
        val final = File(assetsDir, "${UUID.randomUUID()}.${LocalVaultPolicy.extensionForMime(mime)}")
        if (!staging.renameTo(final)) {
            staging.delete()
            throw LocalVaultError.ImageUnreadable()
        }
        return StagedImage(final, normalizeMime(mime), total, digestHex, dims.width, dims.height)
    }

    /**
     * Absolute path for an asset file that must already exist inside
     * [assetsDir]. Generated asset names are always flat — a name containing a
     * separator, a traversal element, the staging dir, or a missing file is
     * rejected, never silently resolved.
     */
    fun fileFor(fileName: String): File? {
        if (fileName.isBlank() || fileName != File(fileName).name) return null
        val f = File(assetsDir, fileName)
        val canonical = runCatching { f.canonicalFile }.getOrNull() ?: return null
        val root = runCatching { assetsDir.canonicalFile }.getOrNull() ?: return null
        if (canonical.parentFile != root || !canonical.isFile) return null
        return canonical
    }

    fun openRead(fileName: String): InputStream? =
        fileFor(fileName)?.let { runCatching { FileInputStream(it) }.getOrNull() }

    fun delete(fileName: String) {
        fileFor(fileName)?.delete()
    }

    /**
     * Remove staging leftovers and any asset file not referenced by
     * [keepFileNames]. Only files inside the app-owned directories are ever
     * touched; returns nothing and tolerates partial failure.
     */
    fun reconcileOrphans(keepFileNames: Set<String>) {
        val root = runCatching { assetsDir.canonicalFile }.getOrNull() ?: return
        stagingDir.listFiles()?.forEach { it.delete() }
        assetsDir.listFiles()?.forEach { f ->
            if (!f.isFile) return@forEach
            if (f.name in keepFileNames) return@forEach
            val canonical = runCatching { f.canonicalFile }.getOrNull() ?: return@forEach
            if (canonical.path.startsWith(root.path + File.separator)) {
                canonical.delete()
            }
        }
    }

    /** Bounded decode for thumbnails — samples down so no full-resolution bitmap is held for list UI. */
    fun decodeThumbnail(fileName: String, maxEdgePx: Int = LocalVaultPolicy.MAX_THUMBNAIL_EDGE): Bitmap? {
        val f = fileFor(fileName) ?: return null
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(f.absolutePath, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sample = 1
        while (bounds.outWidth / (sample * 2) >= maxEdgePx &&
            bounds.outHeight / (sample * 2) >= maxEdgePx
        ) {
            sample *= 2
        }
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        return BitmapFactory.decodeFile(f.absolutePath, opts)
    }

    data class ImageDims(val width: Int, val height: Int)

    /** Decode-dimension probe — injectable so repository/store logic is JVM-testable. */
    fun interface ImageDimsProbe {
        fun probe(file: File): ImageDims?
    }

    object AndroidImageDimsProbe : ImageDimsProbe {
        override fun probe(file: File): ImageDims? {
            val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(file.absolutePath, opts)
            return if (opts.outWidth > 0 && opts.outHeight > 0) {
                ImageDims(opts.outWidth, opts.outHeight)
            } else {
                null
            }
        }
    }

    private class MessageDigestHolder {
        private val digest = java.security.MessageDigest.getInstance("SHA-256")
        fun update(bytes: ByteArray, offset: Int, length: Int) = digest.update(bytes, offset, length)
        fun hex(): String = digest.digest().joinToString("") { "%02x".format(it) }
    }

    companion object {
        const val ASSETS_DIR_NAME = "local_assets"
        const val STAGING_DIR_NAME = "staging"
        private const val COPY_BUFFER = 64 * 1024

        fun normalizeMime(mime: String): String =
            if (mime.equals("image/jpg", ignoreCase = true)) "image/jpeg" else mime
    }
}
