package com.prooffoundry.cachevaultmobile.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.VaultSectionKind
import com.prooffoundry.cachevaultmobile.ui.ConnectionState
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@Composable
fun VaultSectionCard(
    kind: VaultSectionKind,
    count: Int,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier
                .border(
                    width = 1.dp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(10.dp),
                )
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                kind.label,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                if (count < 0) "…" else count.toString(),
                style = MaterialTheme.typography.titleMedium,
                color = StampGold,
                fontWeight = FontWeight.Bold,
            )
            Text(
                kind.helper,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
            )
        }
    }
}

@Composable
fun VaultStatusCard(
    connection: ConnectionState,
    hostLabel: String,
    onRePair: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier
                .border(
                    width = 1.dp,
                    color = when (connection) {
                        ConnectionState.CONNECTED -> ProofTeal.copy(alpha = 0.35f)
                        ConnectionState.OFFLINE,
                        ConnectionState.REVOKED,
                        ConnectionState.MOBILE_ACCESS_OFF,
                        -> MaterialTheme.colorScheme.error.copy(alpha = 0.35f)
                        else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f)
                    },
                    shape = RoundedCornerShape(10.dp),
                )
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                stringResource(R.string.vault_status_title),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(stringResource(R.string.vault_status_local_wifi), ProofTeal)
                when (connection) {
                    ConnectionState.CONNECTED -> {
                        StatusPill("Connected", ProofTeal)
                        StatusPill("Proof recorded", StampGold.copy(alpha = 0.9f))
                    }
                    ConnectionState.CHECKING -> StatusPill("Checking…", MaterialTheme.colorScheme.onSurfaceVariant)
                    ConnectionState.REPAIR_NEEDED -> StatusPill("Re-pair needed", StampGold)
                    ConnectionState.REVOKED -> StatusPill("Device revoked", MaterialTheme.colorScheme.error)
                    ConnectionState.MOBILE_ACCESS_OFF -> StatusPill("Mobile Access off", MaterialTheme.colorScheme.error)
                    ConnectionState.OFFLINE -> StatusPill("Not connected", MaterialTheme.colorScheme.error)
                }
            }
            when {
                connection == ConnectionState.CONNECTED && hostLabel.isNotBlank() -> {
                    Text(
                        stringResource(R.string.vault_status_pc, hostLabel),
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        color = ProofTeal,
                    )
                }
                connection == ConnectionState.CHECKING -> {
                    Text(
                        "Loading saved clips from your PC…",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                connection == ConnectionState.OFFLINE ||
                    connection == ConnectionState.MOBILE_ACCESS_OFF -> {
                    Text(
                        stringResource(R.string.offline_recovery_steps),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (connection == ConnectionState.REPAIR_NEEDED && onRePair != null) {
                TextButton(onClick = onRePair) {
                    Text(stringResource(R.string.enter_new_pairing_code))
                }
            }
        }
    }
}

@Composable
private fun StatusPill(label: String, color: androidx.compose.ui.graphics.Color) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = color.copy(alpha = 0.15f),
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            style = MaterialTheme.typography.labelSmall,
            color = color,
        )
    }
}

@Composable
fun VaultHeader(
    title: String,
    subtitle: String,
    subtitleColor: androidx.compose.ui.graphics.Color,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
    showRefresh: Boolean = true,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.labelMedium,
                color = subtitleColor,
            )
        }
        if (showRefresh) {
            IconButton(onClick = onRefresh) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh")
            }
        }
    }
}
