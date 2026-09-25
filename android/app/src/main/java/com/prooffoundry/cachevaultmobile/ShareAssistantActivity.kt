package com.prooffoundry.cachevaultmobile

import android.content.Intent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Base64
import androidx.fragment.app.FragmentActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
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
import com.prooffoundry.cachevaultmobile.data.local.LocalIngestion
import com.prooffoundry.cachevaultmobile.data.local.LocalItemKind
import com.prooffoundry.cachevaultmobile.data.local.LocalSafe
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultDatabase
import com.prooffoundry.cachevaultmobile.data.local.LocalVaultPolicy
import com.prooffoundry.cachevaultmobile.ui.screens.LocalShareScreen
import com.prooffoundry.cachevaultmobile.ui.screens.VaultLockScreen
import com.prooffoundry.cachevaultmobile.ui.screens.SendPhase
import com.prooffoundry.cachevaultmobile.ui.screens.blocksNewSend
import com.prooffoundry.cachevaultmobile.ui.screens.copyCleanText
import com.prooffoundry.cachevaultmobile.ui.screens.shareTextExternal
import com.prooffoundry.cachevaultmobile.ui.theme.CacheVaultMobileTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

/**
 * Android Share Sheet entry (CV-MOBILE-1). "Save on this phone" is the
 * default local destination and works with no pairing and no network. The
 * existing Send-to-PC path remains as a separate, deliberate action.
 *
 * Intent handling rules kept from the companion: narrow `ACTION_SEND` for
 * `text/plain` and `image` MIME only; binary reads run off the UI thread; a
 * revoked/unreadable URI or an oversized stream is a visible failure, not a
 * silent save.
 */
class ShareAssistantActivity : FragmentActivity() {
    private val screenOffReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val app = application as? CacheVaultMobileApp ?: return
            app.vaultLockManager.lock()
            if (app.vaultLockStore.isEnabled) showGate()
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as CacheVaultMobileApp
        if (app.vaultLockStore.isEnabled) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        if (app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked) showGate() else showIntent(intent)
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.RESUMED) {
                while (isActive) {
                    delay(1_000)
                    if ((application as CacheVaultMobileApp).vaultLockManager.lockIfIdle()) showGate()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val app = application as CacheVaultMobileApp
        if (app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked) showGate() else showIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        val app = application as? CacheVaultMobileApp ?: return
        if (app.vaultLockStore.isEnabled) window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        if (app.vaultLockStore.isEnabled && !app.vaultLockManager.unlocked) showGate()
    }

    override fun onStart() {
        super.onStart()
        ContextCompat.registerReceiver(
            this, screenOffReceiver, IntentFilter(Intent.ACTION_SCREEN_OFF), ContextCompat.RECEIVER_NOT_EXPORTED,
        )
    }

    override fun onUserInteraction() {
        super.onUserInteraction()
        (application as? CacheVaultMobileApp)?.vaultLockManager?.noteActivity()
    }

    override fun onStop() {
        runCatching { unregisterReceiver(screenOffReceiver) }
        if (!isChangingConfigurations) (application as? CacheVaultMobileApp)?.vaultLockManager?.lock()
        super.onStop()
    }

    private fun showGate() {
        val app = application as CacheVaultMobileApp
        setContent {
            CacheVaultMobileTheme {
                VaultLockScreen(
                    store = app.vaultLockStore,
                    manager = app.vaultLockManager,
                    isGate = true,
                    onUnlocked = { showIntent(intent) },
                )
            }
        }
    }

    private fun showIntent(incomingIntent: Intent?) {
        val app = application as CacheVaultMobileApp
        val pairing = app.pairingStore.load()
        val repo = app.localVaultRepository
        val type = incomingIntent?.type
        if (Intent.ACTION_SEND == incomingIntent?.action && type != null && type.startsWith("image/")) {
            showImageShare(app, repo, pairing, sharedStreamUri(incomingIntent), type)
        } else {
            showTextShare(app, repo, pairing, incomingIntent)
        }
    }

    private fun showTextShare(
        app: CacheVaultMobileApp,
        repo: com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository,
        pairing: com.prooffoundry.cachevaultmobile.data.PairingConfig?,
        sharedIntent: Intent?,
    ) {
        val shared = extractSharedText(sharedIntent)
        val recognized = LocalIngestion.recognizeText(shared.text)
        if (recognized is LocalIngestion.Incoming.Invalid) {
            // Canceled/malformed intake is not persisted as a user item.
            showInvalidShare(repo, "Nothing readable was shared.")
            return
        }
        val incoming = recognized as LocalIngestion.Incoming.Text
        val sensitiveReason = SensitiveText.reason(incoming.content)
        val previewTitle = LocalVaultPolicy.titleFor(incoming.content)
        val previewBody = LocalVaultPolicy.previewFor(incoming.content)

        setContent {
            CacheVaultMobileTheme {
                var status by remember { mutableStateOf<String?>(null) }
                var sendPhase by remember { mutableStateOf(SendPhase.IDLE) }
                var localBusy by remember { mutableStateOf(false) }
                var savedOnPhone by remember { mutableStateOf(false) }
                var safes by remember { mutableStateOf<List<LocalSafe>>(emptyList()) }
                var safeId by remember { mutableStateOf(LocalVaultDatabase.DEFAULT_SAFE_ID) }
                val scope = rememberCoroutineScope()
                val label = pairing?.pcLabel?.ifBlank { pairing.host }?.takeIf { it.isNotBlank() }

                androidx.compose.runtime.LaunchedEffect(Unit) {
                    safes = runCatching { repo.safes() }.getOrDefault(emptyList())
                }

                fun dismiss() {
                    if (!savedOnPhone && sendPhase != SendPhase.SENT) {
                        scope.launch { runCatching { repo.recordCancelledSave() } }
                    }
                    finish()
                }

                LocalShareScreen(
                    previewTitle = previewTitle,
                    previewBody = previewBody,
                    kindLabel = if (incoming.url != null) "LINK" else "TEXT",
                    safes = safes,
                    selectedSafeId = safeId,
                    onSelectSafe = { safeId = it },
                    onSaveLocally = {
                        if (!localBusy && !savedOnPhone) {
                            scope.launch {
                                localBusy = true
                                try {
                                    LocalIngestion.saveText(repo, incoming.content, safeId, "share_sheet")
                                    savedOnPhone = true
                                    status = "Saved on this phone · ${
                                        safes.firstOrNull { it.id == safeId }?.name ?: "Default Safe"
                                    }"
                                } catch (e: Exception) {
                                    runCatching { repo.recordFailedSave(LocalIngestion.failureReason(e)) }
                                    status = e.message ?: "Could not save on this phone."
                                } finally {
                                    localBusy = false
                                }
                            }
                        }
                    },
                    localSaveEnabled = true,
                    localSaveBusy = localBusy,
                    savedOnPhone = savedOnPhone,
                    connectionLabel = label,
                    sendPhase = sendPhase,
                    onSendToPc = {
                        // Existing companion send, unchanged: paired devices only,
                        // with the same single-send guard and self-heal retry.
                        if (!sendPhase.blocksNewSend()) {
                            val initialPairing = app.pairingStore.load()
                            if (initialPairing == null) {
                                status = getString(R.string.send_failed_not_connected)
                                sendPhase = SendPhase.FAILED
                            } else {
                                scope.launch {
                                    sendPhase = SendPhase.SENDING
                                    status = getString(R.string.sending_to_vault)
                                    var p = initialPairing
                                    if (!p.hasUsableHost()) {
                                        val healed = withContext(Dispatchers.IO) {
                                            app.bridgeRepository.discoverAndSelfHealEndpoint()
                                        }
                                        if (healed != null) p = healed
                                    }
                                    try {
                                        val currentClient = BridgeClient(p)
                                        val resp = withContext(Dispatchers.IO) {
                                            currentClient.sendToPc(
                                                content = incoming.content,
                                                itemType = if (incoming.url != null) "url" else "text",
                                                sourceApp = "Android Share",
                                                sourceDeviceName = Build.MODEL,
                                                sourceUrl = incoming.url,
                                                safeId = "default",
                                            )
                                        }
                                        status = sendResultMessage(resp.success, resp.safeName, resp.error)
                                        sendPhase = if (resp.success) SendPhase.SENT else SendPhase.FAILED
                                    } catch (e: BridgeError.Unauthorized) {
                                        status = getString(R.string.send_failed_pairing)
                                        sendPhase = SendPhase.FAILED
                                    } catch (e: BridgeError.Disabled) {
                                        status = getString(R.string.send_failed_mobile_off)
                                        sendPhase = SendPhase.FAILED
                                    } catch (e: Exception) {
                                        val healed = withContext(Dispatchers.IO) {
                                            app.bridgeRepository.discoverAndSelfHealEndpoint()
                                        }
                                        if (healed != null) {
                                            val healedClient = BridgeClient(healed)
                                            val retried = runCatching {
                                                withContext(Dispatchers.IO) {
                                                    healedClient.sendToPc(
                                                        content = incoming.content,
                                                        itemType = if (incoming.url != null) "url" else "text",
                                                        sourceApp = "Android Share",
                                                        sourceDeviceName = Build.MODEL,
                                                        sourceUrl = incoming.url,
                                                        safeId = "default",
                                                    )
                                                }
                                            }.getOrNull()
                                            if (retried != null) {
                                                status = sendResultMessage(retried.success, retried.safeName, retried.error)
                                                sendPhase = if (retried.success) SendPhase.SENT else SendPhase.FAILED
                                                return@launch
                                            }
                                        }
                                        status = getString(R.string.send_failed_connection)
                                        sendPhase = SendPhase.FAILED
                                    }
                                }
                            }
                        }
                    },
                    onCopyText = {
                        copyCleanText(this@ShareAssistantActivity, incoming.content)
                        status = "Copied"
                    },
                    onShareWithSomeone = {
                        shareTextExternal(this@ShareAssistantActivity, incoming.content)
                        status = "Share sheet opened"
                    },
                    onDismiss = { dismiss() },
                    statusMessage = status,
                    sensitiveReason = sensitiveReason,
                )
            }
        }
    }

    private fun showImageShare(
        app: CacheVaultMobileApp,
        repo: com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository,
        pairing: com.prooffoundry.cachevaultmobile.data.PairingConfig?,
        uri: Uri?,
        declaredType: String?,
    ) {
        val mime = uri?.let { contentResolver.getType(it) } ?: declaredType
        val displayName = uri?.let {
            runCatching {
                contentResolver.query(it, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                    ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
            }.getOrNull()
        }
        val recognized = if (uri == null) {
            LocalIngestion.Incoming.Invalid("empty")
        } else {
            LocalIngestion.recognizeImage(mime, displayName)
        }
        if (recognized is LocalIngestion.Incoming.Invalid) {
            showInvalidShare(repo, "That image type is not supported or could not be read.")
            return
        }
        val imageUri = uri!!

        setContent {
            CacheVaultMobileTheme {
                var status by remember { mutableStateOf<String?>(null) }
                var sendPhase by remember { mutableStateOf(SendPhase.IDLE) }
                var localBusy by remember { mutableStateOf(false) }
                var savedOnPhone by remember { mutableStateOf(false) }
                var safes by remember { mutableStateOf<List<LocalSafe>>(emptyList()) }
                var safeId by remember { mutableStateOf(LocalVaultDatabase.DEFAULT_SAFE_ID) }
                val scope = rememberCoroutineScope()
                val label = pairing?.pcLabel?.ifBlank { pairing.host }?.takeIf { it.isNotBlank() }

                androidx.compose.runtime.LaunchedEffect(Unit) {
                    safes = runCatching { repo.safes() }.getOrDefault(emptyList())
                }

                fun dismiss() {
                    if (!savedOnPhone && sendPhase != SendPhase.SENT) {
                        scope.launch { runCatching { repo.recordCancelledSave() } }
                    }
                    finish()
                }

                LocalShareScreen(
                    previewTitle = displayName ?: "Image",
                    previewBody = "Type: ${mime ?: "image"}",
                    kindLabel = "IMAGE",
                    safes = safes,
                    selectedSafeId = safeId,
                    onSelectSafe = { safeId = it },
                    onSaveLocally = {
                        if (!localBusy && !savedOnPhone) {
                            scope.launch {
                                localBusy = true
                                try {
                                    LocalIngestion.saveImage(
                                        repo,
                                        declaredMime = mime,
                                        displayName = displayName,
                                        safeId = safeId,
                                        openStream = { contentResolver.openInputStream(imageUri) },
                                    )
                                    savedOnPhone = true
                                    status = "Saved on this phone · ${
                                        safes.firstOrNull { it.id == safeId }?.name ?: "Default Safe"
                                    }"
                                } catch (e: Exception) {
                                    runCatching { repo.recordFailedSave(LocalIngestion.failureReason(e)) }
                                    status = e.message ?: "Could not save on this phone."
                                } finally {
                                    localBusy = false
                                }
                            }
                        }
                    },
                    localSaveEnabled = true,
                    localSaveBusy = localBusy,
                    savedOnPhone = savedOnPhone,
                    connectionLabel = label,
                    sendPhase = sendPhase,
                    onSendToPc = {
                        if (!sendPhase.blocksNewSend()) {
                            if (pairing == null) {
                                status = getString(R.string.send_failed_not_connected)
                                sendPhase = SendPhase.FAILED
                            } else {
                                scope.launch {
                                    sendPhase = SendPhase.SENDING
                                    status = getString(R.string.sending_image_to_vault)
                                    try {
                                        val shared: SharedImage? = withContext(Dispatchers.IO) {
                                            ImageFileHelper.readSharedImage(
                                                this@ShareAssistantActivity, imageUri, mime,
                                            )
                                        }
                                        if (shared == null) {
                                            status = getString(R.string.send_failed_unknown, "image unreadable")
                                            sendPhase = SendPhase.FAILED
                                            return@launch
                                        }
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
                                        sendPhase = if (resp.success) SendPhase.SENT else SendPhase.FAILED
                                    } catch (e: BridgeError.Unauthorized) {
                                        status = getString(R.string.send_failed_pairing)
                                        sendPhase = SendPhase.FAILED
                                    } catch (e: BridgeError.Disabled) {
                                        status = getString(R.string.send_failed_mobile_off)
                                        sendPhase = SendPhase.FAILED
                                    } catch (e: Exception) {
                                        status = getString(R.string.send_failed_connection)
                                        sendPhase = SendPhase.FAILED
                                    }
                                }
                            }
                        }
                    },
                    onCopyText = null,
                    onShareWithSomeone = null,
                    onDismiss = { dismiss() },
                    statusMessage = status,
                )
            }
        }
    }

    private fun showInvalidShare(
        repo: com.prooffoundry.cachevaultmobile.data.local.LocalVaultRepository,
        message: String,
    ) {
        setContent {
            CacheVaultMobileTheme {
                val scope = rememberCoroutineScope()
                LocalShareScreen(
                    previewTitle = message,
                    previewBody = "",
                    kindLabel = "NOT SAVED",
                    safes = emptyList(),
                    selectedSafeId = LocalVaultDatabase.DEFAULT_SAFE_ID,
                    onSelectSafe = {},
                    onSaveLocally = {},
                    localSaveEnabled = false,
                    localSaveBusy = false,
                    savedOnPhone = false,
                    connectionLabel = null,
                    onSendToPc = {},
                    sendPhase = SendPhase.FAILED,
                    onCopyText = null,
                    onShareWithSomeone = null,
                    onDismiss = {
                        scope.launch { runCatching { repo.recordCancelledSave() } }
                        finish()
                    },
                    statusMessage = null,
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

    private data class SharedPayload(val text: String?, val url: String?)

    private fun extractSharedText(intent: Intent?): SharedPayload {
        val action = intent?.action
        val type = intent?.type
        if (Intent.ACTION_SEND == action && type != null && type.startsWith("text/")) {
            val extra = intent.getStringExtra(Intent.EXTRA_TEXT)
            val url = extra?.trim()?.takeIf {
                it.startsWith("http://") || it.startsWith("https://")
            }
            return SharedPayload(extra, url)
        }
        return SharedPayload(null, null)
    }
}
