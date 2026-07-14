package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.ui.ConnectionDoctorInfo
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConnectionDoctorScreen(
    info: ConnectionDoctorInfo,
    onBack: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Connection Doctor") },
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
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            DoctorRow("PC host", info.host.ifBlank { "—" })
            DoctorRow("Port", info.port.toString())
            DoctorRow("Device", info.deviceId.ifBlank { "—" })
            DoctorRow("Status", info.connectionState.label)
            DoctorRow(
                "Last check",
                if (info.statusOk) "PC reachable · token accepted" else "Failed or not verified",
            )
            info.lastError?.let { DoctorRow("Last error", it) }
            DoctorRow("App version", "${info.appVersion} (build ${info.appBuild})")
            DoctorRow("Protocol", info.protocolVersion.toString())
            info.pcVersion?.let { DoctorRow("PC version", it) }
            info.minimumMobileVersion?.let { DoctorRow("Minimum supported version", it) }
            Text("Suggested fix", style = MaterialTheme.typography.labelLarge, color = StampGold)
            Text(info.suggestedFix, style = MaterialTheme.typography.bodyMedium)
            Text(
                "Local Wi-Fi access only. No cloud sync. Your PC stays the source of truth.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun DoctorRow(label: String, value: String) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = ProofTeal)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
