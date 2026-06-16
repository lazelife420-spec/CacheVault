package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.data.ClipFeed
import com.prooffoundry.cachevaultmobile.ui.AppUiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    state: AppUiState,
    onSearch: (String) -> Unit,
    onFeed: (ClipFeed, String?) -> Unit,
    onOpenClip: (String) -> Unit,
    onSettings: () -> Unit,
    onRefresh: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Cache Vault Mobile")
                        Text(
                            "Connected: ${state.hostLabel.ifBlank { "PC" }}",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onRefresh) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
        ) {
            OutlinedTextField(
                value = state.searchQuery,
                onValueChange = onSearch,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Search clips") },
                singleLine = true,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FeedChip("All", state.activeFeed == ClipFeed.ALL) {
                    onFeed(ClipFeed.ALL, null)
                }
                FeedChip("Favorites", state.activeFeed == ClipFeed.FAVORITES) {
                    onFeed(ClipFeed.FAVORITES, null)
                }
                FeedChip("Removed", state.activeFeed == ClipFeed.RECENTLY_REMOVED) {
                    onFeed(ClipFeed.RECENTLY_REMOVED, null)
                }
            }
            if (state.collections.isNotEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    state.collections.take(4).forEach { entry ->
                        FeedChip(
                            entry.name,
                            state.activeFeed == ClipFeed.COLLECTION &&
                                state.selectedCollection == entry.name,
                        ) {
                            onFeed(ClipFeed.COLLECTION, entry.name)
                        }
                    }
                }
            }
            if (!state.error.isNullOrBlank()) {
                Text(state.error, color = MaterialTheme.colorScheme.error)
            }
            if (state.loading) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.Center,
                ) {
                    CircularProgressIndicator()
                }
            }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.clips, key = { it.id }) { clip ->
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onOpenClip(clip.id) }
                            .padding(vertical = 8.dp),
                    ) {
                        Text(clip.preview.ifBlank { "(no preview)" })
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            if (clip.isFavorite) Text("★", style = MaterialTheme.typography.labelSmall)
                            if (clip.isSensitive) Text("sensitive", style = MaterialTheme.typography.labelSmall)
                            if (clip.deletedAt != null) Text("removed", style = MaterialTheme.typography.labelSmall)
                            clip.collection?.let {
                                Text(it, style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FeedChip(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label) },
    )
}
