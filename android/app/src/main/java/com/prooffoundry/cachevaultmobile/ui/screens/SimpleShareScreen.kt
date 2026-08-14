package com.prooffoundry.cachevaultmobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
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

/**
 * Where a Send-to-PC attempt currently stands.
 *
 * Drives the primary button so one tap cannot become several in-flight sends:
 * repeated taps against an unresponsive button previously created duplicate
 * vault items on the desktop.
 */
enum class SendPhase { IDLE, SENDING, SENT, FAILED }

/**
 * True when a new send must be ignored.
 *
 * Single source of truth shared by the button's enabled state and the tap
 * handler, so the two cannot drift apart. FAILED is deliberately not blocking:
 * a failed send must stay retryable.
 */
fun SendPhase.blocksNewSend(): Boolean =
    this == SendPhase.SENDING || this == SendPhase.SENT

/** Simple Mode — large buttons, plain language, no technical jargon. */
@Composable
fun SimpleShareScreen(
    sharedText: String,
    sharedUrl: String?,
    connectionLabel: String,
    isConnected: Boolean,
    statusMessage: String?,
    onSendToPc: () -> Unit,
    onCopyText: () -> Unit,
    onShareWithSomeone: () -> Unit,
    onDismiss: () -> Unit,
    sensitiveReason: String? = null,
    imageLabel: String? = null,
    phase: SendPhase = SendPhase.IDLE,
) {
    var showSensitiveWarning by remember { mutableStateOf(false) }
    val isImage = imageLabel != null
    val isSending = phase == SendPhase.SENDING

    Column(
        modifier = Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = stringResource(R.string.share_screen_title),
            style = MaterialTheme.typography.headlineMedium.copy(
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
        Text(
            text = if (isConnected) {
                stringResource(R.string.share_connected, connectionLabel)
            } else {
                stringResource(R.string.share_not_connected)
            },
            style = MaterialTheme.typography.bodyLarge,
            color = if (isConnected) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.error
            },
        )
        if (!isConnected) {
            Text(
                text = stringResource(R.string.offline_recovery_steps),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (imageLabel != null) {
            Text(
                text = imageLabel,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
            )
        }
        if (sensitiveReason != null) {
            SensitiveBadge(reason = sensitiveReason)
        }
        statusMessage?.let { StatusBanner(message = it, phase = phase) }
        PrimaryActionButton(
            text = if (isSending) {
                stringResource(R.string.sending_to_vault)
            } else {
                stringResource(R.string.send_to_cache_vault)
            },
            // Disabled once sent so a second tap cannot duplicate the item.
            enabled = isConnected && !phase.blocksNewSend(),
            showProgress = isSending,
            onClick = {
                if (sensitiveReason != null) showSensitiveWarning = true else onSendToPc()
            },
        )
        if (!isImage) {
            SecondaryActionButton(
                text = stringResource(R.string.share_copy_text),
                onClick = onCopyText,
            )
            SecondaryActionButton(
                text = stringResource(R.string.share_with_someone),
                onClick = onShareWithSomeone,
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        TextButton(
            onClick = onDismiss,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                stringResource(R.string.share_done),
                fontSize = 18.sp,
            )
        }
        Text(
            text = stringResource(R.string.share_footer),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }

    if (showSensitiveWarning && sensitiveReason != null) {
        AlertDialog(
            onDismissRequest = { showSensitiveWarning = false },
            title = { Text("This looks sensitive") },
            text = {
                Text(
                    "This looks like $sensitiveReason. Send it to " +
                        "$connectionLabel anyway? It will be stored on your PC " +
                        "(local-only) with masking.",
                )
            },
            confirmButton = {
                TextButton(
                    enabled = !phase.blocksNewSend(),
                    onClick = {
                        showSensitiveWarning = false
                        onSendToPc()
                    },
                ) { Text(stringResource(R.string.send_to_cache_vault)) }
            },
            dismissButton = {
                TextButton(onClick = { showSensitiveWarning = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun SensitiveBadge(reason: String) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(modifier = Modifier.padding(12.dp)) {
            Text(
                text = "⚠ Looks sensitive — $reason. You'll be asked to confirm before sending.",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}

/**
 * Result surface for a send attempt.
 *
 * Rendered as a filled banner rather than a bare line of text: the previous
 * plain-text status sat above the button and was easy to miss, which left users
 * unsure whether a send had succeeded.
 */
@Composable
private fun StatusBanner(message: String, phase: SendPhase) {
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

@Composable
private fun PrimaryActionButton(
    text: String,
    enabled: Boolean = true,
    showProgress: Boolean = false,
    onClick: () -> Unit,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier
            .fillMaxWidth()
            .height(64.dp),
        colors = ButtonDefaults.buttonColors(),
    ) {
        if (showProgress) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                strokeWidth = 2.dp,
                color = LocalContentColor.current,
            )
            Spacer(modifier = Modifier.width(12.dp))
        }
        Text(text = text, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun SecondaryActionButton(
    text: String,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp),
    ) {
        Text(text = text, fontSize = 18.sp, fontWeight = FontWeight.Medium)
    }
}

fun copyCleanText(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Cache Vault", text))
}

fun shareTextExternal(context: Context, text: String) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(intent, "Share with someone"))
}
