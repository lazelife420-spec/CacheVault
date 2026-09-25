package com.prooffoundry.cachevaultmobile.integration

import android.content.Context
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import android.net.Uri
import com.prooffoundry.cachevaultmobile.MainActivity
import com.prooffoundry.cachevaultmobile.R

/** Publishes stable launcher actions that enter real Cache Vault destinations. */
object AppShortcutPublisher {
    fun publish(context: Context) {
        val manager = context.getSystemService(ShortcutManager::class.java) ?: return
        manager.dynamicShortcuts = listOf(
            shortcut(context, "save", "Save", "Open Save on this phone", R.drawable.ic_shortcut_add),
            shortcut(context, "search", "Search", "Search this phone's vault", R.drawable.ic_shortcut_search),
            shortcut(context, "favorites", "Favorites", "Open saved favorites", R.drawable.ic_shortcut_favorite),
            shortcut(context, "safes", "Safes", "Organize items in Safes", R.drawable.ic_shortcut_safes),
        )
    }

    private fun shortcut(context: Context, id: String, label: String, longLabel: String, iconRes: Int) =
        ShortcutInfo.Builder(context, id)
            .setShortLabel(label)
            .setLongLabel(longLabel)
            .setIcon(Icon.createWithResource(context, iconRes))
            .setIntent(
                Intent(Intent.ACTION_VIEW, Uri.parse("cachevault://open/$id"), context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            )
            .build()
}
