package com.prooffoundry.cachevaultmobile.ui.components

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.data.ClipFeed
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal

@Composable
fun FeedTabRow(
    selected: ClipFeed,
    onSelect: (ClipFeed) -> Unit,
    screenshotsLabel: String,
    modifier: Modifier = Modifier,
) {
    val tabs = listOf(
        ClipFeed.ALL to "All",
        ClipFeed.FAVORITES to "Favorites",
        ClipFeed.SCREENSHOTS to screenshotsLabel,
        ClipFeed.RECENT to "Recent",
    )
    val listState = rememberLazyListState()
    val selectedIndex = tabs.indexOfFirst { it.first == selected }.coerceAtLeast(0)

    LaunchedEffect(selected) {
        listState.animateScrollToItem(selectedIndex)
    }

    LazyRow(
        state = listState,
        modifier = modifier,
        contentPadding = PaddingValues(horizontal = 2.dp),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(6.dp),
    ) {
        itemsIndexed(tabs, key = { _, tab -> tab.first.name }) { _, (feed, label) ->
            CompactTab(
                label = label,
                selected = feed == selected,
                onClick = { onSelect(feed) },
            )
        }
    }
}

@Composable
private fun CompactTab(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(20.dp),
        color = if (selected) ProofTeal.copy(alpha = 0.18f) else MaterialTheme.colorScheme.surface,
        modifier = Modifier.height(36.dp),
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
            color = if (selected) ProofTeal else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
