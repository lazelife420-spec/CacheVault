package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Star
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.data.local.LocalAsset
import com.prooffoundry.cachevaultmobile.data.local.LocalItem
import com.prooffoundry.cachevaultmobile.data.local.LocalItemKind
import com.prooffoundry.cachevaultmobile.data.local.LocalSafe
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository
import com.prooffoundry.cachevaultmobile.ui.ClipListFormatter
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Phone-local item detail (CV-MOBILE-1). Every action on this screen is local:
 * copy, share, favorite, move and remove touch only this phone's vault. The
 * content hash shown here is computed on this phone and is not a desktop
 * receipt or a remote signature.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LocalItemDetailScreen(
    item: LocalItem?,
    asset: LocalAsset?,
    safes: List<LocalSafe>,
    revealed: Boolean,
    repository: LocalVaultRepository,
    onBack: () -> Unit,
    onCopy: (LocalItem) -> Unit,
    onShareText: (LocalItem) -> Unit,
    onShareImage: (LocalItem, LocalAsset) -> Unit,
    onToggleFavorite: (LocalItem) -> Unit,
    onMoveToSafe: (String, String) -> Unit,
    onRemove: (LocalItem) -> Unit,
    onRestore: (LocalItem) -> Unit,
    onReveal: (String) -> Unit,
) {
    val context = LocalContext.current
    var safeMenuOpen by remember { mutableStateOf(false) }
    val bitmap by produceState<androidx.compose.ui.graphics.ImageBitmap?>(null, asset?.fileName) {
        val name = asset?.fileName
        if (name != null) {
            value = withContext(Dispatchers.IO) {
                repository.decodeAssetThumbnail(name, maxEdgePx = 1200)
            }?.asImageBitmap()
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        item?.title ?: "Item",
                        maxLines = 1,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (item != null) {
                        IconButton(onClick = { onToggleFavorite(item) }) {
                            Icon(
                                if (item.isFavorite) Icons.Filled.Star else Icons.Outlined.Star,
                                contentDescription = if (item.isFavorite) "Unfavorite" else "Favorite",
                                tint = if (item.isFavorite) StampGold else MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
            )
        },
    ) { padding ->
        if (item == null) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(20.dp),
            ) {
                Text(
                    "Loading…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            return@Scaffold
        }
        val removed = item.removedAt != null
        val showSensitiveMask = item.isSensitive && !revealed

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Surface(shape = RoundedCornerShape(6.dp), color = ProofTeal.copy(alpha = 0.15f)) {
                Text(
                    when (item.kind) {
                        LocalItemKind.LINK -> "LINK"
                        LocalItemKind.IMAGE -> "IMAGE"
                        LocalItemKind.TEXT -> "TXT"
                    } + " · this phone",
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelMedium,
                    color = ProofTeal,
                )
            }
            if (item.isSensitive) {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.errorContainer,
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            "Sensitive content — ${item.sensitiveReason ?: "detected on this phone"}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                        if (!revealed && !removed) {
                            OutlinedButton(
                                onClick = { onReveal(item.id) },
                                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                            ) { Text("Reveal") }
                        }
                    }
                }
            }

            when (item.kind) {
                LocalItemKind.IMAGE -> {
                    if (asset != null && bitmap != null) {
                        Image(
                            bitmap = bitmap!!,
                            contentDescription = item.title,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 480.dp),
                        )
                        Text(
                            "${asset.mime} · ${asset.byteCount / 1024} KB" +
                                (asset.width?.let { w -> asset.height?.let { h -> " · ${w}×${h}" } } ?: ""),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        Text(
                            "Image bytes are not available on this phone.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                else -> {
                    if (showSensitiveMask) {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(10.dp),
                            color = MaterialTheme.colorScheme.surface,
                        ) {
                            Text(
                                "Content hidden — tap Reveal to show it.",
                                modifier = Modifier.padding(14.dp),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surface,
                        ) {
                            Text(
                                item.content.orEmpty().ifBlank { "(no content)" },
                                modifier = Modifier.padding(18.dp),
                                style = MaterialTheme.typography.bodyLarge.copy(
                                    fontFamily = FontFamily.Default,
                                ),
                            )
                        }
                    }
                }
            }
            HorizontalDivider()

            if (removed) {
                Button(onClick = { onRestore(item) }, modifier = Modifier.fillMaxWidth()) {
                    Text("Restore to this phone")
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    when (item.kind) {
                        LocalItemKind.IMAGE -> {
                            Button(
                                onClick = { asset?.let { onShareImage(item, it) } },
                                enabled = asset != null,
                                modifier = Modifier
                                    .weight(1f)
                                    .height(44.dp),
                            ) { Text("Share") }
                        }
                        else -> {
                            Button(
                                onClick = {
                                    if (item.isSensitive && !revealed) {
                                        Toast.makeText(
                                            context,
                                            "Reveal before copying sensitive content.",
                                            Toast.LENGTH_SHORT,
                                        ).show()
                                    } else {
                                        onCopy(item)
                                    }
                                },
                                enabled = !showSensitiveMask || revealed,
                                modifier = Modifier
                                    .weight(1f)
                                    .height(44.dp),
                            ) { Text("Copy") }
                            OutlinedButton(
                                onClick = {
                                    if (item.isSensitive && !revealed) {
                                        Toast.makeText(
                                            context,
                                            "Reveal before sharing sensitive content.",
                                            Toast.LENGTH_SHORT,
                                        ).show()
                                    } else {
                                        onShareText(item)
                                    }
                                },
                                modifier = Modifier
                                    .weight(1f)
                                    .height(44.dp),
                            ) { Text("Share") }
                        }
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    OutlinedButton(
                        onClick = { safeMenuOpen = true },
                        modifier = Modifier
                            .weight(1f)
                            .height(40.dp),
                    ) {
                        Text("Move to Safe")
                    }
                    DropdownMenu(
                        expanded = safeMenuOpen,
                        onDismissRequest = { safeMenuOpen = false },
                    ) {
                        safes.forEach { safe ->
                            DropdownMenuItem(
                                text = { Text(safe.name) },
                                onClick = {
                                    safeMenuOpen = false
                                    onMoveToSafe(item.id, safe.id)
                                },
                            )
                        }
                    }
                    OutlinedButton(
                        onClick = { onRemove(item) },
                        modifier = Modifier
                            .weight(1f)
                            .height(40.dp),
                    ) {
                        Text("Remove", color = MaterialTheme.colorScheme.error)
                    }
                }
                Text(
                    "Remove moves the item to Recently Removed on this phone only. Nothing on a paired PC is changed.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            // Provenance stays available without competing with the content:
            // quiet metadata block at the bottom of the detail flow.
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(10.dp),
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.6f),
            ) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    DetailMeta("Saved", ClipListFormatter.formatWhen(item.createdAt))
                    safes.firstOrNull { it.id == item.safeId }?.let {
                        DetailMeta("Safe", it.name)
                    }
                    item.contentHash?.let {
                        DetailMeta("SHA-256 (computed on this phone)", it.take(16) + "…")
                    }
                    if (removed) {
                        DetailMeta("Removed", ClipListFormatter.formatWhen(item.removedAt))
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
        Text(
            value,
            style = MaterialTheme.typography.labelMedium.copy(fontFamily = FontFamily.Monospace),
            fontWeight = FontWeight.Normal,
        )
    }
}
