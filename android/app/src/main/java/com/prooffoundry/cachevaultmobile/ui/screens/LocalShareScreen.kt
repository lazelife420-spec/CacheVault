package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.local.LocalSafe
import com.prooffoundry.cachevaultmobile.ui.theme.ProofTeal
import com.prooffoundry.cachevaultmobile.ui.theme.StampGold

/**
 * Share-sheet intake for CV-MOBILE-1. The local vault is the default
 * destination: "Save on this phone" is the primary action and works with no
 * pairing and no network. "Send to <PC>" remains available as a separate,
 * deliberate action when a pairing exists.
 */
@Composable
fun LocalShareScreen(
    previewTitle: String,
    previewBody: String,
    kindLabel: String,
    safes: List<LocalSafe>,
    selectedSafeId: String,
    onSelectSafe: (String) -> Unit,
    onSaveLocally: () -> Unit,
    localSaveEnabled: Boolean,
    localSaveBusy: Boolean,
    savedOnPhone: Boolean,
    connectionLabel: String?,
    onSendToPc: () -> Unit,
    sendPhase: SendPhase,
    onCopyText: (() -> Unit)?,
    onShareWithSomeone: (() -> Unit)?,
    onDismiss: () -> Unit,
    statusMessage: String?,
    sensitiveReason: String? = null,
) {
    var showSensitiveWarning by remember { mutableStateOf(false) }
    var pendingSensitive by remember { mutableStateOf<(() -> Unit)?>(null) }
    var safeMenuOpen by remember { mutableStateOf(false) }
    val safeName = safes.firstOrNull { it.id == selectedSafeId }?.name ?: "Default Safe"

    Column(
        modifier = Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = stringResource(R.string.local_share_title),
            style = MaterialTheme.typography.headlineMedium.copy(
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
        Text(
            text = stringResource(R.string.local_share_subtitle),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Surface(
            shape = MaterialTheme.shapes.medium,
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    kindLabel,
                    style = MaterialTheme.typography.labelSmall,
                    color = ProofTeal,
                )
                Text(
                    previewTitle,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 1,
                )
                if (previewBody.isNotBlank()) {
                    Text(
                        previewBody,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 4,
                    )
                }
            }
        }

        if (sensitiveReason != null) {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        modifier = Modifier.padding(top = 2.dp).size(18.dp),
                    )
                    Text(
                        text = "Looks sensitive — $sensitiveReason. You'll be asked to confirm before saving or sending.",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
        }

        // Destination: an explicit, named phone-local Safe.
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("Save into", style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = { safeMenuOpen = true }) {
                Text(safeName, color = ProofTeal)
            }
            DropdownMenu(expanded = safeMenuOpen, onDismissRequest = { safeMenuOpen = false }) {
                safes.forEach { safe ->
                    DropdownMenuItem(
                        text = { Text(safe.name) },
                        onClick = {
                            safeMenuOpen = false
                            onSelectSafe(safe.id)
                        },
                    )
                }
            }
        }

        statusMessage?.let { ShareStatusBanner(message = it, phase = sendPhase) }

        Button(
            onClick = {
                if (sensitiveReason != null && !savedOnPhone) {
                    pendingSensitive = { onSaveLocally() }
                    showSensitiveWarning = true
                } else {
                    onSaveLocally()
                }
            },
            enabled = localSaveEnabled && !localSaveBusy && !savedOnPhone,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            shape = RoundedCornerShape(28.dp),
        ) {
            if (localSaveBusy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = LocalContentColor.current,
                )
                Spacer(modifier = Modifier.width(10.dp))
            }
            Text(
                if (savedOnPhone) {
                    stringResource(R.string.local_share_saved)
                } else {
                    stringResource(R.string.local_save_on_phone)
                },
                fontSize = 17.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }

        OutlinedButton(
            onClick = {
                if (sensitiveReason != null) {
                    pendingSensitive = { onSendToPc() }
                    showSensitiveWarning = true
                } else {
                    onSendToPc()
                }
            },
            enabled = connectionLabel != null && !sendPhase.blocksNewSend(),
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
        ) {
            Text(
                if (connectionLabel != null) {
                    stringResource(R.string.local_send_to_pc, connectionLabel)
                } else {
                    stringResource(R.string.local_send_to_pc_unavailable)
                },
                fontSize = 16.sp,
                color = ProofTeal,
            )
        }

        if (onCopyText != null) {
            TextButton(onClick = onCopyText, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.share_copy_text))
            }
        }
        if (onShareWithSomeone != null) {
            TextButton(onClick = onShareWithSomeone, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.share_with_someone))
            }
        }

        TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.share_done), fontSize = 18.sp)
        }
        Text(
            text = stringResource(R.string.local_share_footer),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }

    if (showSensitiveWarning && sensitiveReason != null) {
        AlertDialog(
            onDismissRequest = {
                showSensitiveWarning = false
                pendingSensitive = null
            },
            title = { Text("This looks sensitive") },
            text = {
                Text(
                    "This looks like $sensitiveReason. Save it anyway? " +
                        "It will be stored on this phone (local-only) with masking.",
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showSensitiveWarning = false
                        pendingSensitive?.invoke()
                        pendingSensitive = null
                    },
                ) { Text("Confirm") }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showSensitiveWarning = false
                        pendingSensitive = null
                    },
                ) { Text("Cancel") }
            },
        )
    }
}

@Composable
fun ShareStatusBanner(message: String, phase: SendPhase) {
    val container = when (phase) {
        SendPhase.SENT -> MaterialTheme.colorScheme.primaryContainer
        SendPhase.FAILED -> MaterialTheme.colorScheme.errorContainer
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val content = when (phase) {
        SendPhase.SENT -> MaterialTheme.colorScheme.onPrimaryContainer
        SendPhase.FAILED -> MaterialTheme.colorScheme.onErrorContainer
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Surface(
        color = container,
        contentColor = content,
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(14.dp),
        )
    }
}
