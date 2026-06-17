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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

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
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "What do you want to do?",
            style = MaterialTheme.typography.headlineMedium.copy(
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
        Text(
            text = if (isConnected) "Connected to $connectionLabel" else "Not connected to PC",
            style = MaterialTheme.typography.bodyLarge,
            color = if (isConnected) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.error
            },
        )
        statusMessage?.let {
            Text(text = it, style = MaterialTheme.typography.titleMedium)
        }
        SimpleActionButton(
            text = "Send to PC",
            enabled = isConnected,
            onClick = onSendToPc,
        )
        SimpleActionButton(text = "Copy Text", onClick = onCopyText)
        SimpleActionButton(text = "Share with Someone", onClick = onShareWithSomeone)
        SimpleActionButton(text = "Done", onClick = onDismiss)
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Local-only · paired Send-to-PC · no cloud",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun SimpleActionButton(
    text: String,
    enabled: Boolean = true,
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
        Text(text = text, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
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
