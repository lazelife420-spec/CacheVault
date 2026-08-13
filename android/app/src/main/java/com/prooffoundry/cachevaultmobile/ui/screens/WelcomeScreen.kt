package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
            .padding(horizontal = 24.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        Text("Cache Vault Mobile", style = MaterialTheme.typography.headlineLarge)
        Text(stringResource(R.string.byline), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            stringResource(R.string.pairing_title),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            stringResource(R.string.pairing_subtitle),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            stringResource(R.string.promise),
            color = StampGold,
            style = MaterialTheme.typography.bodyLarge,
        )
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = onScanQr,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .testTag("welcome_scan_qr")
                .semantics { contentDescription = "welcome_scan_qr" },
            colors = ButtonDefaults.buttonColors(),
        ) {
            Text(
                stringResource(R.string.scan_qr_code),
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        OutlinedButton(
            onClick = onFindPc,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .testTag("welcome_find_pc")
                .semantics { contentDescription = "welcome_find_pc" },
        ) {
            Text(stringResource(R.string.find_pc_wifi))
        }
        androidx.compose.material3.TextButton(
            onClick = onManualSetup,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("welcome_manual_setup")
                .semantics { contentDescription = "welcome_manual_setup" },
        ) {
            Text(
                "Advanced: " + stringResource(R.string.manual_setup),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.weight(1f))
        Text(
            stringResource(R.string.no_cloud),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
