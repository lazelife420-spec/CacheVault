package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.prooffoundry.cachevaultmobile.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QrScanScreen(
    initialPayload: String = "",
    loading: Boolean = false,
    error: String? = null,
    onPairQr: (String) -> Unit,
    onManualSetup: () -> Unit,
    onBack: () -> Unit,
) {
    var payloadText by remember { mutableStateOf(initialPayload) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.scan_qr_code)) },
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
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                "Scan the pairing QR code displayed on your PC screen.",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                "Open Cache Vault on your PC -> Mobile Access -> Pair Phone. Your phone will connect automatically without cloud accounts.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            OutlinedTextField(
                value = payloadText,
                onValueChange = { payloadText = it },
                label = { Text("Pairing QR Code Payload") },
                placeholder = { Text("Paste or enter QR code string...") },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("qr_payload_input")
                    .semantics { contentDescription = "qr_payload_input" },
                singleLine = false,
                maxLines = 4,
            )

            if (error != null) {
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            Button(
                onClick = { onPairQr(payloadText.trim()) },
                enabled = !loading && payloadText.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .testTag("qr_connect_button")
                    .semantics { contentDescription = "qr_connect_button" },
                colors = ButtonDefaults.buttonColors(),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        color = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier.padding(end = 8.dp),
                    )
                    Text("Connecting...", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                } else {
                    Text("Connect to PC with QR Code", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            Spacer(Modifier.height(12.dp))

            TextButton(
                onClick = onManualSetup,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    "Advanced: " + stringResource(R.string.manual_setup),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
