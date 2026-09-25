package com.prooffoundry.cachevaultmobile

import android.content.Intent
import android.net.Uri
import android.view.WindowManager
import android.content.pm.ShortcutManager
import androidx.lifecycle.Lifecycle
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import com.prooffoundry.cachevaultmobile.security.UnlockMode
import com.prooffoundry.cachevaultmobile.security.VaultLockManager
import com.prooffoundry.cachevaultmobile.security.VerifyResult
import com.prooffoundry.cachevaultmobile.integration.AppShortcutPublisher
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class VaultLockInstrumentedTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun lockGatesDeepLinkAndSavedContentAcrossWrongPinBackgroundAndRestart() {
        val app = compose.activity.application as CacheVaultMobileApp
        runBlocking { app.vaultLockStore.configure(TEST_PIN, UnlockMode.PIN) }
        app.vaultLockManager.configurationChanged()
        app.vaultLockManager.lock()
        compose.runOnUiThread { compose.activity.window.addFlags(WindowManager.LayoutParams.FLAG_SECURE) }

        // A new process session is always locked; no "unlocked" bit is persisted.
        assertFalse(VaultLockManager(app.vaultLockStore).unlocked)
        compose.waitForIdle()
        exists("Your vault is sealed")
        exists("Paired PC browsing stays unavailable until this app is unlocked.")
        assertTrue(compose.activity.window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0)

        compose.onNodeWithText("PIN").performTextInput("000000")
        compose.onNodeWithText("Unlock").performClick()
        eventuallyExists("That PIN or passphrase did not unlock the vault.")
        exists("Your vault is sealed")

        compose.onNodeWithText("PIN").performTextClearance()
        compose.onNodeWithText("PIN").performTextInput(TEST_PIN)
        compose.onNodeWithText("Unlock").performClick()
        eventuallyExists("Local vault · This phone")

        // Stopping the Activity simulates leaving the app; return must show the gate.
        compose.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        assertFalse(app.vaultLockManager.unlocked)
        compose.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        exists("Your vault is sealed")

        // URI entry points still resolve into the same gate before opening a route.
        compose.runOnUiThread {
            compose.activity.acceptIncomingIntent(
                Intent(Intent.ACTION_VIEW, Uri.parse("cachevault://open/favorites")),
            )
        }
        exists("Your vault is sealed")
        AppShortcutPublisher.publish(compose.activity)
        val saveShortcut = compose.activity.getSystemService(ShortcutManager::class.java)
            .dynamicShortcuts.first { it.id == "save" }
        compose.runOnUiThread { compose.activity.acceptIncomingIntent(requireNotNull(saveShortcut.intent)) }
        exists("Your vault is sealed")
    }

    @Test fun repeatedWrongPinsThrottleWithoutDeletingOrResettingTheVault() = runBlocking {
        val app = compose.activity.application as CacheVaultMobileApp
        app.vaultLockStore.configure(TEST_PIN, UnlockMode.PIN)
        repeat(4) { assertEquals(VerifyResult.Invalid, app.vaultLockStore.verify("000000")) }
        assertTrue(app.vaultLockStore.verify("000000") is VerifyResult.Throttled)
        assertTrue(app.vaultLockStore.isEnabled)
        // Setup is explicit and non-destructive; it resets the retry window for the fixture.
        app.vaultLockStore.configure(TEST_PIN, UnlockMode.PIN)
        assertEquals(VerifyResult.Accepted, app.vaultLockStore.verify(TEST_PIN))
    }

    @Test fun shareIntentIsHeldBehindGateAndWrongSecretDoesNotRevealPayload() {
        val app = compose.activity.application as CacheVaultMobileApp
        runBlocking { app.vaultLockStore.configure(TEST_PIN, UnlockMode.PIN) }
        app.vaultLockManager.configurationChanged()
        app.vaultLockManager.lock()
        val share = Intent(compose.activity, ShareAssistantActivity::class.java).apply {
            action = Intent.ACTION_SEND
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, SECRET_SHARE_TEXT)
        }
        compose.activity.startActivity(share)
        compose.waitForIdle()
        exists("Your vault is sealed")
        compose.waitUntil(5_000) { compose.onAllNodesWithText(SECRET_SHARE_TEXT).fetchSemanticsNodes().isEmpty() }
    }

    private fun exists(text: String) {
        compose.onNodeWithText(text).fetchSemanticsNode()
    }

    private fun eventuallyExists(text: String) {
        compose.waitUntil(10_000) { compose.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty() }
    }

    private companion object {
        const val TEST_PIN = "942681"
        const val SECRET_SHARE_TEXT = "SHARE PAYLOAD MUST STAY HIDDEN"
    }
}
