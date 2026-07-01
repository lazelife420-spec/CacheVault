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
        val lastSeenAt = prefs.getString(KEY_LAST_SEEN_AT, null)
        val autoConnectApproved = prefs.getBoolean(KEY_AUTO_CONNECT_APPROVED, false)
        val keepConnectedInBackground = prefs.getBoolean(KEY_KEEP_CONNECTED_IN_BACKGROUND, false)
        return PairingConfig(
            host = host,
            port = port,
            deviceId = deviceId,
            token = token,
            pcLabel = label,
            lastSeenAt = lastSeenAt,
            autoConnectApproved = autoConnectApproved,
            keepConnectedInBackground = keepConnectedInBackground,
        )
    }

    fun save(config: PairingConfig) {
        val clean = PairingConfig.sanitize(
            config.host, config.port, config.deviceId, config.token, config.pcLabel,
        )
        prefs.edit()
            .putString(KEY_HOST, clean.host)
            .putInt(KEY_PORT, clean.port)
            .putString(KEY_DEVICE_ID, clean.deviceId)
            .putString(KEY_TOKEN, clean.token)
            .putString(KEY_PC_LABEL, clean.pcLabel)
            .putString(KEY_LAST_SEEN_AT, clean.lastSeenAt)
            .putBoolean(KEY_AUTO_CONNECT_APPROVED, clean.autoConnectApproved)
            .putBoolean(KEY_KEEP_CONNECTED_IN_BACKGROUND, clean.keepConnectedInBackground)
            .apply()
    }

    fun updatePcLabel(label: String) {
        prefs.edit().putString(KEY_PC_LABEL, label.trim()).apply()
    }

    fun updateConnectionPreferences(
        autoConnectApproved: Boolean? = null,
        keepConnectedInBackground: Boolean? = null,
    ) {
        val edit = prefs.edit()
        autoConnectApproved?.let { edit.putBoolean(KEY_AUTO_CONNECT_APPROVED, it) }
        keepConnectedInBackground?.let { edit.putBoolean(KEY_KEEP_CONNECTED_IN_BACKGROUND, it) }
        edit.apply()
    }

    fun updateLastSeen(lastSeenAt: String?) {
        prefs.edit().putString(KEY_LAST_SEEN_AT, lastSeenAt).apply()
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
        private const val KEY_LAST_SEEN_AT = "last_seen_at"
        private const val KEY_AUTO_CONNECT_APPROVED = "auto_connect_approved"
        private const val KEY_KEEP_CONNECTED_IN_BACKGROUND = "keep_connected_in_background"
    }
}
