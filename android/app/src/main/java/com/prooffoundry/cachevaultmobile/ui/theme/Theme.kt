package com.prooffoundry.cachevaultmobile.ui.theme

import com.prooffoundry.cachevaultmobile.ui.theme.CompactTypography
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier

val FoundryBlack = Color(0xFF0B0F14)
val IronGray = Color(0xFF1C232B)
val ProofTeal = Color(0xFF00D1B2)
val ReceiptWhite = Color(0xFFF4F7F8)
val StampGold = Color(0xFFD6A84F)
val MutedText = Color(0xFF8A939C)

private val DarkColors = darkColorScheme(
    primary = ProofTeal,
    onPrimary = FoundryBlack,
    secondary = StampGold,
    background = FoundryBlack,
    surface = IronGray,
    onBackground = ReceiptWhite,
    onSurface = ReceiptWhite,
    onSurfaceVariant = MutedText,
)

@Composable
fun CacheVaultMobileTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = CompactTypography,
    ) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
            contentColor = MaterialTheme.colorScheme.onBackground,
            content = content,
        )
    }
}
