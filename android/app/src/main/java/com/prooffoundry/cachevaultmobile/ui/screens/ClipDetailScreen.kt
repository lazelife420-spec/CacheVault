package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.data.ImageAssetState
import com.prooffoundry.cachevaultmobile.data.ImageFileHelper
import com.prooffoundry.cachevaultmobile.ui.ClipListFormatter
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ClipDetailScreen(
    clip: ClipSummary?,
    imageAsset: ImageAssetState,
    loading: Boolean,
    error: String?,
    onBack: () -> Unit,
    onRetry: (() -> Unit)?,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onSave: () -> Unit,
    onViewAsset: () -> Unit,
    onOpenFullScreen: () -> Unit,
) {
    val clipboard = LocalClipboardManager.current
    val context = LocalContext.current
    val title = clip?.let { ClipListFormatter.cardTitle(it) } ?: "Clip details"
    val text = clip?.content?.ifBlank { clip.preview }.orEmpty()
    val isLink = clip?.let { ClipKinds.isLink(it) } == true
    val isPath = clip?.let { ClipKinds.isPath(it) } == true
    val isImage = clip?.let { ClipKinds.isImageReference(it) } == true
    val isCode = clip?.classification.equals("code", ignoreCase = true) ||
        clip?.classification.equals("command", ignoreCase = true)
    val linkUrl = clip?.let { ClipKinds.linkUrl(it) }
    val badge = clip?.let { ClipListFormatter.typeBadge(it) }.orEmpty()
    val bitmap = remember(imageAsset.bytes) {
        imageAsset.bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        title,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        if (clip == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(20.dp),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    when {
                        loading -> {
                            CircularProgressIndicator()
                            Text("Loading clip details…", style = MaterialTheme.typography.bodyMedium)
                        }
                        !error.isNullOrBlank() -> {
                            Text(
                                error,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.error,
                            )
                            if (onRetry != null) {
                                Button(onClick = onRetry) { Text("Try again") }
                            }
                        }
                        else -> {
                            Text(
                                "Clip details are not available yet.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Surface(shape = RoundedCornerShape(6.dp), color = ProofTeal.copy(alpha = 0.15f)) {
                Text(
                    badge,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelMedium,
                    color = ProofTeal,
                )
            }
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(10.dp),
                color = MaterialTheme.colorScheme.surface,
            ) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    DetailMeta("Type", badge)
                    clip.sourceApp?.let { DetailMeta("Source", it) }
                    clip.createdAt?.let { DetailMeta("Saved", ClipListFormatter.formatWhen(it)) }
                    DetailMeta("Receipts", "Stored on your PC")
                }
            }
            if (clip.isSensitive) {
                Text("Sensitive clip — handle carefully.", color = MaterialTheme.colorScheme.secondary)
            }
            if (clip.deletedAt != null) {
                Text("Recently Removed (read-only)", style = MaterialTheme.typography.labelMedium)
            }
            if (isPath && !isImage) {
                Text(
                    "File path reference only. Originals stay on your PC.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (!error.isNullOrBlank()) {
                Text(
                    error,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            if (isImage) {
                when {
                    imageAsset.loading -> {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center,
                        ) {
                            CircularProgressIndicator()
                        }
                    }
                    bitmap != null -> {
                        Image(
                            bitmap = bitmap,
                            contentDescription = clip.preview,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 520.dp)
                                .clickable(onClick = onOpenFullScreen),
                        )
                    }
                    imageAsset.error != null -> {
                        Text(
                            imageAsset.error,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    !clip.hasAsset -> {
                        Text(
                            stringResource(R.string.image_asset_placeholder),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            if (!isImage || bitmap == null) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.surface,
                ) {
                    Text(
                        text.ifBlank { "(no clip content)" },
                        modifier = Modifier.padding(14.dp),
                        style = MaterialTheme.typography.bodyMedium.copy(
                            fontFamily = if (isCode) FontFamily.Monospace else FontFamily.Default,
                        ),
                    )
                }
            }
            HorizontalDivider()

            when {
                isLink && linkUrl != null -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(linkUrl)))
                        }) { Text("Open Link") }
                        Button(onClick = {
                            clipboard.setText(AnnotatedString(linkUrl))
                            onCopy()
                        }) { Text("Copy") }
                        Button(onClick = {
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, linkUrl)
                            }
                            context.startActivity(Intent.createChooser(intent, "Share link"))
                            onShare()
                        }) { Text("Share") }
                    }
                }
                isImage -> {
                    if (bitmap != null) {
                        Button(
                            onClick = onOpenFullScreen,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.view_full_screen))
                        }
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        OutlinedButton(
                            onClick = onViewAsset,
                            enabled = clip.hasAsset && !imageAsset.loading,
                        ) {
                            Text(if (bitmap == null) "View" else "Reload")
                        }
                        Button(
                            onClick = {
                                val bytes = imageAsset.bytes
                                if (bytes != null) {
                                    ImageFileHelper.shareImage(
                                        context, bytes, imageAsset.contentType, clip.id,
                                    )
                                    onShare()
                                } else {
                                    Toast.makeText(
                                        context,
                                        "Load the image from your PC first.",
                                        Toast.LENGTH_SHORT,
                                    ).show()
                                }
                            },
                            enabled = imageAsset.bytes != null,
                        ) { Text("Share") }
                        OutlinedButton(
                            onClick = {
                                val bytes = imageAsset.bytes
                                if (bytes != null) {
                                    val ok = ImageFileHelper.saveToPictures(
                                        context,
                                        bytes,
                                        imageAsset.contentType,
                                        "cachevault_${clip.id}.png",
                                    )
                                    onSave()
                                    Toast.makeText(
                                        context,
                                        if (ok) "Saved to Pictures/CacheVault"
                                        else "Could not save image",
                                        Toast.LENGTH_LONG,
                                    ).show()
                                } else {
                                    Toast.makeText(
                                        context,
                                        "Load the image from your PC first.",
                                        Toast.LENGTH_SHORT,
                                    ).show()
                                }
                            },
                            enabled = imageAsset.bytes != null,
                        ) { Text("Save to Phone") }
                    }
                }
                else -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {
                            clipboard.setText(AnnotatedString(text))
                            onCopy()
                        }) { Text("Copy") }
                        Button(onClick = {
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, text)
                            }
                            context.startActivity(Intent.createChooser(intent, "Share clip"))
                            onShare()
                        }) { Text("Share") }
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailMeta(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
