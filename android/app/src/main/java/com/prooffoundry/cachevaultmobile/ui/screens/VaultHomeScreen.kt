package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.VaultSectionKind
import com.prooffoundry.cachevaultmobile.ui.AppUiState
import com.prooffoundry.cachevaultmobile.ui.ConnectionState
import com.prooffoundry.cachevaultmobile.ui.VaultSections
import com.prooffoundry.cachevaultmobile.ui.components.ClipCard
import com.prooffoundry.cachevaultmobile.ui.components.VaultSectionCard
import com.prooffoundry.cachevaultmobile.ui.components.VaultStatusCard
import com.prooffoundry.cachevaultmobile.ui.connectionSubtitle
import com.prooffoundry.cachevaultmobile.ui.resolveConnectionState
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun VaultHomeScreen(
    state: AppUiState,
    onSearch: (String) -> Unit,
    onRefresh: () -> Unit,
    onOpenClip: (String) -> Unit,
    onBrowseAll: () -> Unit,
    onSection: (VaultSectionKind) -> Unit,
    onRePair: () -> Unit,
) {
    val connection = resolveConnectionState(
        state.status,
        state.error,
        state.loading,
        state.hasLoadedVault,
    )
    val pullState = rememberPullRefreshState(state.loading, onRefresh)
    val recent = VaultSections.recentPreview(state.allClips)
    val counts = state.sectionCounts
    val countsPending = !state.hasLoadedVault && state.loading

    androidx.compose.foundation.layout.Box(
        modifier = Modifier
            .fillMaxSize()
            .pullRefresh(pullState),
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Text("Cache Vault", style = MaterialTheme.typography.titleMedium)
                Text(
                    connectionSubtitle(connection, state.hostLabel),
                    style = MaterialTheme.typography.labelMedium,
                    color = when (connection) {
                        ConnectionState.CONNECTED -> ProofTeal
                        ConnectionState.CHECKING -> MaterialTheme.colorScheme.onSurfaceVariant
                        ConnectionState.REPAIR_NEEDED -> StampGold
                        else -> MaterialTheme.colorScheme.error
                    },
                )
            }
            item {
                OutlinedTextField(
                    value = state.vaultSearchQuery,
                    onValueChange = onSearch,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    placeholder = { Text(stringResource(R.string.vault_search_hint)) },
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodyMedium,
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                        focusedContainerColor = MaterialTheme.colorScheme.surface,
                    ),
                    trailingIcon = {
                        if (state.vaultSearchQuery.isNotBlank()) {
                            IconButton(onClick = { onSearch("") }) {
                                Icon(
                                    androidx.compose.material.icons.Icons.Default.Clear,
                                    contentDescription = "Clear",
                                )
                            }
                        }
                    },
                )
            }
            item {
                VaultStatusCard(
                    connection = connection,
                    hostLabel = state.hostLabel,
                    onRePair = if (connection == ConnectionState.REPAIR_NEEDED) onRePair else null,
                )
            }
            item {
                Text(
                    "Vault Sections",
                    style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            item {
                SectionGrid(counts, countsPending, onSection)
            }
            if (countsPending) {
                item {
                    androidx.compose.foundation.layout.Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.height(20.dp),
                            strokeWidth = 2.dp,
                            color = ProofTeal,
                        )
                    }
                }
            }
            if (state.hasLoadedVault && (counts.sensitive > 0 || counts.recentlyRemoved > 0)) {
                item {
                    Text("Needs Review", style = MaterialTheme.typography.labelLarge)
                }
                item {
                    NeedsReviewRow(counts, onSection)
                }
            }
            if (state.hasLoadedVault) {
                item {
                    RowHeader("Recent Activity", onBrowseAll)
                }
                if (recent.isEmpty() && !state.loading) {
                    item {
                        Text(
                            stringResource(R.string.clips_empty),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(vertical = 8.dp),
                        )
                    }
                }
                items(recent, key = { it.id }) { clip ->
                    ClipCard(
                        clip = clip,
                        onClick = { onOpenClip(clip.id) },
                        showThumbnail = false,
                        thumbnailBytes = state.thumbnailBytes[clip.id],
                    )
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

@Composable
private fun SectionGrid(
    counts: com.prooffoundry.cachevaultmobile.data.VaultSectionCounts,
    countsPending: Boolean,
    onSection: (VaultSectionKind) -> Unit,
) {
    val primary = listOf(
        VaultSectionKind.TEXT,
        VaultSectionKind.LINKS,
        VaultSectionKind.CODE,
        VaultSectionKind.COMMANDS,
        VaultSectionKind.SCREENSHOTS,
        VaultSectionKind.FAVORITES,
        VaultSectionKind.PROOF,
        VaultSectionKind.RECENT,
    )
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        primary.chunked(2).forEach { row ->
            androidx.compose.foundation.layout.Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { kind ->
                    VaultSectionCard(
                        kind = kind,
                        count = when {
                            countsPending -> -1
                            kind == VaultSectionKind.PROOF -> 0
                            else -> counts.countFor(kind)
                        },
                        onClick = { if (!countsPending) onSection(kind) },
                        modifier = Modifier.weight(1f),
                    )
                }
                if (row.size == 1) {
                    androidx.compose.foundation.layout.Spacer(modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun NeedsReviewRow(
    counts: com.prooffoundry.cachevaultmobile.data.VaultSectionCounts,
    onSection: (VaultSectionKind) -> Unit,
) {
    androidx.compose.foundation.layout.Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (counts.sensitive > 0) {
            VaultSectionCard(
                kind = VaultSectionKind.SENSITIVE,
                count = counts.sensitive,
                onClick = { onSection(VaultSectionKind.SENSITIVE) },
                modifier = Modifier.weight(1f),
            )
        }
        if (counts.recentlyRemoved > 0) {
            VaultSectionCard(
                kind = VaultSectionKind.REMOVED,
                count = counts.recentlyRemoved,
                onClick = { onSection(VaultSectionKind.REMOVED) },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun RowHeader(title: String, onAction: () -> Unit) {
    androidx.compose.foundation.layout.Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = MaterialTheme.typography.labelLarge)
        TextButton(onClick = onAction) {
            Text("Browse all", style = MaterialTheme.typography.labelSmall, color = ProofTeal)
        }
    }
}
