package com.prooffoundry.cachevaultmobile

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import com.prooffoundry.cachevaultmobile.data.PairingStore
import com.prooffoundry.cachevaultmobile.ui.ManualSetupPrefill
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Exercise Manual Setup connect flow — fields prefilled via launch intent, Connect tapped in UI. */
@RunWith(AndroidJUnit4::class)
class ManualSetupFlowInstrumentedTest {

    @Test
    fun manualSetupViaUi() {
        val args = InstrumentationRegistry.getArguments()
        val host = args.getString("host") ?: error("Missing -e host")
        val port = args.getString("port") ?: "8742"
        val deviceId = args.getString("device_id") ?: error("Missing -e device_id")
        val token = args.getString("token") ?: error("Missing -e token")
        val expectFailure = args.getString("expect_failure") == "1"

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        PairingStore(context).clear()

        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName)!!
        launch.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK or Intent.FLAG_ACTIVITY_NEW_TASK)
        launch.putExtra(ManualSetupPrefill.EXTRA_HOST, host)
        launch.putExtra(ManualSetupPrefill.EXTRA_PORT, port)
        launch.putExtra(ManualSetupPrefill.EXTRA_DEVICE_ID, deviceId)
        launch.putExtra(ManualSetupPrefill.EXTRA_TOKEN, token)
        launch.putExtra(ManualSetupPrefill.EXTRA_OPEN, true)
        context.startActivity(launch)

        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        device.waitForIdle()

        val hostField = device.wait(
            Until.findObject(By.desc("manual_setup_host")),
            20_000,
        )
        assertNotNull("Manual Setup form not shown", hostField)

        tapConnect(device)
        device.waitForIdle()

        if (expectFailure) {
            val error = device.wait(
                Until.findObject(By.textContains("Could not connect")),
                12_000,
            )
            assertNotNull("Expected Could not connect error", error)
            assertTrue(
                "Bad token must not mark phone paired",
                !PairingStore(context).isPaired(),
            )
        } else {
            val home = device.wait(
                Until.findObject(By.textContains("Vault Sections")),
                35_000,
            )
            if (home == null) {
                val err = device.findObject(By.textContains("Could not connect"))
                assertNotNull(
                    "Manual Setup did not reach home; error=${err?.text ?: "none"}",
                    home,
                )
            }
            assertTrue(PairingStore(context).isPaired())
        }
    }

    private fun tapConnect(device: UiDevice) {
        device.findObject(By.textContains("Enter the details"))?.click()
        device.waitForIdle()
        val connect = device.wait(
            Until.findObject(By.desc("manual_setup_connect")),
            8_000,
        ) ?: device.wait(
            Until.findObject(By.text("Connect to Cache Vault on this PC")),
            5_000,
        )
        assertNotNull("Connect button not found", connect)
        connect.click()
    }
}
