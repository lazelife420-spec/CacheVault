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
import com.prooffoundry.cachevaultmobile.data.BridgeError
import com.prooffoundry.cachevaultmobile.data.ImageFileHelper
import com.prooffoundry.cachevaultmobile.data.SensitiveText
import com.prooffoundry.cachevaultmobile.data.SharedImage
import com.prooffoundry.cachevaultmobile.ui.screens.SimpleShareScreen
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
                val scope = rememberCoroutineScope()
                val connected = pairing != null
                val label = pairing?.pcLabel?.ifBlank { pairing.host } ?: "your PC"
                SimpleShareScreen(
                    sharedText = shared.text,
                    sharedUrl = shared.url,
                    connectionLabel = label,
                    isConnected = connected,
                    statusMessage = status,
                    onSendToPc = {
                        if (pairing == null) {
                            status = "Could not send — not connected"
                            return@SimpleShareScreen
                        }
                        scope.launch {
                            status = "Sending to PC…"
                            try {
                                val resp = withContext(Dispatchers.IO) {
                                    app.bridgeRepository.client().sendToPc(
                                        content = shared.text,
                                        itemType = if (shared.url != null) "url" else "text",
                                        sourceApp = "Android Share",
                                        sourceDeviceName = Build.MODEL,
                                        sourceUrl = shared.url,
                                        safeId = "default",
                                    )
                                }
                                status = sendResultMessage(resp.success, resp.safeName, resp.error)
                            } catch (e: BridgeError.Unauthorized) {
                                status = "Could not send — pairing expired"
                            } catch (e: BridgeError.Disabled) {
                                status = "Could not send — Mobile Access off on PC"
                            } catch (e: Exception) {
                                status = "Could not send — check connection"
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
                    onSendToPc = {
                        if (pairing == null || shared == null) {
                            status = "Could not send — not connected"
                            return@SimpleShareScreen
                        }
                        scope.launch {
                            status = "Sending image to PC…"
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
                            } catch (e: BridgeError.Unauthorized) {
                                status = "Could not send — pairing expired"
                            } catch (e: BridgeError.Disabled) {
                                status = "Could not send — Mobile Access off on PC"
                            } catch (e: Exception) {
                                status = "Could not send — check connection"
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
            "Sent to PC · ${safeName ?: "Default Safe"} · Receipt stamped"
        } else {
            "Could not send — ${error ?: "unknown error"}"
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
