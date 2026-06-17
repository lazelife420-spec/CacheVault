package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@Composable
fun WelcomeScreen(
    onConnectToPc: () -> Unit,
    onScanQr: () -> Unit,
    onFindPc: () -> Unit,
    onManualSetup: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Spacer(Modifier.height(24.dp))
        Text("Cache Vault Mobile", style = MaterialTheme.typography.headlineLarge)
        Text(stringResource(R.string.byline), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            stringResource(R.string.promise),
            color = StampGold,
            style = MaterialTheme.typography.bodyLarge,
        )
        Spacer(Modifier.height(32.dp))
        Button(onClick = onConnectToPc, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.connect_to_my_pc))
        }
        OutlinedButton(onClick = onScanQr, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.scan_qr_code))
        }
        OutlinedButton(onClick = onFindPc, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.find_pc_wifi))
        }
        OutlinedButton(onClick = onManualSetup, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.manual_setup))
        }
        Spacer(Modifier.weight(1f))
        Text(
            stringResource(R.string.no_cloud),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
