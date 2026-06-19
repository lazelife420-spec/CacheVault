package com.prooffoundry.cachevaultmobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SensitiveTextTest {
    @Test
    fun plainTextIsNotSensitive() {
        assertNull(SensitiveText.reason("Pick up milk and eggs on the way home"))
        assertNull(SensitiveText.reason("https://example.com/articles/how-to"))
        assertNull(SensitiveText.reason("C:\\Users\\me\\notes.txt"))
        assertNull(SensitiveText.reason(""))
        assertNull(SensitiveText.reason(null))
    }

    @Test
    fun apiKeyPrefixesDetected() {
        assertEquals("API key/token", SensitiveText.reason("sk-abcdEFGH1234ijklMNOP5678"))
        assertEquals("API key/token", SensitiveText.reason("AKIAABCDEFGHIJKLMNOP"))
        assertEquals(
            "API key/token",
            SensitiveText.reason("ghp_abcdefghijklmnopqrstuvwxyz0123"),
        )
    }

    @Test
    fun jwtDetected() {
        val jwt = "eyJhbGciOi.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4"
        assertEquals("JWT token", SensitiveText.reason(jwt))
    }

    @Test
    fun credentialAssignmentDetected() {
        assertEquals("a password or token", SensitiveText.reason("password = hunter2xyz"))
        assertEquals("a password or token", SensitiveText.reason("api_key: abcd1234efgh"))
    }

    @Test
    fun privateKeyDetected() {
        val pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----"
        assertEquals("private key", SensitiveText.reason(pem))
    }

    @Test
    fun oneTimeCodeDetected() {
        assertEquals("a one-time code", SensitiveText.reason("482915"))
        assertNull(SensitiveText.reason("12")) // too short
    }

    @Test
    fun cardNumberDetectedViaLuhn() {
        // Valid Luhn test card number.
        assertEquals("a card number", SensitiveText.reason("4242 4242 4242 4242"))
        // 16 digits that fail Luhn are not flagged as a card.
        assertTrue(SensitiveText.reason("1234 5678 9012 3456") != "a card number")
    }

    @Test
    fun highEntropySecretDetected() {
        assertEquals("a high-entropy secret", SensitiveText.reason("Xq7Vb2Lm9Kd4Rt6Wz1Ya8Pc"))
    }

    @Test
    fun recoveryCodeDetected() {
        assertEquals("a recovery code", SensitiveText.reason("Your recovery code: ab12-cd34"))
    }
}
