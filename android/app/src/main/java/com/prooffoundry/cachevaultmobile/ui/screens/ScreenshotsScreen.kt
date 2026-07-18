package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.ui.AppUiState
import com.prooffoundry.cachevaultmobile.ui.VaultSections
import com.prooffoundry.cachevaultmobile.ui.components.ScreenshotGridCard
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun ScreenshotsScreen(
    state: AppUiState,
    onRefresh: () -> Unit,
    onOpenImage: (ClipSummary, List<ClipSummary>) -> Unit,
) {
    val shots = VaultSections.screenshotClips(state.allClips)
    val pullState = rememberPullRefreshState(state.loading, onRefresh)
    val loading = state.loading && !state.hasLoadedVault

    androidx.compose.foundation.layout.Box(
        modifier = Modifier
            .fillMaxSize()
            .pullRefresh(pullState),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 14.dp),
        ) {
            Text(
                stringResource(R.string.images_tab),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
            )
            if (loading) {
                Text(
                    stringResource(R.string.loading_clips),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            } else {
                Text(
                    stringResource(R.string.images_count, shots.size),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }
            when {
                loading -> {
                    androidx.compose.foundation.layout.Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(color = ProofTeal)
                    }
                }
                shots.isEmpty() -> {
                    Text(
                        stringResource(R.string.images_empty),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 24.dp),
                    )
                }
                else -> {
                    val groups = VaultSections.groupScreenshotsByDate(shots)
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(bottom = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        groups.forEach { group ->
                            item(span = { GridItemSpan(maxLineSpan) }, key = "header:${group.label}") {
                                Text(
                                    group.label,
                                    style = MaterialTheme.typography.labelLarge,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(top = 4.dp, bottom = 2.dp),
                                )
                            }
                            items(group.clips, key = { it.id }) { clip ->
                                ScreenshotGridCard(
                                    clip = clip,
                                    onClick = { onOpenImage(clip, shots) },
                                    thumbnailBytes = state.thumbnailBytes[clip.id],
                                )
                            }
                        }
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
