package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.DeleteOutline
import android.graphics.Bitmap
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.local.LocalFilter
import com.prooffoundry.cachevaultmobile.ui.LocalVaultViewModel.LocalUiState
import com.prooffoundry.cachevaultmobile.ui.components.LocalItemCard
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

/**
 * Local-first home (CV-MOBILE-1): what Cache Vault is doing on this phone
 * and the obvious next thing — save something. Never gated on pairing and
 * never waiting on network discovery.
 */
@Composable
fun LocalVaultHomeScreen(
    state: LocalUiState,
    onSearch: (String) -> Unit,
    onFilter: (LocalFilter) -> Unit,
    onOpenItem: (String) -> Unit,
    onCopyItem: (String) -> Unit,
    onAdd: () -> Unit,
    onOpenSafes: () -> Unit,
    loadThumbnail: suspend (String) -> Bitmap?,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        val showingRemoved = state.filter == LocalFilter.REMOVED
        if (state.fatalError != null) {
            item {
                Text("Local vault needs attention", color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
        }

        if (state.fatalError != null) {
            item {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.errorContainer,
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text(
                            "This phone's vault could not be opened.",
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                        Text(
                            state.fatalError,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                        Text(
                            "Nothing was deleted. Items shown elsewhere are unaffected.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.8f),
                        )
                    }
                }
            }
            return@LazyColumn
        }

        if (!showingRemoved) item {
            OutlinedTextField(
                value = state.query,
                onValueChange = onSearch,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                placeholder = { Text(stringResource(R.string.local_search_hint)) },
                singleLine = true,
                textStyle = MaterialTheme.typography.bodyMedium,
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                ),
                trailingIcon = {
                    if (state.query.isNotBlank()) {
                        IconButton(onClick = { onSearch("") }) {
                            Icon(Icons.Default.Clear, contentDescription = "Clear")
                        }
                    }
                },
            )
        }

        if (!showingRemoved) item {
            val populated = state.items.any { !it.isRemoved }
            Button(
                onClick = onAdd,
                enabled = true,
                modifier = Modifier.fillMaxWidth().height(if (populated) 44.dp else 54.dp),
                shape = RoundedCornerShape(if (populated) 22.dp else 27.dp),
            ) {
                Icon(Icons.Default.Add, contentDescription = null)
                Text("Save on this phone", modifier = Modifier.padding(start = 8.dp),
                    style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            }
        }

        if (!showingRemoved) item {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                items(LocalFilter.entries.toList(), key = { it.name }) { filter ->
                    FilterChipItem(
                        label = filter.label,
                        selected = state.filter == filter,
                        onClick = { onFilter(filter) },
                    )
                }
            }
        }

        if (state.items.isEmpty()) {
            item {
                when {
                    state.busy -> {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center,
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.height(20.dp).padding(top = 8.dp),
                                strokeWidth = 2.dp,
                                color = ProofTeal,
                            )
                        }
                    }
                    state.query.isNotBlank() -> {
                        Text(
                            stringResource(R.string.local_search_empty),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(vertical = 8.dp),
                        )
                    }
                    state.filter == LocalFilter.REMOVED -> {
                        Column(modifier = Modifier.padding(vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Items can be restored to this phone.",
                                style = MaterialTheme.typography.bodyMedium)
                            Text(stringResource(R.string.local_removed_empty),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    else -> {
                        Surface(
                            shape = RoundedCornerShape(10.dp),
                            color = MaterialTheme.colorScheme.surface,
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Text(
                                    stringResource(R.string.local_empty_title),
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                Text(
                                    stringResource(R.string.local_empty_body),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Text(
                                    stringResource(R.string.local_empty_pc_hint),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = StampGold.copy(alpha = 0.85f),
                                )
                            }
                        }
                    }
                }
            }
        } else {
            if (state.filter == LocalFilter.REMOVED) {
                item {
                    Text("Items can be restored to this phone.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 2.dp))
                }
            }
            item {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        when {
                            state.query.isNotBlank() -> "Results on this phone"
                            state.filter == LocalFilter.REMOVED -> "Recently Removed"
                            state.filter == LocalFilter.FAVORITES -> "Favorites"
                            else -> "Recent"
                        },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
            if (!showingRemoved) {
                        TextButton(onClick = { onFilter(LocalFilter.REMOVED) }) {
                            Icon(Icons.Default.DeleteOutline, contentDescription = null,
                                modifier = Modifier.padding(end = 4.dp))
                            Text("Recently Removed")
                        }
                    }
                }
            }
            items(state.items, key = { it.id }) { item ->
                LocalItemCard(
                    item = item,
                    onClick = { onOpenItem(item.id) },
                    onCopy = { onCopyItem(item.id) },
                    loadThumbnail = loadThumbnail,
                )
            }
        }

        if (!showingRemoved) item {
            Surface(
                onClick = onOpenSafes,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = MaterialTheme.colorScheme.surface,
            ) {
                Row(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
                    Icon(Icons.Default.FolderOpen, contentDescription = null, tint = ProofTeal)
                    Column(modifier = Modifier.padding(start = 12.dp)) {
                        Text("Organize in Safes", style = MaterialTheme.typography.titleSmall)
                        Text("Named groups for items saved on this phone",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun FilterChipItem(label: String, selected: Boolean, onClick: () -> Unit) {
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
