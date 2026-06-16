package com.prooffoundry.cachevaultmobile.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class PairingStore(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context,
        PREFS_NAME,
        MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    fun isPaired(): Boolean =
        !prefs.getString(KEY_HOST, null).isNullOrBlank() &&
            !prefs.getString(KEY_DEVICE_ID, null).isNullOrBlank() &&
            !prefs.getString(KEY_TOKEN, null).isNullOrBlank()

    fun load(): PairingConfig? {
        val host = prefs.getString(KEY_HOST, null) ?: return null
        val deviceId = prefs.getString(KEY_DEVICE_ID, null) ?: return null
        val token = prefs.getString(KEY_TOKEN, null) ?: return null
        val port = prefs.getInt(KEY_PORT, DEFAULT_PORT)
        val label = prefs.getString(KEY_PC_LABEL, "") ?: ""
        return PairingConfig(host, port, deviceId, token, label)
    }

    fun save(config: PairingConfig) {
        prefs.edit()
            .putString(KEY_HOST, config.host.trim())
            .putInt(KEY_PORT, config.port)
            .putString(KEY_DEVICE_ID, config.deviceId.trim())
            .putString(KEY_TOKEN, config.token.trim())
            .putString(KEY_PC_LABEL, config.pcLabel.trim())
            .apply()
    }

    fun updatePcLabel(label: String) {
        prefs.edit().putString(KEY_PC_LABEL, label.trim()).apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    companion object {
        const val DEFAULT_PORT = 8742
        private const val PREFS_NAME = "cache_vault_mobile_pairing"
        private const val KEY_HOST = "host"
        private const val KEY_PORT = "port"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_TOKEN = "token"
        private const val KEY_PC_LABEL = "pc_label"
    }
}
