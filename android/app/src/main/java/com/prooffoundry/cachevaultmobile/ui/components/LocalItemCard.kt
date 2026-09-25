package com.prooffoundry.cachevaultmobile.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Notes
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.data.local.LocalItem
import com.prooffoundry.cachevaultmobile.data.local.LocalItemKind
import com.prooffoundry.cachevaultmobile.ui.ClipListFormatter
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

/**
 * Card for a phone-local vault item. The "This phone" badge keeps local
 * records visually distinct from remote PC clips (which carry "On PC").
 * Sensitive previews are masked until an explicit reveal in detail view —
 * lists, search, recent and activity never render sensitive bodies.
 */
@Composable
fun LocalItemCard(
    item: LocalItem,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onCopy: (() -> Unit)? = null,
) {
    val (kindIcon, kindLabel) = when (item.kind) {
        LocalItemKind.LINK -> Icons.Default.Link to "Link"
        LocalItemKind.IMAGE -> Icons.Default.Image to "Image"
        LocalItemKind.TEXT -> Icons.AutoMirrored.Filled.Notes to "Text"
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
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Leading kind tile — the concept board's icon rows: type reads at
            // a glance without a text badge shouting on every card.
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = if (item.isSensitive) {
                    StampGold.copy(alpha = 0.14f)
                } else {
                    ProofTeal.copy(alpha = 0.13f)
                },
            ) {
                Icon(
                    kindIcon,
                    contentDescription = kindLabel,
                    tint = if (item.isSensitive) StampGold else ProofTeal,
                    modifier = Modifier
                        .padding(9.dp)
                        .size(20.dp),
                )
            }
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                if (item.isSensitive) {
                    Text(
                        "Sensitive — tap to open",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = StampGold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                } else {
                    Text(
                        item.title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (item.preview.isNotBlank()) {
                        Text(
                            item.preview,
                            style = MaterialTheme.typography.bodySmall.copy(
                                fontFamily = FontFamily.Default,
                            ),
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = ClipListFormatter.PREVIEW_MAX_LINES,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "$kindLabel · ${ClipListFormatter.formatRelativeWhen(item.createdAt)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
                    )
                    if (item.isFavorite) {
                        Icon(
                            Icons.Default.Star,
                            contentDescription = "Favorite",
                            tint = StampGold,
                            modifier = Modifier.size(11.dp),
                        )
                    }
                }
            }
            if (onCopy != null && item.kind != LocalItemKind.IMAGE) {
                IconButton(
                    onClick = onCopy,
                    modifier = Modifier.size(32.dp),
                ) {
                    Icon(
                        Icons.Default.ContentCopy,
                        contentDescription = "Copy",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(17.dp),
                    )
                }
            }
        }
    }
}
