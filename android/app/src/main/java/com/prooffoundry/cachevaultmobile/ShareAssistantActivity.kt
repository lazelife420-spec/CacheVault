package com.prooffoundry.cachevaultmobile

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import com.prooffoundry.cachevaultmobile.data.BridgeError
import com.prooffoundry.cachevaultmobile.data.SensitiveText
import com.prooffoundry.cachevaultmobile.ui.screens.SimpleShareScreen
import com.prooffoundry.cachevaultmobile.ui.screens.copyCleanText
import com.prooffoundry.cachevaultmobile.ui.screens.shareTextExternal
import com.prooffoundry.cachevaultmobile.ui.theme.CacheVaultMobileTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Android Share Sheet entry — opens Simple Mode for shared text/links. */
class ShareAssistantActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val shared = extractSharedText(intent)
        val sensitiveReason = SensitiveText.reason(shared.text)
        val app = application as CacheVaultMobileApp
        val pairing = app.pairingStore.load()
        setContent {
            CacheVaultMobileTheme {
                var status by mutableStateOf<String?>(null)
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
                                        sourceDeviceName = android.os.Build.MODEL,
                                        sourceUrl = shared.url,
                                        safeId = "default",
                                    )
                                }
                                status = if (resp.success) {
                                    "Sent to PC · ${resp.safeName ?: "Default Safe"} · Receipt stamped"
                                } else {
                                    "Could not send — ${resp.error ?: "unknown error"}"
                                }
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
