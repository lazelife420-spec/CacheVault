package com.prooffoundry.cachevaultmobile.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** App access gate. This authenticates access to the UI; it does not encrypt existing vault files. */
class VaultLockStore(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context,
        PREFS,
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    val isEnabled: Boolean get() = prefs.getBoolean(KEY_ENABLED, false)
    val lockTimeoutMs: Long get() = prefs.getLong(KEY_TIMEOUT, DEFAULT_TIMEOUT_MS)
    val biometricEnabled: Boolean get() = prefs.getBoolean(KEY_BIOMETRIC, false)

    suspend fun configure(secret: String, mode: UnlockMode) = withContext(Dispatchers.Default) {
        require(secret.isValid(mode))
        val salt = ByteArray(SALT_BYTES).also(SecureRandom()::nextBytes)
        val verifier = derive(secret, salt)
        prefs.edit()
            .putString(KEY_MODE, mode.name)
            .putString(KEY_SALT, android.util.Base64.encodeToString(salt, android.util.Base64.NO_WRAP))
            .putString(KEY_VERIFIER, android.util.Base64.encodeToString(verifier, android.util.Base64.NO_WRAP))
            .putBoolean(KEY_ENABLED, true)
            .putLong(KEY_TIMEOUT, DEFAULT_TIMEOUT_MS)
            .putInt(KEY_FAILURES, 0)
            .putLong(KEY_LOCKED_UNTIL, 0L)
            .apply()
        verifier.fill(0)
    }

    suspend fun verify(secret: String): VerifyResult = withContext(Dispatchers.Default) {
        val until = prefs.getLong(KEY_LOCKED_UNTIL, 0L)
        val waitMs = until - System.currentTimeMillis()
        if (waitMs > 0) return@withContext VerifyResult.Throttled(waitMs)
        val salt = decode(KEY_SALT) ?: return@withContext VerifyResult.Invalid
        val expected = decode(KEY_VERIFIER) ?: return@withContext VerifyResult.Invalid
        val actual = derive(secret, salt)
        val valid = MessageDigest.isEqual(expected, actual)
        actual.fill(0)
        expected.fill(0)
        if (valid) {
            prefs.edit().putInt(KEY_FAILURES, 0).putLong(KEY_LOCKED_UNTIL, 0L).apply()
            VerifyResult.Accepted
        } else {
            val failures = prefs.getInt(KEY_FAILURES, 0) + 1
            val delay = if (failures < FAILURE_THRESHOLD) 0L else {
                val exponent = ((failures - FAILURE_THRESHOLD) / FAILURE_STEP).coerceAtMost(4)
                BASE_LOCKOUT_MS * (1L shl exponent)
            }
            prefs.edit().putInt(KEY_FAILURES, failures)
                .putLong(KEY_LOCKED_UNTIL, System.currentTimeMillis() + delay).apply()
            if (delay > 0) VerifyResult.Throttled(delay) else VerifyResult.Invalid
        }
    }

    suspend fun disable(secret: String): VerifyResult {
        val result = verify(secret)
        if (result == VerifyResult.Accepted) {
            clearBiometricKey()
            prefs.edit().clear().apply()
        }
        return result
    }

    fun setTimeout(timeoutMs: Long) {
        require(timeoutMs in ALLOWED_TIMEOUTS)
        prefs.edit().putLong(KEY_TIMEOUT, timeoutMs).apply()
    }

    fun mode(): UnlockMode = runCatching { UnlockMode.valueOf(prefs.getString(KEY_MODE, UnlockMode.PIN.name)!!) }
        .getOrDefault(UnlockMode.PIN)

    fun enableBiometric(cipherText: ByteArray, iv: ByteArray) {
        prefs.edit().putString(KEY_BIO_CIPHERTEXT, android.util.Base64.encodeToString(cipherText, android.util.Base64.NO_WRAP))
            .putString(KEY_BIO_IV, android.util.Base64.encodeToString(iv, android.util.Base64.NO_WRAP))
            .putBoolean(KEY_BIOMETRIC, true).apply()
    }

    fun disableBiometric() { prefs.edit().putBoolean(KEY_BIOMETRIC, false).apply() }

    fun biometricCipherForUnlock(): Cipher? = runCatching {
        val iv = decode(KEY_BIO_IV) ?: return null
        val key = keyStoreSecretKey() ?: return null
        Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv)) }
    }.getOrNull()

    fun completeBiometricUnlock(cipher: Cipher): Boolean = runCatching {
        val encrypted = decode(KEY_BIO_CIPHERTEXT) ?: return false
        MessageDigest.isEqual(cipher.doFinal(encrypted), BIO_CANARY)
    }.getOrDefault(false)

    fun biometricEnrollmentCipher(): Cipher? = runCatching {
        val ks = loadKeyStore()
        // A prior biometric enrollment may have invalidated its key. Setup is
        // an explicit action after PIN/passphrase unlock, so replace that
        // unused gate key before creating the new enrollment-bound key.
        runCatching { ks.deleteEntry(BIO_KEY_ALIAS) }
        val generator = javax.crypto.KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        val builder = KeyGenParameterSpec.Builder(
            BIO_KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setRandomizedEncryptionRequired(true)
            .setUserAuthenticationRequired(true)
            .setUserAuthenticationValidityDurationSeconds(-1)
            .setInvalidatedByBiometricEnrollment(true)
        generator.init(builder.build())
        generator.generateKey()
        val key = keyStoreSecretKey() ?: return null
        Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key) }
    }.getOrNull()

    fun finishBiometricEnrollment(cipher: Cipher): Boolean = runCatching {
        val encrypted = cipher.doFinal(BIO_CANARY)
        enableBiometric(encrypted, cipher.iv)
        true
    }.getOrDefault(false)

    fun clearBiometricKey() { runCatching { loadKeyStore().deleteEntry(BIO_KEY_ALIAS) }; disableBiometric() }

    private fun decode(key: String): ByteArray? = prefs.getString(key, null)?.let {
        runCatching { android.util.Base64.decode(it, android.util.Base64.NO_WRAP) }.getOrNull()
    }

    private fun keyStoreSecretKey(): SecretKey? = loadKeyStore().getKey(BIO_KEY_ALIAS, null) as? SecretKey
    private fun loadKeyStore(): KeyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    private fun derive(secret: String, salt: ByteArray): ByteArray {
        return VaultLockKdf.derive(secret, salt)
    }

    private fun String.isValid(mode: UnlockMode): Boolean = when (mode) {
        UnlockMode.PIN -> length in 6..12 && all(Char::isDigit)
        UnlockMode.PASSPHRASE -> length in 10..128
    }

    companion object {
        private const val PREFS = "cache_vault_lock"
        private const val KEY_ENABLED = "enabled"
        private const val KEY_MODE = "mode"
        private const val KEY_SALT = "salt"
        private const val KEY_VERIFIER = "verifier"
        private const val KEY_TIMEOUT = "timeout_ms"
        private const val KEY_FAILURES = "failures"
        private const val KEY_LOCKED_UNTIL = "locked_until"
        private const val KEY_BIOMETRIC = "biometric"
        private const val KEY_BIO_IV = "biometric_iv"
        private const val KEY_BIO_CIPHERTEXT = "biometric_ciphertext"
        private const val SALT_BYTES = 16
        // PBKDF2-HMAC-SHA256 with a per-install random salt, in line with NIST SP 800-132.
        const val DEFAULT_TIMEOUT_MS = 60_000L
        private const val FAILURE_THRESHOLD = 5
        private const val FAILURE_STEP = 3
        private const val BASE_LOCKOUT_MS = 30_000L
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val BIO_KEY_ALIAS = "cache_vault_biometric_gate_v1"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private val BIO_CANARY = "cache-vault-biometric-unlock-v1".toByteArray(Charsets.UTF_8)
        val ALLOWED_TIMEOUTS = setOf(15_000L, 60_000L, 300_000L, 900_000L)
    }
}

internal object VaultLockKdf {
    const val ITERATIONS = 310_000
    fun derive(secret: String, salt: ByteArray): ByteArray {
        val spec = PBEKeySpec(secret.toCharArray(), salt, ITERATIONS, 256)
        return try { SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded }
        finally { spec.clearPassword() }
    }
}

enum class UnlockMode { PIN, PASSPHRASE }
sealed interface VerifyResult {
    data object Accepted : VerifyResult
    data object Invalid : VerifyResult
    data class Throttled(val remainingMs: Long) : VerifyResult
}
