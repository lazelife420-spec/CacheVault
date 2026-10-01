package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.AppIdentity
import com.prooffoundry.cachevaultmobile.data.BridgeStatus
import com.prooffoundry.cachevaultmobile.ui.ConnectionState
import com.prooffoundry.cachevaultmobile.ui.UpdateLauncher
import com.prooffoundry.cachevaultmobile.ui.resolveConnectionState
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    pcName: String,
    host: String,
    port: Int,
    deviceId: String,
    lastSeenAt: String?,
    autoConnectApproved: Boolean,
    keepConnectedInBackground: Boolean,
    status: BridgeStatus?,
    error: String?,
    lastError: String?,
    hasLoadedVault: Boolean = true,
    loading: Boolean = false,
    onDisconnect: () -> Unit,
    onRePair: () -> Unit,
    onReconnect: () -> Unit,
    onAutoConnectApproved: (Boolean) -> Unit,
    onKeepConnectedChanged: (Boolean) -> Unit,
    onConnectionDoctor: () -> Unit,
    onVaultLockSettings: () -> Unit = {},
    captureClipboardEnabled: Boolean = false,
    captureScreenshotsEnabled: Boolean = false,
    captureSensitiveBlockEnabled: Boolean = true,
    screenshotsPermitted: Boolean = true,
    onCaptureClipboardChanged: (Boolean) -> Unit = {},
    onCaptureScreenshotsChanged: (Boolean) -> Unit = {},
    onCaptureSensitiveBlockChanged: (Boolean) -> Unit = {},
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

            SectionTitle("Vault Lock")
            Text(
                "Set a PIN or passphrase, optionally add Android biometric unlock, and choose when the app locks.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(onClick = onVaultLockSettings, modifier = Modifier.fillMaxWidth()) {
                Text("Vault Lock settings")
            }

            SectionTitle("Capture on this phone")
            CaptureSection(
                clipboardEnabled = captureClipboardEnabled,
                screenshotsEnabled = captureScreenshotsEnabled,
                sensitiveBlockEnabled = captureSensitiveBlockEnabled,
                screenshotsPermitted = screenshotsPermitted,
                onClipboardChanged = onCaptureClipboardChanged,
                onSensitiveBlockChanged = onCaptureSensitiveBlockChanged,
                onScreenshotsChanged = onCaptureScreenshotsChanged,
            )

            SectionTitle("Connection")
            StatusLine(connection)
            Text("${stringResource(R.string.connected_to_label)} ${pcName.ifBlank { "PC" }}")
            Text("PC: ${host.ifBlank { "—" }}:$port")
            Text("Device: This phone", style = MaterialTheme.typography.bodySmall)
            Text(
                "${stringResource(R.string.last_seen_label)} ${com.prooffoundry.cachevaultmobile.ui.ClipListFormatter.formatRelativeWhen(lastSeenAt)}",
                style = MaterialTheme.typography.bodySmall,
            )
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
            if (connection == ConnectionState.UPDATE_REQUIRED) {
                // The message itself (including the real minimum version) is
                // already shown by the generic `error` text above — it comes
                // straight from the live BridgeError, unlike `status` here,
                // which is only ever set on a successful connection and so
                // is stale/null on exactly the failure path this state
                // represents. Only the action lives in this block.
                OutlinedButton(
                    onClick = {
                        val opened = UpdateLauncher.launchUpdate { url ->
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        }
                        if (!opened) {
                            Toast.makeText(
                                context,
                                "Could not open the update page. Check your connection and try again.",
                                Toast.LENGTH_LONG,
                            ).show()
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Check for update")
                }
            }
            if (connection == ConnectionState.REPAIR_NEEDED ||
                connection == ConnectionState.REVOKED ||
                connection == ConnectionState.OFFLINE
            ) {
                Button(onClick = onReconnect, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.reconnect))
                }
                Button(onClick = onRePair, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.enter_new_pairing_code))
                }
            }
            Button(onClick = onDisconnect, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.forget_this_pc))
            }

            SectionTitle("Reconnect")
            Row(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Always reconnect on this Wi-Fi", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        if (autoConnectApproved) {
                            "Reconnect when this trusted PC is found while the app can run."
                        } else {
                            "Connect this time unless you allow always reconnect on this Wi-Fi."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = autoConnectApproved, onCheckedChange = onAutoConnectApproved)
            }
            Row(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        stringResource(R.string.keep_connected_in_background),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        stringResource(R.string.keep_connected_summary),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = keepConnectedInBackground,
                    onCheckedChange = onKeepConnectedChanged,
                )
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

            SectionTitle("About")
            Text(
                "App version: ${AppIdentity.APP_VERSION} (build ${AppIdentity.APP_BUILD})",
                style = MaterialTheme.typography.labelSmall,
            )
            Text("Protocol: ${AppIdentity.PROTOCOL_VERSION}", style = MaterialTheme.typography.labelSmall)
            Text(
                "Compatibility: " + when (status?.compatible) {
                    true -> "Compatible"
                    false -> "Update required"
                    null -> "Unknown — not yet connected"
                },
                style = MaterialTheme.typography.labelSmall,
            )
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
            ConnectionState.VAULT_LOCKED,
            ConnectionState.UPDATE_REQUIRED,
            -> MaterialTheme.colorScheme.error
            else -> MaterialTheme.colorScheme.secondary
        },
    )
}

private fun copyDiagnostics(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Cache Vault diagnostics", text))
    com.prooffoundry.cachevaultmobile.capture.ClipboardEcho.mark(text)
}

/**
 * Standalone capture toggles. Honest about platform limits: screenshots import
 * automatically once photo access is granted; clipboard capture saves on app
 * open or via the capture notification — Android does not let any app read
 * the clipboard silently in the background.
 */
@Composable
private fun CaptureSection(
    clipboardEnabled: Boolean,
    screenshotsEnabled: Boolean,
    sensitiveBlockEnabled: Boolean,
    screenshotsPermitted: Boolean,
    onClipboardChanged: (Boolean) -> Unit,
    onSensitiveBlockChanged: (Boolean) -> Unit,
    onScreenshotsChanged: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val mediaPerms = when {
        android.os.Build.VERSION.SDK_INT >= 34 -> arrayOf(
            android.Manifest.permission.READ_MEDIA_IMAGES,
            android.Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED,
        )
        android.os.Build.VERSION.SDK_INT >= 33 -> arrayOf(
            android.Manifest.permission.READ_MEDIA_IMAGES,
        )
        else -> arrayOf(android.Manifest.permission.READ_EXTERNAL_STORAGE)
    }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { grants ->
        val granted = grants.values.any { it }
        if (granted) {
            onScreenshotsChanged(true)
        } else {
            Toast.makeText(
                context,
                "Photo access was not allowed — screenshots cannot be imported.",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    Row(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.weight(1f)) {
            Text("Save copies to this phone", style = MaterialTheme.typography.bodyLarge)
            Text(
                "Saves the clipboard when you open the app, or when you tap the capture notification. Clipboard stays on this phone.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = clipboardEnabled, onCheckedChange = onClipboardChanged)
    }
    Row(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.weight(1f)) {
            Text("Block sensitive auto-saves", style = MaterialTheme.typography.bodyLarge)
            Text(
                "Copies that look like passwords, keys or tokens are skipped by automatic capture. " +
                    "Turn this off to capture them too.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = sensitiveBlockEnabled, onCheckedChange = onSensitiveBlockChanged)
    }
    Row(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.weight(1f)) {
            Text("Import new screenshots", style = MaterialTheme.typography.bodyLarge)
            Text(
                if (screenshotsPermitted) {
                    "New screenshots are filed into this phone's vault automatically."
                } else {
                    "Needs photo access. Choose \"Allow all\" so new screenshots can be imported."
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(
            checked = screenshotsEnabled,
            onCheckedChange = { enabled ->
                if (enabled && !screenshotsPermitted) permLauncher.launch(mediaPerms)
                else onScreenshotsChanged(enabled)
            },
        )
    }
    if (screenshotsEnabled && !screenshotsPermitted) {
        Text(
            "Photo access is off — screenshots are not being imported.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.error,
        )
    }
}
