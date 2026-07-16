package com.prooffoundry.cachevaultmobile.ui

import com.prooffoundry.cachevaultmobile.data.UserMessages

/**
 * Opens the "Check for update" destination. Kept separate from the Compose
 * screen so the trust properties are testable without an Android framework
 * (Intent/Uri can't be constructed in a plain JVM unit test here).
 */
object UpdateLauncher {
    /** Always this fixed constant — there is no parameter for a caller to override it with. */
    fun updateUrl(): String = UserMessages.TRUSTED_UPDATE_URL

    /**
     * Calls [openUrl] with the fixed trusted URL. [openUrl] does the actual
     * platform launch (building the Intent/Uri and calling startActivity)
     * and is expected to throw if nothing can handle it — that exception
     * never propagates out of here, and a failed launch returns `false`
     * rather than reporting success.
     */
    fun launchUpdate(openUrl: (String) -> Unit): Boolean =
        try {
            openUrl(updateUrl())
            true
        } catch (e: Exception) {
            false
        }
}
