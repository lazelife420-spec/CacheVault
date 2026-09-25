package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import com.prooffoundry.cachevaultmobile.security.UnlockMode
import com.prooffoundry.cachevaultmobile.security.VaultLockManager
import com.prooffoundry.cachevaultmobile.security.VaultLockStore
import com.prooffoundry.cachevaultmobile.security.VerifyResult
import kotlinx.coroutines.launch

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun VaultLockScreen(
    store: VaultLockStore,
    manager: VaultLockManager,
    isGate: Boolean,
    onClose: (() -> Unit)? = null,
    onUnlocked: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    val activity = context as? FragmentActivity
    val scope = rememberCoroutineScope()
    var mode by remember { mutableStateOf(store.mode()) }
    var secret by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var timeoutMenu by remember { mutableStateOf(false) }
    var timeout by remember { mutableStateOf(store.lockTimeoutMs) }

    fun launchBiometric(enrollment: Boolean) {
        if (activity == null) {
            message = "Biometric authentication is unavailable here."
            return
        }
        val cipher = if (enrollment) store.biometricEnrollmentCipher() else store.biometricCipherForUnlock()
        if (cipher == null) {
            message = if (enrollment) "Could not prepare the Keystore biometric key. PIN fallback remains available."
            else "Biometric unlock needs setup again. Use your PIN or passphrase."
            if (!enrollment) store.disableBiometric()
            return
        }
        val prompt = BiometricPrompt(activity, activity.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                val usedCipher = result.cryptoObject?.cipher ?: return
                if (enrollment) {
                    if (store.finishBiometricEnrollment(usedCipher)) {
                        manager.configurationChanged()
                        message = "Biometric unlock is ready. Your PIN or passphrase remains the fallback."
                    } else {
                        message = "Biometric setup did not complete. PIN fallback remains available."
                    }
                } else {
                    if (store.completeBiometricUnlock(usedCipher)) {
                        manager.unlock()
                        onUnlocked?.invoke()
                    } else {
                        message = "Could not verify biometric unlock. Use your PIN or passphrase."
                    }
                }
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                if (enrollment) message = "Biometric setup cancelled. PIN fallback remains available."
                else if (errorCode != BiometricPrompt.ERROR_NEGATIVE_BUTTON) message = "Still locked. Use your PIN or passphrase."
            }
        })
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(if (enrollment) "Enable Vault biometric unlock" else "Unlock Cache Vault")
            .setSubtitle("Your PIN or passphrase is always the fallback")
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText("Use PIN")
            .build()
        prompt.authenticate(info, BiometricPrompt.CryptoObject(cipher))
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (isGate) "Vault Door" else "Vault Lock") },
                navigationIcon = {
                    if (!isGate && onClose != null) TextButton(onClick = onClose) { Text("Done") }
                },
                actions = {
                    if (!isGate && store.isEnabled) TextButton(onClick = { manager.lock(); onClose?.invoke() }) { Text("Lock now") }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(horizontal = 24.dp, vertical = 18.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("◈", style = MaterialTheme.typography.displayMedium, color = MaterialTheme.colorScheme.primary)
            Text(if (isGate) "Your vault is sealed" else "A private app-level access gate", style = MaterialTheme.typography.titleLarge)
            Text(
                if (isGate) "Unlock to open saved items, paired PC content, or an incoming share."
                else "The lock protects app access and recent-app previews. It does not encrypt existing local database or image files at rest.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (isGate) {
                if (store.biometricEnabled) {
                    OutlinedButton(onClick = { launchBiometric(false) }, modifier = Modifier.fillMaxWidth()) { Text("Unlock with biometrics") }
                }
                OutlinedTextField(
                    value = secret,
                    onValueChange = { secret = it; message = null },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(if (store.mode() == UnlockMode.PIN) "PIN" else "Passphrase") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = if (store.mode() == UnlockMode.PIN) KeyboardType.NumberPassword else KeyboardType.Password),
                )
                Button(
                    enabled = !busy && secret.isNotEmpty(),
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        busy = true
                        scope.launch {
                            when (val result = store.verify(secret)) {
                                VerifyResult.Accepted -> {
                                    manager.unlock()
                                    secret = ""
                                    message = null
                                    onUnlocked?.invoke()
                                }
                                VerifyResult.Invalid -> {
                                    secret = ""
                                    message = "That PIN or passphrase did not unlock the vault."
                                }
                                is VerifyResult.Throttled -> {
                                    secret = ""
                                    message = "Too many attempts. Try again in ${((result.remainingMs + 999) / 1000)} seconds."
                                }
                            }
                            busy = false
                        }
                    },
                ) { Text(if (busy) "Checking…" else "Unlock") }
            } else if (!store.isEnabled) {
                var expanded by remember { mutableStateOf(false) }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { expanded = true }) { Text(if (mode == UnlockMode.PIN) "Use PIN" else "Use passphrase") }
                    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        DropdownMenuItem(text = { Text("PIN (6–12 digits)") }, onClick = { mode = UnlockMode.PIN; secret = ""; confirmation = ""; expanded = false })
                        DropdownMenuItem(text = { Text("Passphrase (10+ characters)") }, onClick = { mode = UnlockMode.PASSPHRASE; secret = ""; confirmation = ""; expanded = false })
                    }
                }
                OutlinedTextField(value = secret, onValueChange = { secret = it }, modifier = Modifier.fillMaxWidth(), label = { Text(if (mode == UnlockMode.PIN) "Create PIN" else "Create passphrase") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = if (mode == UnlockMode.PIN) KeyboardType.NumberPassword else KeyboardType.Password))
                OutlinedTextField(value = confirmation, onValueChange = { confirmation = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Confirm") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = if (mode == UnlockMode.PIN) KeyboardType.NumberPassword else KeyboardType.Password))
                Button(
                    enabled = !busy && secret == confirmation && validSecret(secret, mode),
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        busy = true
                        scope.launch {
                            runCatching { store.configure(secret, mode) }
                                .onSuccess {
                                    manager.configurationChanged()
                                    (activity?.window)?.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
                                    manager.unlock()
                                    message = "Vault Lock is on. It locks when the app leaves the foreground or after the selected idle timeout."
                                    secret = ""
                                    confirmation = ""
                                }
                                .onFailure { message = "Could not set up Vault Lock. No vault items were changed." }
                            busy = false
                        }
                    },
                ) { Text(if (busy) "Setting up…" else "Enable Vault Lock") }
                Text("PIN/passphrase checks use PBKDF2-HMAC-SHA256 with a random salt. No password is stored reversibly.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Text("Unlock method: ${if (store.mode() == UnlockMode.PIN) "PIN" else "passphrase"} with ${if (store.biometricEnabled) "biometric option" else "no biometric option"}.")
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { timeoutMenu = true }) { Text("Idle timeout: ${timeoutLabel(timeout)}") }
                    DropdownMenu(expanded = timeoutMenu, onDismissRequest = { timeoutMenu = false }) {
                        VaultLockStore.ALLOWED_TIMEOUTS.forEach { value ->
                            DropdownMenuItem(text = { Text(timeoutLabel(value)) }, onClick = { timeout = value; store.setTimeout(value); timeoutMenu = false })
                        }
                    }
                }
                if (!store.biometricEnabled) {
                    OutlinedButton(
                        enabled = BiometricManager.from(context).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) == BiometricManager.BIOMETRIC_SUCCESS,
                        onClick = { launchBiometric(true) }, modifier = Modifier.fillMaxWidth(),
                    ) { Text("Set up Android biometric") }
                } else {
                    OutlinedButton(onClick = { store.clearBiometricKey(); manager.configurationChanged(); message = "Biometric unlock disabled. PIN/passphrase still works." }, modifier = Modifier.fillMaxWidth()) { Text("Disable biometric unlock") }
                }
                Button(onClick = { manager.lock(); onClose?.invoke() }, modifier = Modifier.fillMaxWidth()) { Text("Lock now") }
                OutlinedTextField(
                    value = confirmation,
                    onValueChange = { confirmation = it; message = null },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Current PIN or passphrase to turn off lock") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                )
                OutlinedButton(
                    enabled = !busy && confirmation.isNotEmpty(),
                    onClick = {
                        busy = true
                        scope.launch {
                            when (val result = store.disable(confirmation)) {
                                VerifyResult.Accepted -> {
                                    manager.configurationChanged()
                                    manager.unlock()
                                    activity?.window?.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
                                    message = "Vault Lock turned off. Your saved items were not changed."
                                    confirmation = ""
                                }
                                VerifyResult.Invalid -> { confirmation = ""; message = "That PIN or passphrase did not match." }
                                is VerifyResult.Throttled -> { confirmation = ""; message = "Too many attempts. Try again in ${((result.remainingMs + 999) / 1000)} seconds." }
                            }
                            busy = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Turn off Vault Lock") }
            }
            message?.let { Text(it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall) }
            if (isGate) Text("Paired PC browsing stays unavailable until this app is unlocked.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun validSecret(value: String, mode: UnlockMode): Boolean = when (mode) {
    UnlockMode.PIN -> value.length in 6..12 && value.all(Char::isDigit)
    UnlockMode.PASSPHRASE -> value.length in 10..128
}

private fun timeoutLabel(value: Long): String = when (value) {
    15_000L -> "15 seconds"
    60_000L -> "1 minute"
    300_000L -> "5 minutes"
    else -> "15 minutes"
}
