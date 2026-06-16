package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.ClipSummary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ClipDetailScreen(
    clip: ClipSummary,
    onBack: () -> Unit,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onSave: () -> Unit,
    onViewAsset: () -> Unit,
) {
    val clipboard = LocalClipboardManager.current
    val context = LocalContext.current
    val text = clip.content.ifBlank { clip.preview }
    val isLink = ClipKinds.isLink(clip)
    val isPath = ClipKinds.isPath(clip)
    val isImage = ClipKinds.isImageReference(clip)
    val linkUrl = ClipKinds.linkUrl(clip)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Clip detail") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (clip.isSensitive) {
                Text("Sensitive clip — handle carefully.", color = MaterialTheme.colorScheme.secondary)
            }
            if (clip.deletedAt != null) {
                Text("Recently Removed (read-only)", style = MaterialTheme.typography.labelMedium)
            }
            if (isPath && !isImage) {
                Text(
                    "File path reference (metadata only). Original PC files are not copied.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (isImage && !clip.hasAsset) {
                Text(
                    stringResource(R.string.image_asset_placeholder),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(text, style = MaterialTheme.typography.bodyLarge)
            clip.sourceApp?.let { Text("Source: $it", style = MaterialTheme.typography.labelSmall) }
            clip.createdAt?.let { Text("Saved: $it", style = MaterialTheme.typography.labelSmall) }

            when {
                isLink && linkUrl != null -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(linkUrl)))
                        }) {
                            Text("Open Link")
                        }
                        Button(onClick = {
                            clipboard.setText(AnnotatedString(linkUrl))
                            onCopy()
                        }) {
                            Text("Copy")
                        }
                        Button(onClick = {
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, linkUrl)
                            }
                            context.startActivity(Intent.createChooser(intent, "Share link"))
                            onShare()
                        }) {
                            Text("Share")
                        }
                    }
                }
                isImage -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedButton(onClick = {
                            onViewAsset()
                            Toast.makeText(
                                context,
                                if (clip.hasAsset) "Loading image from PC…"
                                else "Image preview when desktop stores screenshot assets.",
                                Toast.LENGTH_SHORT,
                            ).show()
                        }) {
                            Text("View")
                        }
                        Button(onClick = {
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, text)
                            }
                            context.startActivity(Intent.createChooser(intent, "Share"))
                            onShare()
                        }) {
                            Text("Share")
                        }
                        OutlinedButton(onClick = {
                            onSave()
                            Toast.makeText(
                                context,
                                "Save to Phone will download when PC image assets are available.",
                                Toast.LENGTH_LONG,
                            ).show()
                        }) {
                            Text("Save to Phone")
                        }
                    }
                }
                else -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = {
                            clipboard.setText(AnnotatedString(text))
                            onCopy()
                        }) {
                            Text("Copy")
                        }
                        Button(onClick = {
                            val intent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, text)
                            }
                            context.startActivity(Intent.createChooser(intent, "Share clip"))
                            onShare()
                        }) {
                            Text("Share")
                        }
                    }
                }
            }
        }
    }
}
