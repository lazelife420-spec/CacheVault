package com.prooffoundry.cachevaultmobile.ui.components

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.ui.ClipListFormatter
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@Composable
fun ClipCard(
    clip: ClipSummary,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    showThumbnail: Boolean = false,
    thumbnailBytes: ByteArray? = null,
) {
    val badge = ClipListFormatter.typeBadge(clip)
    val presentation = ClipListFormatter.cardPresentation(clip)
    val monoPreview = badge == "CODE" || badge == "CMD"
    val source = ClipListFormatter.sourceLabel(clip)
    val thumbnail = remember(thumbnailBytes) {
        thumbnailBytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    width = 1.dp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(10.dp),
                )
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.Top,
        ) {
            if (showThumbnail && ClipKinds.isImageReference(clip)) {
                ThumbnailBox(thumbnail, clip.preview, large = false)
            }
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TypeBadge(badge)
                    if (!source.isNullOrBlank()) {
                        Text(
                            source,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f),
                        )
                    } else {
                        Row(modifier = Modifier.weight(1f)) {}
                    }
                    if (clip.isFavorite) {
                        Icon(
                            Icons.Default.Star,
                            contentDescription = "Favorite",
                            tint = StampGold,
                            modifier = Modifier.size(12.dp),
                        )
                    }
                    Text(
                        "Proof",
                        style = MaterialTheme.typography.labelSmall,
                        color = StampGold.copy(alpha = 0.75f),
                    )
                }
                Text(
                    presentation.title,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (presentation.preview.isNotBlank()) {
                    Text(
                        presentation.preview,
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontFamily = if (monoPreview) FontFamily.Monospace else FontFamily.Default,
                        ),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = ClipListFormatter.PREVIEW_MAX_LINES,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(
                    presentation.dateLine,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
                )
            }
        }
    }
}

@Composable
fun ScreenshotGridCard(
    clip: ClipSummary,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    thumbnailBytes: ByteArray? = null,
) {
    val presentation = ClipListFormatter.cardPresentation(clip)
    val thumbnail = remember(thumbnailBytes) {
        thumbnailBytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(
            modifier = Modifier
                .border(
                    width = 1.dp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(10.dp),
                )
                .padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            ThumbnailBox(
                thumbnail = thumbnail,
                contentDescription = clip.preview,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(96.dp),
                large = true,
            )
            Text(
                presentation.title,
                style = MaterialTheme.typography.labelMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (presentation.preview.isNotBlank()) {
                Text(
                    presentation.preview,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                presentation.dateLine,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.75f),
            )
        }
    }
}

@Composable
private fun ThumbnailBox(
    thumbnail: androidx.compose.ui.graphics.ImageBitmap?,
    contentDescription: String,
    modifier: Modifier = Modifier,
    large: Boolean = false,
) {
    Surface(
        modifier = if (large) {
            modifier
        } else {
            modifier.size(52.dp)
        },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.background,
    ) {
        if (thumbnail != null) {
            Image(
                bitmap = thumbnail,
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxWidth(),
            )
        } else {
            Icon(
                Icons.Default.Image,
                contentDescription = null,
                tint = ProofTeal,
                modifier = Modifier.padding(10.dp),
            )
        }
    }
}

@Composable
private fun TypeBadge(label: String) {
    Surface(
        shape = RoundedCornerShape(4.dp),
        color = ProofTeal.copy(alpha = 0.12f),
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 1.dp),
            style = MaterialTheme.typography.labelSmall,
            color = ProofTeal,
        )
    }
}
