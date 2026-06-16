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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EasyConnectScreen(
    onOpenWifiSettings: () -> Unit,
    onSameWifi: () -> Unit,
    onManualSetup: () -> Unit,
    onBack: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.easy_connect)) },
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
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                stringResource(R.string.wifi_hint),
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                stringResource(R.string.wifi_panel_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = onOpenWifiSettings, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.open_wifi_settings))
            }
            Button(onClick = onSameWifi, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.same_wifi_button))
            }
            OutlinedButton(onClick = onManualSetup, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.manual_setup))
            }
        }
    }
}
