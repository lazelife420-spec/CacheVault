package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.ui.AppUiState
import com.prooffoundry.cachevaultmobile.ui.ConnectionState
import com.prooffoundry.cachevaultmobile.ui.resolveConnectionState
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@Composable
fun ProofScreen(
    state: AppUiState,
    onRefresh: () -> Unit,
    onOpenSettings: () -> Unit,
    onCopyDiagnostics: () -> String,
) {
    val context = LocalContext.current
    val connection = resolveConnectionState(state.status, state.error, state.loading)
    val statusOk = connection == ConnectionState.CONNECTED

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Proof", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text(
            stringResource(R.string.proof_subtitle),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(10.dp),
            color = MaterialTheme.colorScheme.surface,
        ) {
            Column(
                modifier = Modifier.padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Proof Receipts", style = MaterialTheme.typography.labelLarge)
                Text(
                    stringResource(R.string.proof_honest_body),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(10.dp),
            color = MaterialTheme.colorScheme.surface,
        ) {
            Column(
                modifier = Modifier.padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text("Connection proof", style = MaterialTheme.typography.labelLarge)
                ProofLine("Last status", if (statusOk) "ok" else connection.label.lowercase())
                ProofLine(
                    "Device",
                    state.deviceId.ifBlank { "—" },
                )
                ProofLine("PC host", state.hostLabel.ifBlank { "—" })
                if (state.lastError != null && !statusOk) {
                    Text(
                        state.lastError,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
        Text(
            stringResource(R.string.proof_actions_hint),
            style = MaterialTheme.typography.labelSmall,
            color = StampGold.copy(alpha = 0.85f),
        )
        Button(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) {
            Text("Refresh proof status")
        }
        OutlinedButton(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth()) {
            Text("Open Settings", color = ProofTeal)
        }
        OutlinedButton(
            onClick = {
                copyText(context, onCopyDiagnostics())
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Copy diagnostics", color = ProofTeal)
        }
    }
}

@Composable
private fun ProofLine(label: String, value: String) {
    androidx.compose.foundation.layout.Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.labelMedium)
    }
}

private fun copyText(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Cache Vault diagnostics", text))
}
