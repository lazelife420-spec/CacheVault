package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.BrowseFilter
import com.prooffoundry.cachevaultmobile.data.ClipKinds
import com.prooffoundry.cachevaultmobile.ui.AppUiState
import com.prooffoundry.cachevaultmobile.ui.components.ClipCard
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun BrowseScreen(
    state: AppUiState,
    onSearch: (String) -> Unit,
    onFilter: (BrowseFilter) -> Unit,
    onRefresh: () -> Unit,
    onOpenClip: (String) -> Unit,
) {
    val pullState = rememberPullRefreshState(state.loading, onRefresh)
    val focusManager = LocalFocusManager.current
    val listState = rememberLazyListState()

    LaunchedEffect(listState.isScrollInProgress) {
        if (listState.isScrollInProgress) {
            focusManager.clearFocus()
        }
    }

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
                "Browse",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
            )
            OutlinedTextField(
                value = state.browseSearchQuery,
                onValueChange = onSearch,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                placeholder = { Text(stringResource(R.string.search_hint)) },
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyMedium,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() }),
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                ),
                trailingIcon = {
                    if (state.browseSearchQuery.isNotBlank()) {
                        IconButton(onClick = { onSearch("") }) {
                            Icon(
                                androidx.compose.material.icons.Icons.Default.Clear,
                                contentDescription = "Clear",
                            )
                        }
                    }
                },
            )
            androidx.compose.foundation.layout.Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                BrowseFilter.entries.forEach { filter ->
                    FilterChip(
                        selected = state.browseFilter == filter,
                        onClick = {
                            focusManager.clearFocus()
                            onFilter(filter)
                        },
                        label = {
                            Text(filter.label, style = MaterialTheme.typography.labelSmall)
                        },
                    )
                }
            }
            if (state.browseSearchQuery.isNotBlank() && !state.loading) {
                Text(
                    "${state.clips.size} result(s)",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            LazyColumn(
                modifier = Modifier.weight(1f),
                state = listState,
                contentPadding = PaddingValues(bottom = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (state.clips.isEmpty() && !state.loading) {
                    item {
                        Text(
                            if (state.browseSearchQuery.isNotBlank()) {
                                stringResource(R.string.search_empty)
                            } else {
                                stringResource(R.string.clips_empty)
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(vertical = 16.dp),
                        )
                    }
                }
                items(state.clips, key = { it.id }) { clip ->
                    ClipCard(
                        clip = clip,
                        onClick = {
                            focusManager.clearFocus()
                            onOpenClip(clip.id)
                        },
                        showThumbnail = ClipKinds.isImageReference(clip),
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
