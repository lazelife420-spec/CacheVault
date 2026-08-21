package com.prooffoundry.cachevaultmobile

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import com.prooffoundry.cachevaultmobile.data.BridgeClient
import com.prooffoundry.cachevaultmobile.data.BridgeError
import com.prooffoundry.cachevaultmobile.data.ImageFileHelper
import com.prooffoundry.cachevaultmobile.data.SensitiveText
import com.prooffoundry.cachevaultmobile.data.SharedImage
import com.prooffoundry.cachevaultmobile.ui.screens.SendPhase
import com.prooffoundry.cachevaultmobile.ui.screens.SimpleShareScreen
import com.prooffoundry.cachevaultmobile.ui.screens.blocksNewSend
import com.prooffoundry.cachevaultmobile.ui.screens.copyCleanText
import com.prooffoundry.cachevaultmobile.ui.screens.shareTextExternal
import com.prooffoundry.cachevaultmobile.ui.theme.CacheVaultMobileTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Android Share Sheet entry — opens Simple Mode for shared text/links/images. */
class ShareAssistantActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as CacheVaultMobileApp
        val pairing = app.pairingStore.load()
        val type = intent?.type
        if (Intent.ACTION_SEND == intent?.action && type != null && type.startsWith("image/")) {
            showImageShare(app, pairing)
        } else {
            showTextShare(app, pairing)
        }
    }

    private fun showTextShare(app: CacheVaultMobileApp, pairing: com.prooffoundry.cachevaultmobile.data.PairingConfig?) {
        val shared = extractSharedText(intent)
        val sensitiveReason = SensitiveText.reason(shared.text)
        setContent {
            CacheVaultMobileTheme {
                var status by remember { mutableStateOf<String?>(null) }
                var phase by remember { mutableStateOf(SendPhase.IDLE) }
                val scope = rememberCoroutineScope()
                val connected = pairing != null
                val label = pairing?.pcLabel?.ifBlank { pairing.host } ?: "your PC"
                SimpleShareScreen(
                    sharedText = shared.text,
                    sharedUrl = shared.url,
                    connectionLabel = label,
                    isConnected = connected,
                    statusMessage = status,
                    phase = phase,
                    onSendToPc = {
                        // Ignore taps while a send is running or already done:
                        // repeated taps used to create duplicate vault items.
                        if (!phase.blocksNewSend()) {
                            val initialPairing = app.pairingStore.load()
                            if (initialPairing == null) {
                                status = getString(R.string.send_failed_not_connected)
                                phase = SendPhase.FAILED
                            } else {
                                scope.launch {
                                    phase = SendPhase.SENDING
                                    status = getString(R.string.sending_to_vault)
                                    var p = initialPairing
                                    if (!p.hasUsableHost()) {
                                        val healed = withContext(Dispatchers.IO) { app.bridgeRepository.discoverAndSelfHealEndpoint() }
                                        if (healed != null) p = healed
                                    }
                                    try {
                                        val currentClient = BridgeClient(p)
                                        val resp = withContext(Dispatchers.IO) {
                                            currentClient.sendToPc(
                                                content = shared.text,
                                                itemType = if (shared.url != null) "url" else "text",
                                                sourceApp = "Android Share",
                                                sourceDeviceName = Build.MODEL,
                                                sourceUrl = shared.url,
                                                safeId = "default",
                                            )
                                        }
                                        status = sendResultMessage(resp.success, resp.safeName, resp.error)
                                        phase = if (resp.success) SendPhase.SENT else SendPhase.FAILED
                                    } catch (e: BridgeError.Unauthorized) {
                                        status = getString(R.string.send_failed_pairing)
                                        phase = SendPhase.FAILED
                                    } catch (e: BridgeError.Disabled) {
                                        status = getString(R.string.send_failed_mobile_off)
                                        phase = SendPhase.FAILED
                                    } catch (e: Exception) {
                                        val healed = withContext(Dispatchers.IO) { app.bridgeRepository.discoverAndSelfHealEndpoint() }
                                        if (healed != null) {
                                            val healedClient = BridgeClient(healed)
                                            val retried = runCatching {
                                                withContext(Dispatchers.IO) {
                                                    healedClient.sendToPc(
                                                        content = shared.text,
                                                        itemType = if (shared.url != null) "url" else "text",
                                                        sourceApp = "Android Share",
                                                        sourceDeviceName = Build.MODEL,
                                                        sourceUrl = shared.url,
                                                        safeId = "default",
                                                    )
                                                }
                                            }.getOrNull()
                                            if (retried != null) {
                                                status = sendResultMessage(retried.success, retried.safeName, retried.error)
                                                phase = if (retried.success) SendPhase.SENT else SendPhase.FAILED
                                                return@launch
                                            }
                                        }
                                        status = getString(R.string.send_failed_connection)
                                        phase = SendPhase.FAILED
                                    }
                                }
                            }
                        }
                    },
                    onCopyText = {
                        copyCleanText(this, shared.text)
                        status = "Copied"
                    },
                    onShareWithSomeone = {
                        shareTextExternal(this, shared.text)
                        status = "Shared"
                    },
                    onDismiss = { finish() },
                    sensitiveReason = sensitiveReason,
                )
            }
        }
    }

    private fun showImageShare(app: CacheVaultMobileApp, pairing: com.prooffoundry.cachevaultmobile.data.PairingConfig?) {
        val uri = sharedStreamUri(intent)
        val shared: SharedImage? = uri?.let {
            ImageFileHelper.readSharedImage(this, it, intent?.type)
        }
        setContent {
            CacheVaultMobileTheme {
                var status by remember {
                    mutableStateOf<String?>(
                        if (shared == null) "Could not read image — unsupported type or over 10 MB." else null,
                    )
                }
                var phase by remember {
                    mutableStateOf(if (shared == null) SendPhase.FAILED else SendPhase.IDLE)
                }
                val scope = rememberCoroutineScope()
                val connected = pairing != null && shared != null
                val label = pairing?.pcLabel?.ifBlank { pairing.host } ?: "your PC"
                val imageLabel = shared?.let {
                    val kb = it.bytes.size / 1024
                    "Image ready: ${it.name ?: "image"} · $kb KB"
                } ?: "No image to send"
                SimpleShareScreen(
                    sharedText = "",
                    sharedUrl = null,
                    connectionLabel = label,
                    isConnected = connected,
                    statusMessage = status,
                    phase = phase,
                    onSendToPc = {
                        // Ignore taps while a send is running or already done.
                        if (!phase.blocksNewSend()) {
                            if (pairing == null || shared == null) {
                                status = getString(R.string.send_failed_not_connected)
                                phase = SendPhase.FAILED
                            } else {
                                scope.launch {
                                    phase = SendPhase.SENDING
                                    status = getString(R.string.sending_image_to_vault)
                                    try {
                                        val resp = withContext(Dispatchers.IO) {
                                            val b64 = Base64.encodeToString(shared.bytes, Base64.NO_WRAP)
                                            app.bridgeRepository.client().sendImageToPc(
                                                contentB64 = b64,
                                                mimeType = shared.mimeType,
                                                originalName = shared.name,
                                                sourceApp = "Android Share",
                                                sourceDeviceName = Build.MODEL,
                                                safeId = "default",
                                            )
                                        }
                                        status = sendResultMessage(resp.success, resp.safeName, resp.error)
                                        phase = if (resp.success) SendPhase.SENT else SendPhase.FAILED
                                    } catch (e: BridgeError.Unauthorized) {
                                        status = getString(R.string.send_failed_pairing)
                                        phase = SendPhase.FAILED
                                    } catch (e: BridgeError.Disabled) {
                                        status = getString(R.string.send_failed_mobile_off)
                                        phase = SendPhase.FAILED
                                    } catch (e: Exception) {
                                        status = getString(R.string.send_failed_connection)
                                        phase = SendPhase.FAILED
                                    }
                                }
                            }
                        }
                    },
                    onCopyText = {},
                    onShareWithSomeone = {},
                    onDismiss = { finish() },
                    imageLabel = imageLabel,
                )
            }
        }
    }

    private fun sendResultMessage(success: Boolean, safeName: String?, error: String?): String =
        if (success) {
            getString(R.string.sent_to_vault, safeName ?: "Default Safe")
        } else {
            getString(R.string.send_failed_unknown, error ?: "unknown error")
        }

    @Suppress("DEPRECATION")
    private fun sharedStreamUri(intent: Intent?): Uri? {
        if (intent == null) return null
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }
    }

    private data class SharedPayload(val text: String, val url: String?)

    private fun extractSharedText(intent: Intent?): SharedPayload {
        val action = intent?.action
        val type = intent?.type
        if (Intent.ACTION_SEND == action && type != null && type.startsWith("text/")) {
            val extra = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty()
            val url = extra.trim().takeIf {
                it.startsWith("http://") || it.startsWith("https://")
            }
            return SharedPayload(extra.ifBlank { "(empty)" }, url)
        }
        return SharedPayload("(nothing shared)", null)
    }
}
