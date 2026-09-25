package com.prooffoundry.cachevaultmobile

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ShortcutManager
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.prooffoundry.cachevaultmobile.integration.AppShortcutPublisher
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AndroidSystemIntegrationInstrumentedTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun launcherShortcutsPointToRealDestinations() {
        AppShortcutPublisher.publish(context)
        val shortcuts = context.getSystemService(ShortcutManager::class.java)
            .dynamicShortcuts.associateBy { it.id }

        assertEquals(setOf("save", "search", "favorites", "safes"), shortcuts.keys)
        shortcuts.forEach { (id, shortcut) ->
            val intent = requireNotNull(shortcut.intent)
            assertEquals(MainActivity::class.java.name, intent.component?.className)
            assertEquals("cachevault://open/$id", intent.dataString)
        }
    }

    @Test
    fun systemShareAndAppDeepLinksResolveToExpectedActivities() {
        assertTrue(resolvesTo(Intent(Intent.ACTION_SEND).setType("text/plain"), ShareAssistantActivity::class.java.name))
        assertTrue(resolvesTo(Intent(Intent.ACTION_SEND).setType("image/png"), ShareAssistantActivity::class.java.name))
        assertTrue(
            resolvesTo(
                Intent(Intent.ACTION_VIEW, Uri.parse("cachevault://open/search")),
                MainActivity::class.java.name,
            ),
        )
    }

    @Test
    fun manifestAvoidsBroadStorageAndSurveillancePermissions() {
        val info = context.packageManager.getPackageInfo(
            context.packageName,
            PackageManager.GET_PERMISSIONS or PackageManager.GET_SERVICES,
        )
        val permissions = info.requestedPermissions.orEmpty().toSet()
        assertFalse(Manifest.permission.READ_EXTERNAL_STORAGE in permissions)
        assertFalse(Manifest.permission.WRITE_EXTERNAL_STORAGE in permissions)
        assertFalse("android.permission.READ_MEDIA_IMAGES" in permissions)
        assertFalse("android.permission.READ_MEDIA_VIDEO" in permissions)

        val forbiddenBindings = setOf(
            Manifest.permission.BIND_ACCESSIBILITY_SERVICE,
            "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE",
        )
        assertTrue(info.services.orEmpty().none { it.permission in forbiddenBindings })
    }

    private fun resolvesTo(intent: Intent, activityClass: String): Boolean =
        context.packageManager.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY).any {
            it.activityInfo.packageName == context.packageName && it.activityInfo.name == activityClass
        }
}
