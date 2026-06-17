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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import com.prooffoundry.cachevaultmobile.ui.ConnectionState
import com.prooffoundry.cachevaultmobile.ui.resolveConnectionState
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    host: String,
    port: Int,
    deviceId: String,
    status: BridgeStatus?,
    error: String?,
    lastError: String?,
    hasLoadedVault: Boolean = true,
    loading: Boolean = false,
    onDisconnect: () -> Unit,
    onRePair: () -> Unit,
    onConnectionDoctor: () -> Unit,
    onBack: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    val connection = resolveConnectionState(status, error, loading, hasLoadedVault)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(stringResource(R.string.promise), color = StampGold)

            SectionTitle("Connection")
            StatusLine(connection)
            Text("Connected to $host:$port")
            if (deviceId.isNotBlank()) {
                Text("Device: $deviceId", style = MaterialTheme.typography.bodySmall)
            }
            if (connection == ConnectionState.REVOKED) {
                Text(
                    stringResource(R.string.device_revoked_body),
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (!error.isNullOrBlank()) {
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            if (connection == ConnectionState.REPAIR_NEEDED ||
                connection == ConnectionState.REVOKED ||
                connection == ConnectionState.OFFLINE
            ) {
                Button(onClick = onRePair, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.enter_new_pairing_code))
                }
            }
            Button(onClick = onDisconnect, modifier = Modifier.fillMaxWidth()) {
                Text("Disconnect / Re-pair")
            }

            SectionTitle("Security")
            Text(
                "Local Wi-Fi only\nToken stored securely on this phone\nNo cloud sync",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            SectionTitle("Troubleshooting")
            OutlinedButton(onClick = onConnectionDoctor, modifier = Modifier.fillMaxWidth()) {
                Text("Connection Doctor")
            }
            lastError?.let { err ->
                Text("Last error", style = MaterialTheme.typography.labelSmall)
                Text(err, style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(
                onClick = {
                    val text = buildString {
                        appendLine("Cache Vault Mobile diagnostics")
                        appendLine("Host: $host:$port")
                        appendLine("Device: $deviceId")
                        appendLine("State: ${connection.label}")
                        appendLine("Error: ${lastError ?: error ?: "none"}")
                    }
                    copyDiagnostics(context, text)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Copy diagnostics")
            }

            status?.let {
                Text("Bridge: ${it.product}", style = MaterialTheme.typography.labelSmall)
                Text("Vault version: ${it.cacheVaultVersion}", style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleSmall, color = StampGold)
}

@Composable
private fun StatusLine(connection: ConnectionState) {
    Text(
        "Status: ${connection.label}",
        style = MaterialTheme.typography.labelLarge,
        color = when (connection) {
            ConnectionState.CONNECTED -> MaterialTheme.colorScheme.primary
            ConnectionState.REVOKED,
            ConnectionState.OFFLINE,
            ConnectionState.MOBILE_ACCESS_OFF,
            -> MaterialTheme.colorScheme.error
            else -> MaterialTheme.colorScheme.secondary
        },
    )
}

private fun copyDiagnostics(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Cache Vault diagnostics", text))
}
