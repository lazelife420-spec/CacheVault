package com.prooffoundry.cachevaultmobile.data

import com.prooffoundry.cachevaultmobile.BuildConfig

/**
 * This app's own identity for the desktop version-compatibility handshake.
 * Sourced from the build (never hand-typed) so it can't drift from the APK
 * that's actually running.
 */
object AppIdentity {
    /** Bump only when this app's wire format changes in a breaking way. */
    const val PROTOCOL_VERSION = 1
    const val PLATFORM = "android"

    val APP_VERSION: String = BuildConfig.VERSION_NAME
    val APP_BUILD: Int = BuildConfig.VERSION_CODE
}
