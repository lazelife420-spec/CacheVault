package com.prooffoundry.cachevaultmobile.data

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.provider.OpenableColumns
import androidx.core.content.FileProvider
import java.io.File

/** An image picked up from the Android Share Sheet, ready to send to the PC. */
data class SharedImage(val bytes: ByteArray, val mimeType: String, val name: String?)

/** Explicit share/save helpers for image bytes fetched from the PC bridge. */
object ImageFileHelper {
    /** Keep in sync with desktop `inbox.MAX_MOBILE_IMAGE_BYTES` (10 MB). */
    const val MAX_IMAGE_BYTES = 10 * 1024 * 1024

    private val ALLOWED_MIME = setOf(
        "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp", "image/bmp",
    )

    /**
     * Read a shared image from [uri]. Returns null if it can't be read, isn't a
     * supported image type, or exceeds [MAX_IMAGE_BYTES].
     */
    fun readSharedImage(context: Context, uri: Uri, declaredType: String?): SharedImage? {
        val resolver = context.contentResolver
        val mime = (resolver.getType(uri) ?: declaredType ?: "").lowercase()
        if (mime !in ALLOWED_MIME) return null
        val bytes = runCatching {
            resolver.openInputStream(uri)?.use { it.readBytes() }
        }.getOrNull() ?: return null
        if (bytes.isEmpty() || bytes.size > MAX_IMAGE_BYTES) return null
        val name = runCatching {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
        }.getOrNull()
        return SharedImage(bytes, if (mime == "image/jpg") "image/jpeg" else mime, name)
    }

    fun shareImage(context: Context, bytes: ByteArray, mimeType: String, clipId: String) {
        val uri = writeCacheFile(context, bytes, mimeType, "cv_share_$clipId")
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = mimeType
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Share image"))
    }

    /** Fallback for when CacheVault's own viewer isn't enough — hand the bytes to any app that can open images. */
    fun openInOtherApp(context: Context, bytes: ByteArray, mimeType: String, clipId: String) {
        val uri = writeCacheFile(context, bytes, mimeType, "cv_open_$clipId")
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mimeType)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Open image with"))
    }

    private fun writeCacheFile(context: Context, bytes: ByteArray, mimeType: String, baseName: String): Uri {
        val ext = when {
            mimeType.contains("png", ignoreCase = true) -> "png"
            mimeType.contains("jpeg", ignoreCase = true) ||
                mimeType.contains("jpg", ignoreCase = true) -> "jpg"
            else -> "img"
        }
        val file = File(context.cacheDir, "$baseName.$ext")
        file.writeBytes(bytes)
        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file,
        )
    }

    fun saveToPictures(context: Context, bytes: ByteArray, mimeType: String, name: String): Boolean {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name)
            put(MediaStore.Images.Media.MIME_TYPE, mimeType)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(
                    MediaStore.Images.Media.RELATIVE_PATH,
                    "${Environment.DIRECTORY_PICTURES}/CacheVault",
                )
            }
        }
        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            ?: return false
        resolver.openOutputStream(uri)?.use { it.write(bytes) } ?: return false
        return true
    }
}
