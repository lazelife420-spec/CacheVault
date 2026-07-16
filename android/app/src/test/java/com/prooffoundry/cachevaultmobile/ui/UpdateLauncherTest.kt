package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.UserMessages
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateLauncherTest {

    @Test
    fun updateUrlIsTheFixedTrustedConstant() {
        assertEquals(UserMessages.TRUSTED_UPDATE_URL, UpdateLauncher.updateUrl())
    }

    @Test
    fun launchUpdateAlwaysOpensTheFixedUrl() {
        // launchUpdate takes no bridge/server-derived input at all — there is
        // no parameter through which a bridge response could ever substitute
        // a different destination.
        var opened: String? = null
        UpdateLauncher.launchUpdate { url -> opened = url }
        assertEquals(UserMessages.TRUSTED_UPDATE_URL, opened)
    }

    @Test
    fun successfulLaunchReturnsTrue() {
        val result = UpdateLauncher.launchUpdate { /* no-op: launch succeeds */ }
        assertTrue(result)
    }

    @Test
    fun failedLaunchReturnsFalseNotSuccess() {
        val result = UpdateLauncher.launchUpdate {
            throw RuntimeException("no activity found to handle Intent")
        }
        assertFalse(result)
    }

    @Test
    fun failedLaunchDoesNotPropagateTheException() {
        // A crash here would take the whole screen down over a dead link —
        // launchUpdate must swallow it and report failure instead.
        UpdateLauncher.launchUpdate { throw IllegalStateException("boom") }
    }
}
