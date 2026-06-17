package com.prooffoundry.cachevaultmobile.ui

import android.content.Intent

/** Optional launch extras for Manual Setup (used by instrumented tests and deep links). */
data class ManualSetupPrefill(
    val host: String = "",
    val port: Int? = null,
    val deviceId: String = "",
    val token: String = "",
    val openManualSetup: Boolean = false,
) {
    companion object {
        const val EXTRA_HOST = "manual_setup_host"
        const val EXTRA_PORT = "manual_setup_port"
        const val EXTRA_DEVICE_ID = "manual_setup_device_id"
        const val EXTRA_TOKEN = "manual_setup_token"
        const val EXTRA_OPEN = "open_manual_setup"

        fun from(intent: Intent?): ManualSetupPrefill {
            if (intent == null) return ManualSetupPrefill()
            val portRaw = intent.getStringExtra(EXTRA_PORT)?.toIntOrNull()
                ?: if (intent.hasExtra(EXTRA_PORT)) intent.getIntExtra(EXTRA_PORT, 0).takeIf { it > 0 } else null
            return ManualSetupPrefill(
                host = intent.getStringExtra(EXTRA_HOST).orEmpty(),
                port = portRaw,
                deviceId = intent.getStringExtra(EXTRA_DEVICE_ID).orEmpty(),
                token = intent.getStringExtra(EXTRA_TOKEN).orEmpty(),
                openManualSetup = intent.getBooleanExtra(EXTRA_OPEN, false),
            )
        }
    }
}
