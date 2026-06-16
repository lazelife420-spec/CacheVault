package com.prooffoundry.cachevaultmobile.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Verified
import androidx.compose.ui.graphics.vector.ImageVector

enum class MainTab(val label: String, val icon: ImageVector) {
    VAULT("Vault", Icons.Default.Home),
    BROWSE("Browse", Icons.Default.List),
    SCREENSHOTS("Screenshots", Icons.Default.Image),
    PROOF("Proof", Icons.Default.Verified),
    SETTINGS("Settings", Icons.Default.Settings),
}
