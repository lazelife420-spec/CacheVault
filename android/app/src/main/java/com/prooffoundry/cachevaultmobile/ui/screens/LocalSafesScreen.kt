package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.local.LocalSafe
import com.prooffoundry.cachevaultmobile.ui.LocalVaultViewModel.LocalUiState
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

/**
 * Phone-local Safes (CV-MOBILE-1): named organizers for items saved on this
 * device. They are not encryption containers and never sync to the desktop.
 */
@Composable
fun LocalSafesScreen(
    state: LocalUiState,
    onSelectSafe: (String?) -> Unit,
    onCreateSafe: (String) -> Unit,
    onRenameSafe: (String, String) -> Unit,
) {
    var showCreate by remember { mutableStateOf(false) }
    var renameTarget by remember { mutableStateOf<LocalSafe?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text(
                "Safes on this phone",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                stringResource(R.string.local_safes_subtitle),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            SafeRow(
                name = "All items",
                count = state.safeCounts.values.sum(),
                selected = state.selectedSafeId == null,
                isDefault = false,
                onClick = { onSelectSafe(null) },
                onRename = null,
            )
        }
        items(state.safes, key = { it.id }) { safe ->
            SafeRow(
                name = safe.name,
                count = state.safeCounts[safe.id] ?: 0,
                selected = state.selectedSafeId == safe.id,
                isDefault = safe.isDefault,
                onClick = { onSelectSafe(safe.id) },
                onRename = if (safe.isDefault) null else ({ renameTarget = safe }),
            )
        }
        item {
            OutlinedButton(onClick = { showCreate = true }, modifier = Modifier.fillMaxWidth()) {
                Text("New Safe", color = ProofTeal)
            }
            Text(
                stringResource(R.string.local_safes_disclaimer),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }

    if (showCreate) {
        SafeNameDialog(
            title = "New Safe",
            confirm = "Create",
            initial = "",
            onDismiss = { showCreate = false },
            onConfirm = {
                onCreateSafe(it)
                showCreate = false
            },
        )
    }
    renameTarget?.let { safe ->
        SafeNameDialog(
            title = "Rename ${safe.name}",
            confirm = "Rename",
            initial = safe.name,
            onDismiss = { renameTarget = null },
            onConfirm = {
                onRenameSafe(safe.id, it)
                renameTarget = null
            },
        )
    }
}

@Composable
private fun SafeRow(
    name: String,
    count: Int,
    selected: Boolean,
    isDefault: Boolean,
    onClick: () -> Unit,
    onRename: (() -> Unit)?,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) {
                ProofTeal.copy(alpha = 0.12f)
            } else {
                MaterialTheme.colorScheme.surface
            },
        ),
        onClick = onClick,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(name, style = MaterialTheme.typography.titleSmall)
                    if (isDefault) {
                        Text(
                            "default",
                            style = MaterialTheme.typography.labelSmall,
                            color = StampGold,
                            modifier = Modifier.padding(start = 8.dp),
                        )
                    }
                }
                Text(
                    "$count item(s) on this phone",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (onRename != null) {
                TextButton(onClick = onRename) { Text("Rename") }
            }
        }
    }
}

@Composable
private fun SafeNameDialog(
    title: String,
    confirm: String,
    initial: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit,
) {
    var name by remember { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                singleLine = true,
                label = { Text("Name") },
            )
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank(),
                onClick = { onConfirm(name) },
            ) { Text(confirm) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
