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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.local.LocalActivityEvent
import com.prooffoundry.cachevaultmobile.ui.ClipListFormatter
import com.prooffoundry.cachevaultmobile.ui.LocalVaultViewModel.LocalUiState
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

/**
 * Local activity ledger (CV-MOBILE-1). Each row describes an action this app
 * observed — never a delivery guarantee and never a signed receipt. Item
 * bodies and tokens are never written to this ledger.
 */
@Composable
fun LocalActivityScreen(state: LocalUiState) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Text(
                "Activity on this phone",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                stringResource(R.string.local_activity_subtitle),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (state.activity.isEmpty()) {
            item {
                Text(
                    stringResource(R.string.local_activity_empty),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            }
        } else {
            items(state.activity, key = { it.id }) { event ->
                ActivityRow(event)
            }
        }
    }
}

@Composable
private fun ActivityRow(event: LocalActivityEvent) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    describeAction(event.action),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    describeOutcome(event.outcome, event.reason),
                    style = MaterialTheme.typography.labelSmall,
                    color = outcomeColor(event.outcome),
                )
            }
            Text(
                ClipListFormatter.formatRelativeWhen(event.at),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun describeAction(action: String): String = when (action) {
    "save" -> "Saved on this phone"
    "favorite" -> "Marked favorite"
    "unfavorite" -> "Removed from favorites"
    "move" -> "Moved to a Safe"
    "remove" -> "Moved to Recently Removed"
    "restore" -> "Restored on this phone"
    "copy" -> "Copied to clipboard"
    "share" -> "Share sheet opened"
    "open" -> "Opened item"
    "reveal" -> "Sensitive content revealed"
    "safe_create" -> "Safe created"
    "safe_rename" -> "Safe renamed"
    else -> action
}

private fun describeOutcome(outcome: String, reason: String?): String = when (outcome) {
    "completed" -> "Done"
    "initiated" -> "Started — receiving app not confirmed"
    "cancelled" -> "Cancelled"
    "failed" -> "Failed${reason?.let { " — $it" } ?: ""}"
    else -> outcome
}

@Composable
private fun outcomeColor(outcome: String): androidx.compose.ui.graphics.Color = when (outcome) {
    "completed" -> ProofTeal
    "initiated" -> StampGold
    "cancelled" -> MaterialTheme.colorScheme.onSurfaceVariant
    "failed" -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}
