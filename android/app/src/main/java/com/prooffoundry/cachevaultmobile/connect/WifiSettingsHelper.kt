package com.prooffoundry.cachevaultmobile.connect

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.widget.Toast

object WifiSettingsHelper {
    /** Open Android Internet/Wi-Fi panel. User chooses the network. */
    fun openWifiSettings(context: Context) {
        val panel = Intent(Settings.Panel.ACTION_INTERNET_CONNECTIVITY)
        if (panel.resolveActivity(context.packageManager) != null) {
            context.startActivity(panel)
            return
        }
        val wifi = Intent(Settings.ACTION_WIFI_SETTINGS)
        if (wifi.resolveActivity(context.packageManager) != null) {
            context.startActivity(wifi)
            return
        }
        Toast.makeText(
            context,
            "Open Wi-Fi Settings from your phone Settings app.",
            Toast.LENGTH_LONG,
        ).show()
    }
}
