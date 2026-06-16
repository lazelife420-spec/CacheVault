package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.ClipFeed
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.ui.AppUiState
import com.prooffoundry.cachevaultmobile.ui.ConnectionState
import com.prooffoundry.cachevaultmobile.ui.connectionSubtitle
import com.prooffoundry.cachevaultmobile.ui.components.ClipCard
import com.prooffoundry.cachevaultmobile.ui.components.FeedTabRow
import com.prooffoundry.cachevaultmobile.ui.components.ScreenshotGridCard
import com.prooffoundry.cachevaultmobile.ui.components.VaultSummarySection
import com.prooffoundry.cachevaultmobile.ui.resolveConnectionState
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterialApi::class)
@Composable
fun HomeScreen(
    state: AppUiState,
    onSearch: (String) -> Unit,
    onFeed: (ClipFeed, String?) -> Unit,
    onOpenClip: (String) -> Unit,
    onSettings: () -> Unit,
    onRefresh: () -> Unit,
) {
    val connection = resolveConnectionState(state.status, state.error, state.loading)
    val screenshotMode = state.activeFeed == ClipFeed.SCREENSHOTS && state.searchQuery.isBlank()
    val pullState = rememberPullRefreshState(
        refreshing = state.loading,
        onRefresh = onRefresh,
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            "Cache Vault",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            connectionSubtitle(connection, state.hostLabel),
                            style = MaterialTheme.typography.labelMedium,
                            color = connectionColor(connection),
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onRefresh) {
                        Icon(
                            Icons.Default.Refresh,
                            contentDescription = "Refresh",
                            modifier = Modifier.height(20.dp),
                        )
                    }
                    IconButton(onClick = onSettings) {
                        Icon(
                            Icons.Default.Settings,
                            contentDescription = "Settings",
                            modifier = Modifier.height(20.dp),
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
                modifier = Modifier.height(56.dp),
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .pullRefresh(pullState),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 14.dp),
            ) {
                OutlinedTextField(
                    value = state.searchQuery,
                    onValueChange = onSearch,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    placeholder = { Text(stringResource(R.string.search_hint)) },
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodyMedium,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                        focusedContainerColor = MaterialTheme.colorScheme.surface,
                    ),
                    trailingIcon = {
                        if (state.searchQuery.isNotBlank()) {
                            IconButton(onClick = { onSearch("") }) {
                                Icon(Icons.Default.Clear, contentDescription = "Clear search")
                            }
                        }
                    },
                )
                FeedTabRow(
                    selected = state.activeFeed,
                    onSelect = { feed -> onFeed(feed, null) },
                    screenshotsLabel = stringResource(R.string.screenshots_tab),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp),
                )
                if (state.searchQuery.isNotBlank() && !state.loading) {
                    Text(
                        "${state.clips.size} result(s)",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(bottom = 4.dp),
                    )
                }
                if (state.activeFeed == ClipFeed.ALL && state.searchQuery.isBlank()) {
                    VaultSummarySection(state.vaultSummary)
                    QuickActionRow(
                        onRefresh = onRefresh,
                        onScreenshots = { onFeed(ClipFeed.SCREENSHOTS, null) },
                        onSettings = onSettings,
                    )
                }
                if (!state.error.isNullOrBlank() && connection != ConnectionState.CONNECTED) {
                    ConnectionBanner(connection, state.error)
                }
                if (state.loading && state.clips.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                        contentAlignment = Alignment.Center,
                    ) {
                        LoadingState()
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                    ) {
                        if (screenshotMode) {
                            ScreenshotGrid(state = state, onOpenClip = onOpenClip)
                        } else {
                            ClipList(state = state, onOpenClip = onOpenClip)
                        }
                    }
                }
            }
            PullRefreshIndicator(
                refreshing = state.loading,
                state = pullState,
                modifier = Modifier.align(Alignment.TopCenter),
                contentColor = ProofTeal,
            )
        }
    }
}

@Composable
private fun QuickActionRow(
    onRefresh: () -> Unit,
    onScreenshots: () -> Unit,
    onSettings: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        QuickActionChip("Refresh", onRefresh)
        QuickActionChip("Screenshots", onScreenshots)
        QuickActionChip("Settings", onSettings)
    }
}

@Composable
private fun QuickActionChip(label: String, onClick: () -> Unit) {
    TextButton(
        onClick = onClick,
        modifier = Modifier.height(32.dp),
        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = ProofTeal)
    }
}

@Composable
private fun ConnectionBanner(connection: ConnectionState, error: String) {
    val (title, body) = when (connection) {
        ConnectionState.REPAIR_NEEDED -> "Re-pair needed" to stringResource(R.string.repair_needed_body)
        ConnectionState.REVOKED -> "Device revoked" to stringResource(R.string.device_revoked_body)
        ConnectionState.OFFLINE -> "Not connected" to stringResource(R.string.no_pc_found_body)
        ConnectionState.MOBILE_ACCESS_OFF -> "Mobile Access off" to error
        else -> null to error
    }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.error.copy(alpha = 0.12f),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            if (title != null) {
                Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.error)
            }
            Text(
                body,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun LoadingState() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(20.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(modifier = Modifier.height(20.dp), strokeWidth = 2.dp)
        Text(
            stringResource(R.string.loading_clips),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 10.dp),
        )
    }
}

@Composable
private fun ClipList(
    state: AppUiState,
    onOpenClip: (String) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (state.clips.isNotEmpty()) {
            item {
                Text(
                    feedSectionTitle(state),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp, bottom = 2.dp),
                )
            }
        }
        if (state.clips.isEmpty() && !state.loading) {
            item { EmptyFeedMessage(state) }
        }
        items(state.clips, key = { it.id }) { clip ->
            ClipCard(
                clip = clip,
                onClick = { onOpenClip(clip.id) },
                showThumbnail = ClipKinds.isImageReference(clip),
                thumbnailBytes = state.thumbnailBytes[clip.id],
            )
        }
    }
}

@Composable
private fun ScreenshotGrid(
    state: AppUiState,
    onOpenClip: (String) -> Unit,
) {
    if (state.clips.isEmpty() && !state.loading) {
        Box(modifier = Modifier.fillMaxSize()) {
            EmptyFeedMessage(state)
        }
        return
    }
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(2) }) {
            Text(
                "Screenshots",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = 2.dp),
            )
        }
        items(state.clips, key = { it.id }) { clip ->
            ScreenshotGridCard(
                clip = clip,
                onClick = { onOpenClip(clip.id) },
                thumbnailBytes = state.thumbnailBytes[clip.id],
            )
        }
    }
}

private fun feedSectionTitle(state: AppUiState): String = when {
    state.searchQuery.isNotBlank() -> "Search Results"
    state.activeFeed == ClipFeed.FAVORITES -> "Favorites"
    state.activeFeed == ClipFeed.RECENT -> "Recent Clips"
    else -> "Recent Clips"
}

@Composable
private fun EmptyFeedMessage(state: AppUiState) {
    val connection = resolveConnectionState(state.status, state.error, state.loading)
    val (title, body) = when {
        state.searchQuery.isNotBlank() -> "No matching clips" to stringResource(R.string.search_empty)
        state.activeFeed == ClipFeed.SCREENSHOTS -> "No screenshots yet" to stringResource(R.string.screenshots_empty)
        connection != ConnectionState.CONNECTED -> "Not connected" to stringResource(R.string.no_pc_found_body)
        else -> "No saved clips yet" to stringResource(R.string.clips_empty)
    }
    Column(modifier = Modifier.padding(vertical = 20.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall)
        Text(
            body,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp),
        )
    }
}

@Composable
private fun connectionColor(connection: ConnectionState) = when (connection) {
    ConnectionState.CONNECTED -> ProofTeal
    ConnectionState.REPAIR_NEEDED -> StampGold
    ConnectionState.REVOKED,
    ConnectionState.OFFLINE,
    ConnectionState.MOBILE_ACCESS_OFF,
    -> MaterialTheme.colorScheme.error
    ConnectionState.CHECKING -> MaterialTheme.colorScheme.onSurfaceVariant
}
