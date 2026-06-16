package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.connect.DiscoveredPc
import com.prooffoundry.cachevaultmobile.connect.formatDiscoveredPc

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiscoverPcScreen(
    loading: Boolean,
    discovered: DiscoveredPc?,
    failed: Boolean,
    onConnect: (DiscoveredPc) -> Unit,
    onRetry: () -> Unit,
    onManualSetup: () -> Unit,
    onBack: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.find_pc_wifi)) },
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
            verticalArrangement = Arrangement.spacedBy(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            when {
                loading -> {
                    CircularProgressIndicator()
                    Text(stringResource(R.string.discover_looking))
                }
                discovered != null -> {
                    Text(
                        formatDiscoveredPc(discovered.displayName, discovered.host, discovered.port),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Button(
                        onClick = { onConnect(discovered) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.connect_to_my_pc))
                    }
                }
                failed -> {
                    Text(
                        stringResource(R.string.discover_failed),
                        color = MaterialTheme.colorScheme.error,
                    )
                    Button(onClick = onRetry, modifier = Modifier.fillMaxWidth()) {
                        Text("Try again")
                    }
                    OutlinedButton(onClick = onManualSetup, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.manual_setup))
                    }
                }
            }
        }
    }
}
