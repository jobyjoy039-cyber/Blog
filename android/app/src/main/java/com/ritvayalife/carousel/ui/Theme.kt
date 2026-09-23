package com.ritvayalife.carousel.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import com.ritvayalife.carousel.R

val Green = Color(0xFF2E5E4E)
val DeepGreen = Color(0xFF1F3A34)
val Cream = Color(0xFFF5F1E8)
val Sand = Color(0xFFE8E2D6)
val Gold = Color(0xFFC2A87D)
val Gray = Color(0xFF6B6B6B)

val Inter = FontFamily(
    Font(R.font.inter_regular, FontWeight.Normal),
    Font(R.font.inter_medium, FontWeight.Medium),
)
val InterTight = FontFamily(Font(R.font.inter_tight_bold, FontWeight.Bold))

@Composable
fun RitvayaTheme(content: @Composable () -> Unit) {
    val colors = lightColorScheme(
        primary = Green,
        onPrimary = Color.White,
        primaryContainer = Sand,
        onPrimaryContainer = Green,
        secondary = Gold,
        onSecondary = Color.White,
        secondaryContainer = Sand,
        onSecondaryContainer = DeepGreen,
        background = Cream,
        onBackground = DeepGreen,
        surface = Cream,
        onSurface = DeepGreen,
        surfaceVariant = Sand,
        onSurfaceVariant = Gray,
        surfaceContainer = Color(0xFFFBF8F2),
        surfaceContainerLow = Color(0xFFFBF8F2),
        surfaceContainerHigh = Color(0xFFF0EBE0),
        outline = Color(0xFFB9C4BE),
    )
    val base = Typography()
    val typography = Typography(
        headlineSmall = base.headlineSmall.copy(fontFamily = InterTight, fontWeight = FontWeight.Bold),
        titleLarge = base.titleLarge.copy(fontFamily = InterTight, fontWeight = FontWeight.Bold),
        titleMedium = base.titleMedium.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
        titleSmall = base.titleSmall.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
        bodyLarge = base.bodyLarge.copy(fontFamily = Inter),
        bodyMedium = base.bodyMedium.copy(fontFamily = Inter),
        bodySmall = base.bodySmall.copy(fontFamily = Inter),
        labelLarge = base.labelLarge.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
        labelMedium = base.labelMedium.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
        labelSmall = base.labelSmall.copy(fontFamily = Inter, fontWeight = FontWeight.Medium),
    )
    MaterialTheme(colorScheme = colors, typography = typography, content = content)
}
