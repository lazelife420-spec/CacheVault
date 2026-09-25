package com.prooffoundry.cachevaultmobile.security

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import java.security.MessageDigest

class VaultLockKdfTest {
    @Test fun pbkdf2VerifierIsDeterministicSaltedAndNotThePassword() {
        val saltA = ByteArray(16) { it.toByte() }
        val saltB = ByteArray(16) { (it + 1).toByte() }
        val first = VaultLockKdf.derive("correct horse battery staple", saltA)
        val repeat = VaultLockKdf.derive("correct horse battery staple", saltA)
        val otherSalt = VaultLockKdf.derive("correct horse battery staple", saltB)

        assertEquals(32, first.size)
        assertArrayEquals(first, repeat)
        assertFalse(MessageDigest.isEqual(first, otherSalt))
        assertFalse(String(first, Charsets.UTF_8).contains("correct horse"))
        assertEquals(310_000, VaultLockKdf.ITERATIONS)
    }
}
