package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import com.prooffoundry.cachevaultmobile.data.UserMessages
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    host: String,
    status: BridgeStatus?,
    onDisconnect: () -> Unit,
    onBack: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(stringResource(R.string.promise), color = StampGold)
            Text("Status: Paired · Active", style = MaterialTheme.typography.labelLarge)
            Text("Connected PC: $host")
            status?.let {
                Text("Bridge: ${it.product}")
                Text("API version: ${it.mobileApiVersion}")
                Text("Vault version: ${it.cacheVaultVersion}")
                Text("Device id: ${it.deviceId}")
                Text(if (it.readOnly) "Read-only companion" else "Read-only expected")
            }
            Text(
                "Disconnect removes pairing secrets from this phone only. " +
                    "Revoke on the PC to block this device entirely.",
                style = MaterialTheme.typography.bodySmall,
            )
            Button(
                onClick = onDisconnect,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Disconnect / Re-pair")
            }
        }
    }
}
