package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.prooffoundry.cachevaultmobile.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ManualSetupScreen(
    defaultPort: Int,
    initialHost: String = "",
    initialPort: Int? = null,
    initialDeviceId: String = "",
    initialToken: String = "",
    loading: Boolean,
    error: String?,
    successMessage: String? = null,
    onPair: (host: String, port: Int, deviceId: String, token: String) -> Unit,
    onBack: () -> Unit,
) {
    var host by rememberSaveable { mutableStateOf(initialHost) }
    var port by rememberSaveable { mutableStateOf((initialPort ?: defaultPort).toString()) }
    var deviceId by rememberSaveable { mutableStateOf(initialDeviceId) }
    var token by rememberSaveable { mutableStateOf(initialToken) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        stringResource(R.string.manual_setup),
                        fontSize = 22.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                },
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
                .verticalScroll(rememberScrollState())
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                stringResource(R.string.manual_setup_intro),
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                stringResource(R.string.pairing_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            ManualField(
                value = host,
                onValueChange = { host = it },
                label = stringResource(R.string.manual_setup_host_label),
                tag = "manual_setup_host",
                keyboardType = KeyboardType.Uri,
                imeAction = ImeAction.Next,
            )
            ManualField(
                value = port,
                onValueChange = { port = it },
                label = stringResource(R.string.manual_setup_port_label),
                tag = "manual_setup_port",
                keyboardType = KeyboardType.Number,
                imeAction = ImeAction.Next,
            )
            ManualField(
                value = deviceId,
                onValueChange = { deviceId = it },
                label = stringResource(R.string.manual_setup_device_id_label),
                tag = "manual_setup_device_id",
                keyboardType = KeyboardType.Ascii,
                imeAction = ImeAction.Next,
            )
            ManualField(
                value = token,
                onValueChange = { token = it },
                label = stringResource(R.string.manual_setup_token_label),
                tag = "manual_setup_token",
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done,
            )
            when {
                !successMessage.isNullOrBlank() -> {
                    Text(
                        successMessage,
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.testTag("manual_setup_success"),
                    )
                }
                !error.isNullOrBlank() -> {
                    Text(
                        error,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyLarge,
                        modifier = Modifier.testTag("manual_setup_error"),
                    )
                    Text(
                        stringResource(R.string.try_again),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Button(
                onClick = {
                    val p = port.toIntOrNull() ?: defaultPort
                    onPair(host.trim(), p, deviceId.trim(), token.trim())
                },
                enabled = !loading && host.isNotBlank() && deviceId.isNotBlank() && token.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .testTag("manual_setup_connect")
                    .semantics { contentDescription = "manual_setup_connect" },
                colors = ButtonDefaults.buttonColors(),
            ) {
                Text(
                    if (loading) {
                        stringResource(R.string.connecting)
                    } else {
                        stringResource(R.string.connect_to_my_pc)
                    },
                    fontSize = 18.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Spacer(Modifier.height(8.dp))
            Text(
                stringResource(R.string.no_cloud),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ManualField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    tag: String,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Next,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label, style = MaterialTheme.typography.bodyLarge) },
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .testTag(tag)
            .semantics { contentDescription = tag },
        singleLine = true,
        textStyle = MaterialTheme.typography.bodyLarge,
        keyboardOptions = KeyboardOptions(
            capitalization = KeyboardCapitalization.None,
            autoCorrect = false,
            keyboardType = keyboardType,
            imeAction = imeAction,
        ),
    )
}
